"""Prepare answering instructions and validate source references without model calls."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re

from retail_copilot.context import ContextError, build_context
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.pinecone_ingest import IngestionError, prepare_upload
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path


class AnsweringError(ValueError):
    """A safe description of an invalid pack, prompt or draft."""


STATUS_MESSAGES = {
    "supported": "",
    "insufficient_evidence": "I could not find enough approved evidence to answer this reliably. Please consult the authorised support channel or policy owner.",
    "needs_clarification": "I need one clarification before answering.",
    "action_not_supported": "I can explain the policy and next steps, but I cannot perform the requested action or verify anyone's eligibility.",
}


def answer_limits(settings: dict) -> dict:
    options = settings["answering"]
    limits = {key: options[key] for key in ("max_draft_characters", "max_claims", "max_claim_characters")}
    for key, upper in (("max_draft_characters", 50000), ("max_claims", 20), ("max_claim_characters", 4000)):
        if type(limits[key]) is not int or not 1 <= limits[key] <= upper:
            raise AnsweringError("Answering limits must be positive whole numbers within the teaching limits.")
    return limits


def revalidate_pack(pack: dict, prepared: dict, settings: dict) -> dict:
    """Rebuild the saved pack from its records so changed labels/text cannot be trusted."""
    if not isinstance(pack, dict) or pack.get("artifact_type") != "context_preview":
        raise AnsweringError("Choose a context preview created by the context command.")
    evidence = json.loads(pack["context_text"])
    if not isinstance(evidence, dict) or not isinstance(evidence.get("sources"), list) or not isinstance(pack.get("source_registry"), dict):
        raise AnsweringError("The context needs an evidence list and source registry.")
    labels = [f"S{position + 1}" for position in range(len(evidence["sources"]))]
    if set(pack["source_registry"]) != set(labels):
        raise AnsweringError("The context source labels and registry do not agree.")
    hits = []
    for label, source in zip(labels, evidence["sources"], strict=True):
        if not isinstance(source, dict) or source.get("source_id") != label:
            raise AnsweringError("Keep source labels in their original context order.")
        entry = pack["source_registry"][label]
        if not isinstance(entry, dict) or entry.get("chunk_id") != source.get("chunk_id"):
            raise AnsweringError("A source label points to a different passage.")
        hits.append({"chunk_id": source["chunk_id"], "text": source["text"], "metadata": entry["metadata"],
                     "score": entry["similarity_score"], "retrieval_method": entry["retrieval_method"],
                     "lookup_origins": entry["lookup_origins"]})
    rebuilt = build_context({**pack, "matches": hits, "created_at_utc": pack.get("source_retrieval_created_at_utc")}, prepared, settings)
    if rebuilt["retrieval_mode"] != pack.get("retrieval_mode", "semantic"):
        raise AnsweringError("The saved evidence mode changed. Rebuild the context.")
    for key in ("context_text", "source_registry", "selected_source_count", "references_without_passages", "evidence_sufficiency"):
        if rebuilt[key] != pack.get(key):
            raise AnsweringError("The saved context changed or its source labels no longer match. Rebuild the context.")
    return rebuilt


def _compact_evidence_message(pack: dict) -> str:
    """Keep whole passages and labels; citation metadata stays in the saved pack."""
    evidence = json.loads(pack["context_text"])
    return json.dumps({
        "policy_date": evidence["policy_date"],
        "sources": [{
            "source_id": source["source_id"],
            "title": source["document_title"],
            "section": source["section_heading"],
            "text": source["text"],
        } for source in evidence["sources"]],
        # Put the actual question after the evidence without changing its text.
        "question": pack["question"],
    }, ensure_ascii=False, indent=2)


def build_prompt(pack: dict, instructions: str, settings: dict) -> dict:
    """Use a revalidated pack; keep instructions separate from question/source data."""
    limits = answer_limits(settings)
    if not isinstance(instructions, str) or not instructions.strip():
        raise AnsweringError("The answering instructions file is empty.")
    response_format = {
        "required_keys": ["status", "claims", "clarifying_question"],
        "status_choices": list(STATUS_MESSAGES),
        "claim_shape": {"text": "A short statement supported by the cited passages", "source_ids": ["S1"]},
        "clarifying_question": "A question string for needs_clarification; otherwise null",
        "allowed_source_ids": list(pack["source_registry"]), **limits,
    }
    has_evidence = bool(pack["source_registry"])
    messages = [
        {"role": "system", "content": instructions.strip() + "\n\nResponse format:\n" + json.dumps(response_format, indent=2)},
        {"role": "user", "content": _compact_evidence_message(pack)},
    ] if has_evidence else []
    return {
        "schema_version": 1, "artifact_type": "answering_preview", "preview_only": True,
        "question": pack["question"], "as_of_date": pack["as_of_date"],
        "context_sha256": hashlib.sha256(pack["context_text"].encode("utf-8")).hexdigest(),
        "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
        "messages": messages, "response_format": response_format,
        "source_registry": deepcopy(pack["source_registry"]),
        "empty_context_fallback": None if has_evidence else {"status": "insufficient_evidence", "claims": [], "clarifying_question": None},
        "message_characters": sum(len(message["content"]) for message in messages),
        "model_input_tokens": None, "service_calls_made": 0, "external_request_charge_usd": "0",
        "model_call_made": False, "answer_generated": False,
    }


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AnsweringError("The draft repeats a JSON field. No answer was accepted.")
        result[key] = value
    return result


def validate_draft(raw: str, pack: dict, settings: dict) -> dict:
    """Check structure and IDs against a revalidated pack, not semantic claim support."""
    limits = answer_limits(settings)
    if not isinstance(raw, str) or not raw.strip() or len(raw) > limits["max_draft_characters"]:
        raise AnsweringError("The draft is empty or exceeds the configured character limit.")
    try:
        draft = json.loads(raw, object_pairs_hook=unique_json_object)
    except json.JSONDecodeError:
        raise AnsweringError("The draft must be one JSON object without extra text or Markdown fences.") from None
    if not isinstance(draft, dict) or set(draft) != {"status", "claims", "clarifying_question"}:
        raise AnsweringError("The draft does not use the required response fields.")
    if not isinstance(draft["status"], str) or draft["status"] not in STATUS_MESSAGES:
        raise AnsweringError("The draft has an unsupported response status.")
    claims = draft["claims"]
    if not isinstance(claims, list) or len(claims) > limits["max_claims"]:
        raise AnsweringError("The draft has too many claims or an invalid claims list.")
    if draft["status"] == "supported" and not claims:
        raise AnsweringError("A supported answer needs at least one sourced claim.")
    question = draft["clarifying_question"]
    if draft["status"] == "needs_clarification":
        if claims or not isinstance(question, str) or not question.strip() or len(question) > limits["max_claim_characters"]:
            raise AnsweringError("A clarification response needs one question and no policy claims.")
    elif question is not None:
        raise AnsweringError("Use a clarifying question only with needs_clarification.")
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"text", "source_ids"}:
            raise AnsweringError("Each claim needs text and a separate source_ids list.")
        text, ids = claim["text"], claim["source_ids"]
        if not isinstance(text, str) or not text.strip() or len(text) > limits["max_claim_characters"]:
            raise AnsweringError("A claim is empty or exceeds its character limit.")
        if not isinstance(ids, list) or not ids or any(not isinstance(label, str) for label in ids):
            raise AnsweringError("Every policy claim needs a list of supporting source IDs.")
        if len(ids) != len(set(ids)) or any(label not in pack["source_registry"] for label in ids):
            raise AnsweringError("A claim cites an unknown or repeated source ID. No answer was accepted.")
    # Citation text is rendered by the application, never supplied as model footnotes.
    for text in [claim["text"] for claim in claims] + ([question] if question is not None else []):
        if "[" in text or "]" in text or re.search(r"https?://|www\.", text, re.IGNORECASE):
            raise AnsweringError("Keep citations and links out of draft text; use the source_ids field.")
    return deepcopy(draft)


def render_draft(raw: str, pack: dict, settings: dict) -> dict:
    """Reject invalid drafts in full, then render citation labels from actual metadata."""
    draft = validate_draft(raw, pack, settings)
    lines = ["Fictional training guidance."]
    if STATUS_MESSAGES[draft["status"]]:
        lines.append(STATUS_MESSAGES[draft["status"]])
    citations = {}
    for claim in draft["claims"]:
        lines.append(claim["text"] + " " + " ".join(f"[{label}]" for label in claim["source_ids"]))
        for label in claim["source_ids"]:
            entry = pack["source_registry"][label]
            metadata = entry["metadata"]
            citations.setdefault(label, {"source_id": label, "chunk_id": entry["chunk_id"], **{
                key: metadata[key] for key in ("document_title", "section_heading", "source_file", "document_id", "version")
            }})
    if draft["clarifying_question"] is not None:
        lines.append(draft["clarifying_question"])
    for label, citation in citations.items():
        lines.append(f"[{label}] {citation['document_title']} / {citation['section_heading']} ({citation['source_file']}, version {citation['version']})")
    return {"status": draft["status"], "text": "\n\n".join(lines), "citations": list(citations.values()),
            "source_ids_valid": True, "claim_support_checked": False, "action_claims_checked": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="Print the prepared instructions and evidence; do not call a model.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        options = settings["answering"]
        input_path = generated_json_path(PROJECT_ROOT, options["input_file"])
        output = generated_json_path(PROJECT_ROOT, options["output_file"])
        protected = {input_path}
        for section, values in settings.items():
            if section != "answering" and isinstance(values, dict):
                protected.update(generated_json_path(PROJECT_ROOT, value) for key, value in values.items()
                                 if key in ("output_file", "report_file", "baseline_output_file"))
        if output in protected:
            raise AnsweringError("Keep the answering preview separate from context and earlier reports.")
        if output.exists():
            previous = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(previous, dict) or previous.get("artifact_type") != "answering_preview":
                raise AnsweringError("The output already contains a different artifact; choose a separate preview file.")
        prompt_path = (PROJECT_ROOT / options["system_prompt_file"]).resolve()
        if not prompt_path.is_relative_to((PROJECT_ROOT / "prompts").resolve()) or prompt_path.suffix != ".md":
            raise AnsweringError("Keep the answering instructions in a Markdown file inside prompts/.")
        instructions = prompt_path.read_text(encoding="utf-8")
        saved = json.loads(input_path.read_text(encoding="utf-8"))
        pack = revalidate_pack(saved, prepare_upload(PROJECT_ROOT, settings), settings)
        preview = build_prompt(pack, instructions, settings)
        preview.update({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                        "source_context_file": input_path.relative_to(PROJECT_ROOT).as_posix()})
        save_chunk_export(preview, output)
        print("Answering instructions: OFFLINE PREVIEW")
        print(f"Question: {pack['question']}")
        print(f"Allowed source IDs: {', '.join(pack['source_registry']) or 'none'}")
        print(f"Prepared message characters: {preview['message_characters']}. Model tokens: not measured.")
        if preview["empty_context_fallback"] is not None:
            print("No evidence: use the fixed insufficient-evidence message without requesting a model draft.")
        print("Draft checks cover format and source IDs. Claim support and action claims still require evaluation.")
        print("No model call, no generated answer and no external request charge.")
        print(f"Saved: {output.relative_to(PROJECT_ROOT).as_posix()}")
        if args.show:
            for message in preview["messages"]:
                print(f"\n{message['role'].upper()}\n{message['content']}")
        return 0
    except (AnsweringError, ContextError, IngestionError) as error:
        print(f"Answering preparation stopped: {error}")
    except (ValueError, KeyError, TypeError, OSError):
        print("Answering preparation stopped: check the context, instructions, corpus and settings files.")
    print("No successful current preview is claimed. Earlier output may remain; check its timestamp.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
