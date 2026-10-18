"""Run the authored fictional evaluation cases, retaining evidence and honest review boundaries."""

import argparse
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path

from pinecone import Pinecone, RetryConfig

from retail_copilot.answering import AnsweringError, build_prompt, render_draft, validate_draft
from retail_copilot.context import ContextError, build_context
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.generate import GenerationError, generate_answer, generation_options, inspect_model
from retail_copilot.ollama_embeddings import LocalOllamaError
from retail_copilot.pinecone_ingest import IngestionError, check_index, prepare_upload
from retail_copilot.policy_lookup import PolicyLookupError, follow_policy_references, plan_lookup
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path
from retail_copilot.readiness import read_credential
from retail_copilot.retrieve import RetrievalError, retrieve_question, retrieval_options, score_expected_sources


class EvaluationError(ValueError):
    """A safe message that does not contain credentials or provider response bodies."""


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_cases(root: Path, settings: dict) -> list[dict]:
    cases = json.loads((root / "evaluation/cases.json").read_text(encoding="utf-8"))
    if (not isinstance(cases, list) or len(cases) != 15
            or any(not isinstance(case, dict) for case in cases)
            or {case.get("test_id") for case in cases} != {f"E{i:02}" for i in range(1, 16)}):
        raise EvaluationError("Keep the initial 15 authored cases, E01 to E15, in the evaluation file.")
    for case in cases:
        if (case.get("as_of_date") != settings["demo"]["as_of_date"]
                or case.get("evaluation_mode") not in ("end_to_end", "controlled_context")
                or not isinstance(case.get("user_question"), str) or not case["user_question"].strip()):
            raise EvaluationError("Evaluation cases must have a question, supported mode and configured policy date.")
    return cases


def configuration(settings: dict) -> dict:
    """Record only relevant non-secret settings; credentials and environment are never copied."""
    fields = {
        "generation": ("provider", "model", "num_ctx", "num_predict", "temperature", "template_reserve_tokens", "thinking_when_metadata_missing"),
        "embedding": ("provider", "model", "dimensions", "document_template", "query_template"),
        "retrieval": ("index_name", "namespace", "top_k", "metric", "vector_field"),
        "policy_lookup": ("max_policies", "max_added_chunks"),
        "context": ("max_sources", "max_characters"),
        "answering": ("system_prompt_file", "presentation", "max_draft_characters", "max_claims", "max_claim_characters"),
    }
    return {section: {key: settings[section].get(key) for key in keys} for section, keys in fields.items()}


def controlled_result(case: dict, prepared: dict, settings: dict) -> dict:
    """Provide the explicitly authored document subset, without search or fabricated scores."""
    identifiers = case.get("context_document_ids")
    if (case["evaluation_mode"] != "controlled_context" or not isinstance(identifiers, list)
            or not identifiers or len(set(identifiers)) != len(identifiers)):
        raise EvaluationError("A controlled case needs distinct approved document IDs.")
    selected = sorted((record for record in prepared["documents"]
                       if record["document_id"] in identifiers), key=lambda record: record["_id"])
    if {record["document_id"] for record in selected} != set(identifiers):
        raise EvaluationError("A controlled document is absent or not eligible on the policy date.")
    matches = []
    for record in selected:
        metadata = {key: deepcopy(value) for key, value in record.items()
                    if key not in ("_id", "text", settings["retrieval"]["vector_field"])}
        matches.append({"chunk_id": record["_id"], "text": record["text"], "metadata": metadata,
                        "score": None, "retrieval_method": "controlled_context"})
    return {
        "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "question": case["user_question"], "as_of_date": prepared["as_of_date"],
        "model": settings["embedding"]["model"], "dimensions": settings["embedding"]["dimensions"],
        "model_digest": prepared["model_digest"], "corpus_sha256": prepared["corpus_sha256"],
        "index_name": settings["retrieval"]["index_name"], "namespace": settings["retrieval"]["namespace"],
        "retrieval_mode": "controlled_context", "matches": matches,
        "query_prompt_tokens": 0, "pinecone_read_units": 0, "total_seconds": 0,
        "service_calls_made": 0, "answer_generated": False,
    }


