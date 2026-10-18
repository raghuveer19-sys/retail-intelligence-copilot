"""Assemble whole supplied policy passages after a model selects source IDs.

The caller revalidates the evidence pack before calling this function. Model
prose is discarded; selection expands only within that supplied pack and only
from references in seed source text. Seeds are model-cited passages, or exact
policy matches for a narrow overview request when an insufficient draft is empty.
No retrieval is performed.
"""

from copy import deepcopy
import json
import re

from retail_copilot.answering import AnsweringError, unique_json_object, validate_draft
from retail_copilot.policy_lookup import policy_ids


class SourceGuidanceError(AnsweringError):
    """The supplied evidence cannot be assembled safely into whole passages."""


_METADATA_FIELDS = (
    "document_id", "policy_id", "document_title", "version", "section_id",
    "section_heading", "source_file",
)


def _overview_policy_id(question: str) -> str | None:
    """Recognise a narrow request for one named policy's contents, not any mention."""
    text = re.sub(r"[?.!]$", "", question.strip()).strip()
    text = re.sub(r"^please\s+", "", text, flags=re.I)
    text = re.sub(r",?\s+please$", "", text, flags=re.I)
    match = re.fullmatch(
        r"what\s+does\s+(?:policy\s+)?(.+?)\s+say|"
        r"(?:show|explain|summarise|summarize)\s+(?:me\s+)?(?:policy\s+)?(.+)", text, re.I)
    if match is None:
        return None
    candidate = (match.group(1) or match.group(2)).strip()
    identifiers = policy_ids(candidate)
    return identifiers[0] if len(identifiers) == 1 and candidate.upper() == identifiers[0] else None


def _sources(pack: dict, settings: dict) -> tuple[list[dict], int]:
    """Check supplied boundaries and registry agreement, without loading a corpus."""
    try:
        options = settings["context"]
        maximum, characters = options["max_sources"], options["max_characters"]
        if type(maximum) is not int or not 1 <= maximum <= 20:
            raise SourceGuidanceError("The evidence source limit is invalid.")
        if type(characters) is not int or not 1 <= characters <= 100000:
            raise SourceGuidanceError("The evidence character limit is invalid.")
        if not isinstance(pack, dict) or pack.get("artifact_type") != "context_preview":
            raise SourceGuidanceError("Use a revalidated evidence pack for source guidance.")
        text, registry = pack["context_text"], pack["source_registry"]
        if not isinstance(text, str) or len(text) > characters or not isinstance(registry, dict):
            raise SourceGuidanceError("The evidence pack is invalid or exceeds its whole-passage limit.")
        evidence = json.loads(text, object_pairs_hook=unique_json_object)
        if (not isinstance(evidence, dict) or evidence.get("question") != pack["question"]
                or evidence.get("policy_date") != pack["as_of_date"]):
            raise SourceGuidanceError("The evidence does not match the current question and policy date.")
        sources = evidence.get("sources")
        if not isinstance(sources, list) or len(sources) > maximum:
            raise SourceGuidanceError("The evidence exceeds the source limit; no passages were cut.")
        labels = [f"S{index + 1}" for index in range(len(sources))]
        if set(registry) != set(labels):
            raise SourceGuidanceError("The evidence sources and source registry disagree.")
        chunks = set()
        for label, source in zip(labels, sources, strict=True):
            if not isinstance(source, dict) or source.get("source_id") != label:
                raise SourceGuidanceError("Keep the evidence source IDs in their original order.")
            entry = registry[label]
            if not isinstance(entry, dict) or not isinstance(entry.get("metadata"), dict):
                raise SourceGuidanceError("Each evidence passage needs its original source metadata.")
            chunk = source.get("chunk_id")
            if (not isinstance(chunk, str) or not chunk or chunk in chunks
                    or chunk != entry.get("chunk_id")):
                raise SourceGuidanceError("An evidence passage has a duplicate or inconsistent chunk ID.")
            chunks.add(chunk)
            for field in _METADATA_FIELDS:
                if (not isinstance(source.get(field), str) or not source[field].strip()
                        or source[field] != entry["metadata"].get(field)):
                    raise SourceGuidanceError("A passage does not match its source registry metadata.")
            if entry["metadata"].get("status") != "approved":
                raise SourceGuidanceError("Source guidance requires approved evidence passages.")
            if not isinstance(source.get("text"), str) or not source["text"].strip():
                raise SourceGuidanceError("Every evidence passage needs its complete original text.")
        return sources, maximum
    except (KeyError, TypeError, json.JSONDecodeError):
        raise SourceGuidanceError("The supplied evidence or source guidance settings are incomplete.") from None


def assemble_source_guidance(draft: dict, pack: dict, settings: dict) -> dict:
    """Return ``draft`` and ``trace`` using exact whole paragraphs from this pack.

    All supplied sections of seed document IDs are included. Supplied sections
    of policies named in seed text are also included. An empty insufficient
    draft can use exact policy matches only for a clear policy-overview request;
    its status is preserved. Newly added sections never initiate expansion.
    This guarantees text provenance, not answer relevance or completeness.
    """
    sources, maximum = _sources(pack, settings)
    original = validate_draft(json.dumps(draft, ensure_ascii=False), pack, settings)
    cited = {label for claim in original["claims"] for label in claim["source_ids"]}
    originals = [source for source in sources if source["source_id"] in cited]
    seeds = originals
    requested = None
    if not originals and original["status"] == "insufficient_evidence":
        requested = _overview_policy_id(pack["question"])
        if requested is not None:
            seeds = [source for source in sources if source["policy_id"].upper() == requested]
    documents = {source["document_id"] for source in seeds}
    references = {policy for source in seeds for policy in policy_ids(source["text"])}
    selected = [source for source in sources if source["document_id"] in documents
                or source["policy_id"].upper() in references]
    final = deepcopy(original)
    if seeds:
        final["claims"] = [{"text": source["text"], "source_ids": [source["source_id"]]}
                           for source in selected]
        # Expansion may contain more paragraphs than the model's claim limit.
        # Keep the configured text bounds: fail closed instead of cutting text.
        expanded_settings = deepcopy(settings)
        expanded_settings["answering"]["max_claims"] = maximum
        final = validate_draft(json.dumps(final, ensure_ascii=False), pack, expanded_settings)
    original_ids = [source["source_id"] for source in originals]
    selected_ids = [source["source_id"] for source in selected]
    return {
        "draft": final,
        "trace": {
            "mode": "source_passages", "applied": bool(seeds),
            "original_selected_source_ids": original_ids,
            "selection_seed_source_ids": [source["source_id"] for source in seeds],
            "selection_reason": "model_source_ids" if originals else (
                "explicit_policy_identifier" if requested is not None else "no_selected_sources"),
            "requested_policy_ids": [requested] if requested is not None else [],
            "requested_policy_ids_without_passages": [requested] if requested is not None and not seeds else [],
            "added_source_ids": [label for label in selected_ids if label not in cited],
            "selected_source_ids": selected_ids,
            "referenced_policy_ids": sorted(references),
            "referenced_policy_ids_without_passages": sorted(
                references - {source["policy_id"].upper() for source in sources}),
            "exact_source_text_verified": True,
            "semantic_claim_support_checked": False, "relevance_checked": False,
        },
    }
