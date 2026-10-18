"""Preview a labelled evidence pack from saved retrieval; no service calls."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math

from langchain_core.documents import Document

from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.pinecone_ingest import IngestionError, prepare_upload
from retail_copilot.policy_lookup import policy_ids
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path


class ContextError(ValueError):
    """An explanation that can be printed without exposing credentials."""


def select_result(saved: dict, case_id: str) -> dict:
    """Choose a saved case by label; never use expected answers to select evidence."""
    if not isinstance(saved, dict) or saved.get("schema_version") != 1 or not isinstance(saved.get("results"), list):
        raise ContextError("Choose a saved retrieval baseline report with a results list.")
    if any(not isinstance(item, dict) or not isinstance(item.get("evaluation"), dict) for item in saved["results"]):
        raise ContextError("The saved retrieval cases need valid case labels.")
    matches = [item for item in saved["results"] if item["evaluation"].get("test_id") == case_id]
    if len(matches) != 1:
        raise ContextError("The selected case must occur exactly once in the saved retrieval report.")
    return matches[0]


def build_context(result: dict, prepared: dict, settings: dict) -> dict:
    """Keep complete validated candidates; remove exact duplicate IDs, never truncate."""
    options = settings["context"]
    max_sources, max_characters = options["max_sources"], options["max_characters"]
    if type(max_sources) is not int or not 1 <= max_sources <= 20:
        raise ContextError("Set the context source limit to a whole number from 1 to 20.")
    if type(max_characters) is not int or not 1 <= max_characters <= 100000:
        raise ContextError("Set the context character limit to a whole number from 1 to 100000.")
    identity = {
        "schema_version": 1, "as_of_date": prepared["as_of_date"],
        "model": settings["embedding"]["model"], "dimensions": settings["embedding"]["dimensions"],
        "model_digest": prepared["model_digest"], "corpus_sha256": prepared["corpus_sha256"],
        "index_name": settings["retrieval"]["index_name"], "namespace": settings["retrieval"]["namespace"],
    }
    if any(result.get(key) != value for key, value in identity.items()):
        raise ContextError("Saved retrieval does not match the configured corpus, model, destination or policy date.")
    question = result.get("question")
    retrieval_mode = result.get("retrieval_mode", "semantic")
    if retrieval_mode not in ("semantic", "semantic_with_policy_lookup", "controlled_context"):
        raise ContextError("The evidence needs a recognised retrieval or controlled-context mode.")
    if not isinstance(question, str) or not question.strip() or not isinstance(result.get("matches"), list):
        raise ContextError("The retrieval result needs a question and a list of passages.")
    field = settings["retrieval"]["vector_field"]
    expected = {doc["_id"]: {key: value for key, value in doc.items() if key != field}
                for doc in prepared["documents"]}
    seen, registry, sources = {}, {}, []
    duplicates = []
    for hit in result["matches"]:
        if not isinstance(hit, dict) or not isinstance(hit.get("metadata"), dict):
            raise ContextError("Each retrieved passage needs its original text and source metadata.")
        identifier = hit.get("chunk_id")
        if not isinstance(identifier, str) or identifier not in expected:
            raise ContextError("A saved passage has an unknown or excluded source ID.")
        source = expected[identifier]
        metadata = {key: value for key, value in source.items() if key not in ("_id", "text")}
        if hit.get("text") != source["text"] or hit["metadata"] != metadata:
            raise ContextError("Saved passage text or metadata differs from the approved local source. Review retrieval.")
        method = hit.get("retrieval_method", "semantic")
        score = hit.get("score")
        if method not in ("semantic", "policy_lookup", "controlled_context") or (
            method == "semantic" and (type(score) not in (int, float) or not math.isfinite(score))
        ) or (method in ("policy_lookup", "controlled_context") and score is not None):
            raise ContextError("Preserve real search scores; reference-fetched passages must have no similarity score.")
        if (method == "controlled_context") != (retrieval_mode == "controlled_context"):
            raise ContextError("Controlled-context evidence must be clearly labelled and cannot mix with search results.")
        if identifier in seen:
            if hit != seen[identifier]:
                raise ContextError("Two copies of the same chunk disagree. Review the saved retrieval report.")
            duplicates.append(identifier)
            continue
        seen[identifier] = deepcopy(hit)
        doc = Document(id=identifier, page_content=hit["text"], metadata=deepcopy(hit["metadata"]))
        label = f"S{len(sources) + 1}"
        sources.append({
            "source_id": label, "chunk_id": doc.id,
            **{key: doc.metadata[key] for key in (
                "document_id", "policy_id", "document_title", "version", "section_id", "section_heading", "source_file",
            )},
            "text": doc.page_content,
        })
        registry[label] = {
            "chunk_id": doc.id, "metadata": doc.metadata,
            "retrieval_method": method, "similarity_score": score,
            "lookup_origins": deepcopy(hit.get("lookup_origins", [])),
        }
    if len(sources) > max_sources:
        raise ContextError("The evidence pack exceeds the source limit. Review selection or limits; no passages were cut.")
    # JSON preserves text boundaries. It does not make policy text trusted instructions.
    evidence = {"question": question, "policy_date": prepared["as_of_date"], "sources": sources}
    context_text = json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False)
    if len(context_text) > max_characters:
        raise ContextError("The evidence pack exceeds the character limit. Review selection or limits; no text was cut.")
    represented = {source["policy_id"] for source in sources}
    mentioned = set(policy_ids(question))
    for source in sources:
        mentioned.update(policy_ids(source["text"]))
    return {
        **identity, "artifact_type": "context_preview", "preview_only": True,
        "retrieval_mode": retrieval_mode,
        "source_retrieval_created_at_utc": result.get("created_at_utc"),
        "question": question, "selection_policy": "all_validated_unique_candidates",
        "input_passage_count": len(result["matches"]), "selected_source_count": len(sources),
        "duplicate_chunk_ids_removed": duplicates, "source_registry": registry,
        "context_text": context_text, "context_characters": len(context_text),
        "context_utf8_bytes": len(context_text.encode("utf-8")),
        "passage_word_count": sum(len(doc["text"].split()) for doc in sources),
        "limits": {"max_sources": max_sources, "max_characters": max_characters},
        "references_without_passages": sorted(mentioned - represented),
        "evidence_sufficiency": "not_assessed" if sources else "no_retrieved_evidence",
        "model_input_tokens": None, "service_calls_made": 0, "external_request_charge_usd": "0",
        "generation_attempted": False, "answer_generated": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="Saved case label, for example E04; no expected answer is used.")
    parser.add_argument("--show", action="store_true", help="Print the full evidence text after its source list.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        options = settings["context"]
        input_path = generated_json_path(PROJECT_ROOT, options["input_file"])
        output = generated_json_path(PROJECT_ROOT, options["output_file"])
        protected = {input_path}
        for section, values in settings.items():
            if section != "context" and isinstance(values, dict):
                protected.update(generated_json_path(PROJECT_ROOT, value) for key, value in values.items()
                                 if key in ("output_file", "report_file", "baseline_output_file"))
        if output in protected:
            raise ContextError("Keep the context output separate from retrieval, chunk and embedding reports.")
        if output.exists():
            previous = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(previous, dict) or previous.get("artifact_type") != "context_preview":
                raise ContextError("The output already contains a different artifact. Choose a separate context file.")
        saved = json.loads(input_path.read_text(encoding="utf-8"))
        case_id = args.case or options["case_id"]
        result = select_result(saved, case_id)
        prepared = prepare_upload(PROJECT_ROOT, settings)  # Local validation only; no uploads or requests.
        pack = build_context(result, prepared, settings)
        pack.update({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                     "source_report": input_path.relative_to(PROJECT_ROOT).as_posix(), "case_id": case_id})
        save_chunk_export(pack, output)
        print(f"Context construction: OFFLINE PREVIEW | {case_id}")
        print(f"Question: {pack['question']}")
        print(f"Selected {pack['selected_source_count']} whole sections; removed {len(pack['duplicate_chunk_ids_removed'])} duplicate(s).")
        for label, source in pack["source_registry"].items():
            meta = source["metadata"]
            print(f"[{label}] {meta['document_title']} / {meta['section_heading']} | {meta['source_file']} | {source['retrieval_method']}")
        print(f"Complete pack: {pack['context_characters']} characters / limit {options['max_characters']}. Model tokens: not measured.")
        if pack["references_without_passages"]:
            print("Named policies without a passage: " + ", ".join(pack["references_without_passages"]))
        print(f"Evidence sufficiency: {pack['evidence_sufficiency']}. Source labels do not prove claim support.")
        print("No service calls, no external request charge and no generated answer.")
        print(f"Saved: {output.relative_to(PROJECT_ROOT).as_posix()}")
        if args.show:
            print(pack["context_text"])
        return 0
    except (ContextError, IngestionError) as error:
        print(f"Context preparation stopped: {error}")
    except (ValueError, KeyError, TypeError, OSError):
        print("Context preparation stopped: check the saved retrieval report, prepared corpus and configuration files.")
    print("No successful current pack is claimed. Earlier output may remain; check its timestamp.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