def validate_retrieval(result: dict, case: dict, prepared: dict, settings: dict) -> dict:
    if result.get("question") != case["user_question"]:
        raise EvaluationError("Saved retrieval belongs to a different evaluation question.")
    pack = build_context(result, prepared, settings)
    if case["evaluation_mode"] == "controlled_context":
        expected = controlled_result(case, prepared, settings)
        if result.get("retrieval_mode") != "controlled_context" or result["matches"] != expected["matches"]:
            raise EvaluationError("Controlled evidence must contain only the complete authored document subset.")
        return pack
    if (result.get("retrieval_mode") != "semantic_with_policy_lookup"
            or result.get("top_k") != settings["retrieval"]["top_k"]
            or result.get("metric") != settings["retrieval"]["metric"]):
        raise EvaluationError("Saved retrieval does not use the current semantic search and bounded lookup settings.")
    semantic = deepcopy(result)
    semantic.pop("policy_lookup", None)
    semantic["matches"] = [hit for hit in result["matches"] if hit.get("retrieval_method", "semantic") == "semantic"]
    if len(semantic["matches"]) > settings["retrieval"]["top_k"]:
        raise EvaluationError("Saved retrieval exceeds the configured search size.")
    planned = plan_lookup(semantic, prepared, settings["policy_lookup"], settings["retrieval"]["vector_field"])
    lookup = result.get("policy_lookup", {})
    if any(lookup.get(key) != value for key, value in planned.items()):
        raise EvaluationError("Saved policy lookup no longer matches the configured bounded lookup plan.")
    fetched = [hit["chunk_id"] for hit in result["matches"] if hit.get("retrieval_method") == "policy_lookup"]
    if fetched != planned["requested_chunk_ids"]:
        raise EvaluationError("Saved retrieval does not contain every planned policy lookup passage.")
    return pack


def retrieval_metrics(result: dict, case: dict) -> dict:
    if case["evaluation_mode"] == "controlled_context":
        return {"measurement_scope": "controlled_context_not_retrieval", "semantic": None, "with_lookup": None}
    semantic = deepcopy(result)
    semantic.pop("policy_lookup", None)
    semantic["matches"] = [hit for hit in result["matches"] if hit.get("retrieval_method", "semantic") == "semantic"]
    return {"measurement_scope": "retrieval_only", "semantic": score_expected_sources(semantic, case),
            "with_lookup": score_expected_sources(result, case)}


def case_identity(case: dict, prepared: dict, settings: dict, instructions: str, digest: str) -> dict:
    return {"case_sha256": fingerprint(case), "configuration_sha256": fingerprint(configuration(settings)),
            "corpus_sha256": prepared["corpus_sha256"], "embedding_model_digest": prepared["model_digest"],
            "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
            "generation_model_digest": digest}


def initialise_run(output_dir: Path, cases: list, prepared: dict, settings: dict, instructions: str, digest: str) -> dict:
    """Prevent one run directory from silently mixing different experiment conditions."""
    identity = case_identity({"cases": cases}, prepared, settings, instructions, digest)
    path = output_dir / "manifest.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("artifact_type") != "evaluation_manifest" or saved.get("identity") != identity:
            raise EvaluationError("This evaluation directory uses different cases, model, prompt, corpus or settings. Choose a new output directory.")
        return saved
    if any(output_dir.iterdir()):
        raise EvaluationError("Choose an empty evaluation directory, or resume one with its original manifest.")
    manifest = {"schema_version": 1, "artifact_type": "evaluation_manifest", "identity": identity,
                "created_at_utc": datetime.now(timezone.utc).isoformat(), "configuration": configuration(settings),
                "case_ids": [case["test_id"] for case in cases]}
    save_chunk_export(manifest, path)
    return manifest


