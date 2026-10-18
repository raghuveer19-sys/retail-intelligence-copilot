"""Evaluate independent questions through the current chat pipeline, with separate review."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter

from retail_copilot.conversation import conversation_limits
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.evaluate import configuration, fingerprint, load_cases
from retail_copilot.pinecone_ingest import prepare_upload
from retail_copilot.pipeline import ChatError, run_chat_turn
from retail_copilot.plan_names import plan_aliases


DEFAULT_CASES = ("E01", "E05", "E07", "E08", "E09")
DEFAULT_OUTPUT = "data/processed/chat-evaluation-2026-10-18"
METRICS = ("pinecone_read_units", "query_embedding_input_tokens", "resolution_input_tokens",
           "resolution_output_tokens", "generation_input_tokens", "generation_output_tokens", "elapsed_seconds")


class ChatEvaluationError(ValueError):
    """An authored explanation that contains no provider response or credentials."""


def selected_cases(root: Path, settings: dict, identifiers: list[str] | None) -> list[dict]:
    cases = load_cases(root, settings)
    identifiers = list(DEFAULT_CASES) if identifiers is None else identifiers
    by_id = {case["test_id"]: case for case in cases}
    if not identifiers or len(identifiers) != len(set(identifiers)) or any(identifier not in by_id for identifier in identifiers):
        raise ChatEvaluationError("Choose distinct case IDs from the authored evaluation set.")
    selected = [deepcopy(by_id[identifier]) for identifier in identifiers]
    if any(case["evaluation_mode"] != "end_to_end" for case in selected):
        raise ChatEvaluationError("Controlled-context cases belong to the original evaluation runner, not ordinary chat.")
    return selected


def output_directory(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ChatEvaluationError("Choose a relative run directory directly inside data/processed.")
    processed = (root / "data/processed").resolve()
    output = (root / relative).resolve()
    if output.parent != processed or output == processed or output.suffix:
        raise ChatEvaluationError("Choose a separate run directory directly inside data/processed.")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ChatEvaluationError("This run directory already contains files. Choose a new empty directory; results are never overwritten or resumed.")
    return output


def build_manifest(root: Path, settings: dict, cases: list[dict], prepared: dict) -> dict:
    """Fingerprint code and approved inputs locally; never inspect a key or live model."""
    safe_settings = configuration(settings)
    safe_settings["demo"] = {"as_of_date": settings["demo"]["as_of_date"]}
    safe_settings["conversation"] = conversation_limits(settings)
    safe_settings["plan_aliases"] = plan_aliases(settings)
    # Limits affect execution as well as successful outputs. Connection addresses,
    # credentials, arbitrary extra settings and the environment are never copied.
    for section, keys in {
        "generation": ("timeout_seconds",), "embedding": ("max_input_tokens", "timeout_seconds"),
        "retrieval": ("request_timeout_seconds", "cloud", "region"),
    }.items():
        safe_settings[section].update({key: settings[section].get(key) for key in keys})
    sources = sorted((root / "src/retail_copilot").glob("*.py"))
    if not sources:
        raise ChatEvaluationError("The application source files are unavailable for this evaluation.")
    prompt = (root / settings["answering"]["system_prompt_file"]).resolve()
    prompts = (root / "prompts").resolve()
    if not prompt.is_relative_to(prompts) or prompt.suffix != ".md":
        raise ChatEvaluationError("The answering instructions must be inside the prompts directory.")
    inputs = sources + [prompt, root / "prompts/conversation.md", root / "evaluation/cases.json"]
    hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    identity = {
        "configuration": safe_settings, "input_file_sha256": hashes,
        "selected_cases_sha256": fingerprint(cases),
        "corpus": {"corpus_sha256": prepared["corpus_sha256"],
                   "embedding_model_digest": prepared["model_digest"], "as_of_date": prepared["as_of_date"],
                   "record_count": len(prepared["documents"])},
    }
    return {
        "schema_version": 1, "artifact_type": "chat_evaluation_manifest",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "entrypoint": "retail_copilot.pipeline.run_chat_turn", "history_policy": "empty_for_every_case",
        "case_ids": [case["test_id"] for case in cases], "identity": identity, "identity_sha256": fingerprint(identity),
        "retrieval_policy": "fresh_pipeline_requests_no_saved_answers_or_retrieval",
        "generation_model_identity": "Configured name in manifest; actual digest retained per turn when reported.",
        "semantic_review": "Separate review required; execution and source IDs do not establish correct answers.",
    }


def write_new(path: Path, value: dict) -> None:
    """Create a durable JSON artifact exclusively; never replace an existing file."""
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def measured_usage(result: dict, elapsed: float) -> dict:
    diagnostics = result["diagnostics"]
    retrieval, resolution, generation = (diagnostics.get(name) for name in ("retrieval", "resolution", "generation"))
    def tokens(component, name, *, skipped=False):
        if component is None or skipped:
            return 0
        usage = component.get("usage")
        return _number(usage.get(name)) if isinstance(usage, dict) else None
    no_generation = isinstance(generation, dict) and generation.get("model_call_made") is False
    return {
        "pinecone_read_units": 0 if retrieval is None else _number(retrieval.get("pinecone_read_units")),
        "query_embedding_input_tokens": 0 if retrieval is None else _number(retrieval.get("query_prompt_tokens")),
        # None usage on a resolver result can mean a bypass OR an unmeasured
        # failed call. Its absence is not evidence of zero token consumption.
        "resolution_input_tokens": tokens(resolution, "prompt_tokens"),
        "resolution_output_tokens": tokens(resolution, "generated_tokens_including_thinking"),
        "generation_input_tokens": tokens(generation, "prompt_tokens", skipped=no_generation),
        "generation_output_tokens": tokens(generation, "generated_tokens_including_thinking", skipped=no_generation),
        "elapsed_seconds": elapsed,
    }


def _validate_result(result: dict, question: str) -> None:
    if (not isinstance(result, dict) or result.get("question") != question
            or not isinstance(result.get("text"), str) or not result["text"].strip()
            or result.get("status") not in ("supported", "insufficient_evidence", "needs_clarification", "action_not_supported", "acknowledgement")
            or not isinstance(result.get("diagnostics"), dict)):
        raise ChatEvaluationError("The chat did not return a complete current result.")
    diagnostics = result["diagnostics"]
    if any(field not in diagnostics for field in ("retrieval", "resolution", "context", "generation", "citations")):
        raise ChatEvaluationError("The chat did not retain its evidence and execution details.")
    if not isinstance(diagnostics["citations"], list):
        raise ChatEvaluationError("The current result has an invalid citation record.")
    if diagnostics["retrieval"] is not None:
        if (not isinstance(diagnostics["retrieval"], dict) or not isinstance(diagnostics["context"], dict)
                or not isinstance(diagnostics["context"].get("context_text"), str)
                or not isinstance(diagnostics["context"].get("source_registry"), dict)
                or not isinstance(diagnostics["generation"], dict)
                or diagnostics["generation"].get("source_ids_valid") is not True):
            raise ChatEvaluationError("A policy answer is missing complete evidence or validated source references.")


def run_case(case: dict, settings: dict, manifest_hash: str) -> dict:
    """One attempt only. Expectations never enter the application call."""
    started = perf_counter()
    base = {
        "schema_version": 1, "test_id": case["test_id"], "category": case["category"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "manifest_identity_sha256": manifest_hash,
        "input": {"question": case["user_question"], "history": []},
        "authored_expectations_not_sent_to_pipeline": {key: deepcopy(case.get(key)) for key in (
            "expected_source", "expected_behaviour", "reference_answer", "must_include", "must_not_include", "excluded_document_ids", "notes")},
        "semantic_review": {"status": "pending", "claim_support": None, "completeness": None,
                            "response_behaviour": None, "action_boundary": None, "overall_pass": None},
    }
    try:
        result = run_chat_turn(case["user_question"], [], settings)
        _validate_result(result, case["user_question"])
        elapsed = perf_counter() - started
        retrieved = result["diagnostics"]["retrieval"]
        generation = result["diagnostics"]["generation"]
        expected = {(source["document_id"], source["section_id"]) for source in case["expected_source"]}
        found = {(hit["metadata"]["document_id"], hit["metadata"]["section_id"])
                 for hit in retrieved["matches"]} if retrieved is not None else set()
        return {
            **base, "artifact_type": "chat_evaluation_case", "execution_status": "completed",
            "result": result, "result_sha256": fingerprint(result), "usage": measured_usage(result, elapsed),
            "automated_checks": {
                "result_structure_valid": True, "retrieval_performed": retrieved is not None,
                "source_ids_valid": generation.get("source_ids_valid") if generation is not None else None,
                "source_id_check_scope": "Only generated policy drafts; not applicable to an early clarification or acknowledgement.",
            },
            "retrieval_review": {
                "scope": "all_returned_sections_after_bounded_policy_lookup" if retrieved is not None else "not_performed",
                "expected_sections": len(expected), "matched_sections": len(expected & found) if retrieved is not None else None,
                "expected_section_recall": len(expected & found) / len(expected) if retrieved is not None and expected else None,
                "missing_expected_sections": sorted(expected - found) if retrieved is not None else None,
                "excluded_source_leakage": sorted({hit["metadata"]["document_id"] for hit in retrieved["matches"]}
                                                  & set(case.get("excluded_document_ids", []))) if retrieved is not None else None,
            },
        }
    except Exception as error:
        # ChatError is deliberately authored by the application. Other exception
        # bodies may contain credentials or provider output and are never saved.
        message = str(error) if isinstance(error, ChatError) else "This case could not complete. No successful answer is claimed; technical error details were withheld."
        return {
            **base, "artifact_type": "chat_evaluation_failure", "execution_status": "failed",
            "result": None, "failure": {"message": message, "usage_for_failed_calls": None},
            "usage": {**{key: None for key in METRICS}, "elapsed_seconds": perf_counter() - started},
        }


def build_summary(records: list[dict], manifest_hash: str) -> dict:
    totals = {}
    for metric in METRICS:
        known = [_number(record["usage"].get(metric)) for record in records]
        missing = [record["test_id"] for record, value in zip(records, known, strict=True) if value is None]
        reported = sum(value for value in known if value is not None) if any(value is not None for value in known) else None
        totals[metric] = {"reported_subtotal": reported, "complete_total": reported if not missing else None,
                          "known_cases": len(records) - len(missing), "unknown_case_ids": missing}
    completed = [record for record in records if record["execution_status"] == "completed"]
    return {
        "schema_version": 1, "artifact_type": "chat_evaluation_summary",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "manifest_identity_sha256": manifest_hash,
        "requested_cases": len(records), "completed_cases": len(completed), "failed_cases": len(records) - len(completed),
        "case_outcomes": [{"test_id": record["test_id"], "execution_status": record["execution_status"],
                           "response_status": record["result"]["status"] if record["result"] is not None else None} for record in records],
        "usage": totals, "external_generation_charge_usd": "0", "pinecone_charge_usd": None, "local_hardware_cost_usd": None,
        "usage_note": "Subtotals include known usage only. Missing resolver usage or failed-call usage is unknown, not zero. Elapsed time is measured for every attempted case.",
        "reviewed_cases": 0, "answer_quality_pass_rate": None,
        "review_note": "Completed execution and valid source IDs do not prove groundedness, completeness or correct behaviour. Review the displayed text against the actual retained evidence.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Call the current chat pipeline once per selected case and save separate results.")
    parser.add_argument("--case", action="append", help="Select an authored normal case; repeat for a subset. Defaults to E01/E05/E07/E08/E09.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, help="New empty directory directly inside data/processed; never resumes or overwrites.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        cases = selected_cases(PROJECT_ROOT, settings, args.case)
        output = output_directory(PROJECT_ROOT, args.output_dir)
        prepared = prepare_upload(PROJECT_ROOT, settings)
        manifest = build_manifest(PROJECT_ROOT, settings, cases, prepared)
        if not args.run:
            print(f"Chat evaluation: PREVIEW ONLY | {', '.join(manifest['case_ids'])}")
            print("Each case will use run_chat_turn with an empty history. Expected answers remain outside the pipeline.")
            print("No service calls, model inference or files written. Use --run for one attempt per case; reviews remain separate.")
            return 0
        output.mkdir(parents=False, exist_ok=True)
        write_new(output / "manifest.json", manifest)
        records = []
        for case in cases:
            print(f"{case['test_id']}: running the current chat pipeline...", flush=True)
            record = run_case(case, settings, manifest["identity_sha256"])
            suffix = "-failure" if record["execution_status"] == "failed" else ""
            write_new(output / f"{case['test_id']}{suffix}.json", record)
            records.append(record)
            print(f"{case['test_id']}: {record['execution_status']}; semantic review pending.", flush=True)
        summary = build_summary(records, manifest["identity_sha256"])
        write_new(output / "summary.json", summary)
        print(f"Saved {len(records)} case records to {output.relative_to(PROJECT_ROOT).as_posix()}. No answer-quality pass rate is claimed.")
        return int(bool(summary["failed_cases"]))
    except ChatEvaluationError as error:
        print(f"Chat evaluation stopped: {error}")
    except Exception:
        print("Chat evaluation stopped: check the local evaluation inputs and output directory. Existing files were preserved; a call may already have consumed usage.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
