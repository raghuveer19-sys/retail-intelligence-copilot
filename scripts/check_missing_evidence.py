"""Preview or run the authored SIM-only missing-evidence component check."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from retail_copilot.answering import AnsweringError, build_prompt, render_draft, revalidate_pack
from retail_copilot.context import ContextError, build_context
from retail_copilot.documents import load_settings
from retail_copilot.evaluate import EvaluationError, configuration, controlled_result, fingerprint, load_cases
from retail_copilot.evaluate_chat import write_new
from retail_copilot.generate import GenerationError, generate_answer, generation_options, input_budget
from retail_copilot.ollama_embeddings import LocalOllamaError
from retail_copilot.pinecone_ingest import IngestionError, prepare_upload
from retail_copilot.pipeline import _natural_text
from retail_copilot.plan_names import display_plan_names, plan_aliases
from retail_copilot.prepare_embeddings import generated_json_path
from retail_copilot.source_guidance import assemble_source_guidance


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = "data/processed/demo-missing-evidence-2026-10-18.json"


def prepare_check(root: Path, settings: dict) -> dict:
    """Read local approved inputs; deliberately do not follow policy references."""
    case = next(case for case in load_cases(root, settings) if case["test_id"] == "E11")
    if case["evaluation_mode"] != "controlled_context" or case.get("context_document_ids") != ["SIM-1024-v2"]:
        raise EvaluationError("Keep this check limited to the authored E11 SIM-only context.")
    if settings["answering"].get("presentation") != "source_passages":
        raise EvaluationError("This check requires the current source-passages presentation setting.")
    prepared = prepare_upload(root, settings)
    retrieval = controlled_result(case, prepared, settings)
    pack = revalidate_pack(build_context(retrieval, prepared, settings), prepared, settings)
    prompt = (root / settings["answering"]["system_prompt_file"]).resolve()
    if not prompt.is_relative_to((root / "prompts").resolve()) or prompt.suffix != ".md":
        raise EvaluationError("Keep answering instructions inside the prompts directory.")
    paths = sorted((root / "src/retail_copilot").glob("*.py"))
    paths += [prompt, root / "evaluation/cases.json", Path(__file__).resolve()]
    hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    return {"case": case, "context": pack, "controlled_retrieval": retrieval,
            "instructions": prompt.read_text(encoding="utf-8"), "input_file_sha256": hashes}


def run_check(inputs: dict, settings: dict) -> dict:
    """Use the same generation and display components, without the chat retriever."""
    pack = inputs["context"]
    generation = generate_answer(pack, inputs["instructions"], settings)
    assembled = assemble_source_guidance(generation["draft"], pack, settings)
    final = assembled["draft"]
    display_settings = deepcopy(settings)
    display_settings["answering"]["max_claims"] = settings["context"]["max_sources"]
    rendered = render_draft(json.dumps(final), pack, display_settings)
    aliases = plan_aliases(settings)
    text = display_plan_names(_natural_text(final, "source_passages", assembled["trace"]), aliases)
    result = {"question": pack["question"], "status": final["status"], "text": text,
              "diagnostics": {"context": deepcopy(pack), "controlled_retrieval": inputs["controlled_retrieval"],
                              "generation": {**deepcopy(generation), "model_draft": deepcopy(generation["draft"]),
                                             "draft": final, "presentation": "source_passages",
                                             "source_assembly": assembled["trace"]},
                              "citations": rendered["citations"]}}
    case = inputs["case"]
    expectations = {key: deepcopy(case.get(key)) for key in
                    ("expected_source", "expected_behaviour", "reference_answer", "must_include",
                     "must_not_include", "excluded_document_ids", "notes")}
    return {
        "schema_version": 1, "artifact_type": "controlled_component_check", "test_id": "E11",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "evaluation_mode": "controlled_context",
        "scope": "Current generation and source-passage display with only authored SIM evidence; not chat end-to-end.",
        "input": {"question": pack["question"], "context_document_ids": case["context_document_ids"]},
        "configuration": {**configuration(settings), "plan_aliases": aliases},
        "input_file_sha256": inputs["input_file_sha256"],
        "authored_expectations_not_sent_to_model": expectations,
        "generation_result": generation, "result": result, "result_sha256": fingerprint(result),
        "usage": {"pinecone_read_units": 0, "query_embedding_input_tokens": 0,
                  "generation": deepcopy(generation.get("usage")),
                  "generation_seconds": generation.get("generation_seconds"),
                  "external_request_charge_usd": generation["external_request_charge_usd"],
                  "local_hardware_cost_usd": generation["local_hardware_cost_usd"]},
        "retrieval_review": {"scope": "controlled SIM-only evidence; search quality not measured",
                             "expected_section_recall": None, "pinecone_requests": 0},
        "semantic_review": "pending; source-text equality does not establish relevance, completeness or correct status",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Call local Ollama once; no Pinecone or embedding request.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="New JSON inside data/processed; never overwritten.")
    args = parser.parse_args(argv)
    try:
        output = generated_json_path(PROJECT_ROOT, args.output)
        if output.exists():
            raise EvaluationError("The output already exists. Choose a new file; earlier evidence is preserved.")
        settings = load_settings()
        inputs = prepare_check(PROJECT_ROOT, settings)
        preview = build_prompt(inputs["context"], inputs["instructions"], settings)
        options = generation_options(settings)
        budget = input_budget(preview["messages"], options)
        if not args.run:
            print("Missing-evidence component check: PREVIEW ONLY")
            print(f"Question: {inputs['case']['user_question']}")
            print(f"Model: {options['model']}; supplied documents: SIM-1024-v2 only.")
            print(f"Sources: {len(inputs['context']['source_registry'])}; conservative input allowance: {budget['input_token_allowance']}.")
            print("No model, embedding or Pinecone requests; no output file. Use --run for one local check.")
            return 0
        print("Generating from SIM-only evidence locally. No Pinecone or embedding requests; local computing time is used.", flush=True)
        artifact = run_check(inputs, settings)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_new(output, artifact)
        print(artifact["result"]["text"])
        print(f"Saved {output.relative_to(PROJECT_ROOT).as_posix()}. Separate semantic review is required.")
        return 0
    except (EvaluationError, AnsweringError, ContextError, GenerationError, IngestionError, LocalOllamaError) as error:
        print(f"Controlled check stopped: {error}")
    except (ValueError, KeyError, TypeError, OSError, StopIteration):
        print("Controlled check stopped: verify local settings, evidence and model availability. Provider details were not logged.")
    print("No completed current result was accepted. Existing files were preserved; an attempted call may have used local computing time.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