def check_generation(generated: dict, pack: dict, instructions: str, settings: dict, digest: str) -> None:
    preview = build_prompt(pack, instructions, settings)
    for key in ("context_sha256", "instructions_sha256", "messages", "source_registry"):
        if generated.get(key) != preview[key]:
            raise EvaluationError("Saved generation does not match the current evidence or instructions.")
    if (generated.get("artifact_type") != "generation_result" or generated.get("question") != pack["question"]
            or generated.get("context_text") != pack["context_text"]
            or generated.get("model") != settings["generation"]["model"]):
        raise EvaluationError("Saved generation belongs to a different question, model or context.")
    if pack["source_registry"]:
        options = generation_options(settings)
        expected_options = {key: options[key] for key in ("num_ctx", "num_predict", "temperature")}
        if (generated.get("model_call_made") is not True or generated.get("answer_generated") is not True
                or generated.get("model_digest") != digest or generated.get("done_reason") != "stop"
                or generated.get("options") != expected_options):
            raise EvaluationError("Saved generation did not complete with the currently installed model and configured options.")
        usage = generated.get("usage")
        if not isinstance(usage, dict):
            raise EvaluationError("Saved generation is missing its measured token usage.")
        prompt_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("generated_tokens_including_thinking")
        if (type(prompt_tokens) is not int or prompt_tokens <= 0
                or type(output_tokens) is not int or not 0 < output_tokens < options["num_predict"]
                or prompt_tokens + output_tokens > options["num_ctx"]):
            raise EvaluationError("Saved generation has invalid or out-of-bounds token usage.")
    elif (generated.get("model_call_made") is not False or generated.get("answer_generated") is not False
          or generated.get("draft") != preview["empty_context_fallback"] or generated.get("usage") is not None):
        raise EvaluationError("An empty context must use the fixed no-model fallback.")
    raw = json.dumps(generated["draft"], ensure_ascii=False)
    validate_draft(raw, pack, settings)
    if generated.get("answer") != render_draft(raw, pack, settings):
        raise EvaluationError("Saved rendered citations do not match the draft and source metadata.")


def baseline_candidates(root: Path, settings: dict) -> list[dict]:
    path = generated_json_path(root, settings["policy_lookup"]["baseline_output_file"])
    if not path.exists():
        return []
    saved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or not isinstance(saved.get("results"), list):
        raise EvaluationError("The previous retrieval baseline is not a valid result list.")
    return saved["results"]


def run_case(case: dict, prepared: dict, settings: dict, instructions: str, digest: str,
             output_dir: Path, baselines: list, get_index) -> dict:
    """Save retrieval before inference so a failed model call does not repeat Pinecone reads."""
    identity = case_identity(case, prepared, settings, instructions, digest)
    output = output_dir / f"{case['test_id']}.json"
    retrieval_path = output_dir / f"{case['test_id']}-retrieval.json"
    retrieval_source = "new_search"
    new_read_units = 0
    if output.exists():
        saved = json.loads(output.read_text(encoding="utf-8"))
        if saved.get("artifact_type") != "evaluation_case" or saved.get("identity") != identity:
            raise EvaluationError("An existing case has different settings, model, instructions or expectations. Use a new output directory.")
        if fingerprint(saved["generation"]) != saved.get("generation_sha256"):
            raise EvaluationError("A saved answer has changed. Preserve it and choose a new output directory.")
        pack = validate_retrieval(saved["retrieval"], case, prepared, settings)
        check_generation(saved["generation"], pack, instructions, settings, digest)
        return {"result": saved, "resumed": True, "new_pinecone_read_units": 0, "new_model_calls": 0}
    if retrieval_path.exists():
        cache = json.loads(retrieval_path.read_text(encoding="utf-8"))
        if cache.get("artifact_type") != "evaluation_retrieval" or cache.get("test_id") != case["test_id"]:
            raise EvaluationError("An existing retrieval cache belongs to a different artifact or case.")
        result = cache["retrieval"]
        validate_retrieval(result, case, prepared, settings)
        retrieval_source = "evaluation_cache"
    elif case["evaluation_mode"] == "controlled_context":
        result = controlled_result(case, prepared, settings)
        retrieval_source = "controlled_document_subset"
    else:
        candidates = [item for item in baselines if item.get("question") == case["user_question"]]
        if len(candidates) > 1:
            raise EvaluationError("The saved baseline repeats an evaluation question.")
        if candidates:
            result = deepcopy(candidates[0])
            validate_retrieval(result, case, prepared, settings)
            retrieval_source = "prior_baseline"
        else:
            index = get_index()
            result = follow_policy_references(index, retrieve_question(index, case["user_question"], prepared, settings), prepared, settings)
            new_read_units = result["pinecone_read_units"]
    pack = validate_retrieval(result, case, prepared, settings)
    if not retrieval_path.exists():
        save_chunk_export({"schema_version": 1, "artifact_type": "evaluation_retrieval", "test_id": case["test_id"],
                           "retrieval_source": retrieval_source, "retrieval": result}, retrieval_path)
    # Only the question and validated passages go to generation. No expected answer or rubric is supplied.
    generated = generate_answer(pack, instructions, settings, keep_alive_seconds=300)
    check_generation(generated, pack, instructions, settings, digest)
    completed = {
        "schema_version": 1, "artifact_type": "evaluation_case", "test_id": case["test_id"],
        "category": case["category"], "evaluation_mode": case["evaluation_mode"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "identity": identity,
        "configuration": configuration(settings), "retrieval_source": retrieval_source,
        "retrieval": result, "context": pack, "generation": generated, "generation_sha256": fingerprint(generated),
        "retrieval_metrics": retrieval_metrics(result, case),
        "answer_metrics": {"structured_output_valid": True, "source_ids_valid": True,
                           "claim_support": None, "citation_support": None, "completeness": None,
                           "action_boundary": None, "expected_behaviour": None, "review_status": "pending"},
    }
    save_chunk_export(completed, output)
    return {"result": completed, "resumed": False, "new_pinecone_read_units": new_read_units,
            "new_model_calls": int(generated["model_call_made"])}


def scorecard(results: list[dict], failures: list[dict], total: int) -> dict:
    end_to_end = [item for item in results if item["evaluation_mode"] == "end_to_end"]
    rows = [item["retrieval_metrics"]["with_lookup"] for item in end_to_end]
    expected, matched = sum(row["expected_count"] for row in rows), sum(row["matched_count"] for row in rows)
    return {
        "requested_cases": total, "completed_cases": len(results), "failed_cases": len(failures),
        "end_to_end_completed": len(end_to_end), "controlled_context_completed": len(results) - len(end_to_end),
        "expected_sections_found": matched, "expected_sections_total": expected,
        "expected_section_recall_with_lookup": matched / expected if expected else None,
        "retrieval_denominator": "Expected sections in completed end-to-end cases; excludes controlled cases and cases without expected sections.",
        "structured_answers_valid": len(results), "source_ids_valid": len(results),
        "claim_support_reviewed_cases": 0, "answer_quality_pass_rate": None,
        "review_note": "Structure and valid source IDs do not establish claim support, completeness or correct behaviour. Review every answer against its cited evidence and authored rubric.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run local generation and any missing Pinecone retrieval; otherwise preview only.")
    parser.add_argument("--output-dir", default="data/processed/evaluation-baseline", help="Separate result directory inside data/processed; matching cases resume.")
    parser.add_argument("--case", action="append", help="Run one named case; repeat for a subset. Defaults to all 15.")
    args = parser.parse_args(argv)
    logging.getLogger("pinecone").setLevel(logging.CRITICAL)
    try:
        settings = load_settings()
        cases = load_cases(PROJECT_ROOT, settings)
        if args.case:
            if len(set(args.case)) != len(args.case) or any(identifier not in {case["test_id"] for case in cases} for identifier in args.case):
                raise EvaluationError("Choose distinct case IDs from E01 to E15.")
            cases = [case for case in cases if case["test_id"] in args.case]
        output_dir = generated_json_path(PROJECT_ROOT, str(Path(args.output_dir) / "summary.json")).parent
        if output_dir == (PROJECT_ROOT / "data/processed").resolve():
            raise EvaluationError("Use a separate evaluation subdirectory inside data/processed.")
        options = generation_options(settings)
        prepared = prepare_upload(PROJECT_ROOT, settings)
        prompt_path = (PROJECT_ROOT / settings["answering"]["system_prompt_file"]).resolve()
        if not prompt_path.is_relative_to((PROJECT_ROOT / "prompts").resolve()) or prompt_path.suffix != ".md":
            raise EvaluationError("Keep answering instructions inside prompts/ as a Markdown file.")
        instructions = prompt_path.read_text(encoding="utf-8")
        baselines = baseline_candidates(PROJECT_ROOT, settings)
        if not args.run:
            print(f"Evaluation: PREVIEW ONLY | {len(cases)} authored cases | local model {options['model']}")
            print("Normal cases use semantic search plus one bounded policy lookup; E11 supplies only its SIM document.")
            print("Valid saved retrieval and completed matching answers are reused. Missing retrieval uses Pinecone read units.")
            print("No service calls, no model inference and no files written. Use --run to execute.")
            return 0
        digest = inspect_model(options)["digest"]
        output_dir.mkdir(parents=True, exist_ok=True)
        initialise_run(output_dir, load_cases(PROJECT_ROOT, settings), prepared, settings, instructions, digest)
        summary_path = output_dir / "summary.json"
        if summary_path.exists() and json.loads(summary_path.read_text(encoding="utf-8")).get("artifact_type") != "evaluation_summary":
            raise EvaluationError("The summary path contains another artifact; choose a separate directory.")
        results, failures, execution = [], [], []
        _, timeout = retrieval_options(settings)
        with ExitStack() as stack:
            index = None

            def get_index():
                nonlocal index
                if index is None:
                    key = read_credential("PINECONE_API_KEY", PROJECT_ROOT)
                    if not key:
                        raise EvaluationError("Configure PINECONE_API_KEY privately before missing retrieval can run.")
                    client = stack.enter_context(Pinecone(api_key=key, timeout=timeout, retry_config=RetryConfig(max_retries=0)))
                    info = client.indexes.describe(settings["retrieval"]["index_name"])
                    check_index(info, settings, prepared)
                    index = stack.enter_context(client.index(host=info.host))
                return index

            for case in cases:
                print(f"{case['test_id']}: preparing evidence and local answer...", flush=True)
                try:
                    outcome = run_case(case, prepared, settings, instructions, digest, output_dir, baselines, get_index)
                    results.append(outcome.pop("result"))
                    execution.append({"test_id": case["test_id"], **outcome})
                    print(f"{case['test_id']}: {'reused' if outcome['resumed'] else 'saved'}; source IDs checked, claim review pending.", flush=True)
                except Exception as error:
                    # Never echo raw provider errors. A failed call may have consumed local time or Pinecone reads.
                    failure = {"test_id": case["test_id"], "status": "failed", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                               "message": str(error) if isinstance(error, (EvaluationError, GenerationError, AnsweringError, ContextError, LocalOllamaError, PolicyLookupError, RetrievalError, IngestionError)) else "The case could not finish. Check model/service availability and settings; no successful answer is claimed.",
                               "failure_type": type(error).__name__,
                               "usage_for_failed_calls": None}
                    failures.append(failure)
                    failure_path = output_dir / f"{case['test_id']}-failure.json"
                    if not failure_path.exists():
                        save_chunk_export({"artifact_type": "evaluation_failure", **failure}, failure_path)
                    print(f"{case['test_id']}: failed; prior evidence retained; raw error details hidden.", flush=True)
        summary = {"schema_version": 1, "artifact_type": "evaluation_summary", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                   "cases_sha256": fingerprint(load_cases(PROJECT_ROOT, settings)), "configuration": configuration(settings),
                   "model_digest": digest, "scorecard": scorecard(results, failures, len(cases)), "failures": failures,
                   "this_invocation": execution, "completed_case_ids": [item["test_id"] for item in results],
                   "external_generation_charge_usd": "0", "local_hardware_cost_usd": None, "pinecone_charge_usd": None}
        save_chunk_export(summary, summary_path)
        print(f"Completed {len(results)}/{len(cases)}; failures {len(failures)}. Semantic answer review remains separate.")
        print(f"Saved: {summary_path.relative_to(PROJECT_ROOT).as_posix()}")
        return 1 if failures else 0
    except EvaluationError as error:
        print(f"Evaluation stopped: {error}")
    except Exception:
        print("Evaluation stopped: check the local corpus, evaluation file, model and configuration. Provider details were not logged.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
