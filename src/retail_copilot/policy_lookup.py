"""Bounded, one-step lookup of explicitly named approved policies."""

from copy import deepcopy
import math
import re
import time

from langchain_core.documents import Document


class PolicyLookupError(ValueError):
    """A safe explanation of a failed or unsupported lookup."""


# Capture complete IDs, including unsupported version suffixes; never match a prefix.
POLICY_ID = re.compile(r"(?<![A-Za-z0-9_-])([A-Z]{2,12}-\d{4,}(?:-v\d+)?)(?![A-Za-z0-9_-])", re.IGNORECASE)


def policy_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(1).upper() for match in POLICY_ID.finditer(text)))


def plan_lookup(result: dict, prepared: dict, options: dict, vector_field: str) -> dict:
    """Choose missing sections from explicit question IDs, otherwise original hit references."""
    max_policies, max_chunks = options["max_policies"], options["max_added_chunks"]
    if type(max_policies) is not int or not 1 <= max_policies <= 5:
        raise PolicyLookupError("Policy lookup needs max_policies between 1 and 5.")
    if type(max_chunks) is not int or not 1 <= max_chunks <= 12:
        raise PolicyLookupError("Policy lookup needs max_added_chunks between 1 and 12.")
    if "policy_lookup" in result:
        raise PolicyLookupError("Follow policy references only once, starting from the original search.")
    records = {doc["_id"]: {key: value for key, value in doc.items() if key != vector_field}
               for doc in prepared["documents"]}
    by_policy = {}
    for identifier, doc in records.items():
        by_policy.setdefault(doc["policy_id"], []).append(identifier)
    existing = set()
    for hit in result["matches"]:
        identifier = hit["chunk_id"]
        actual = {**hit["metadata"], "_id": identifier, "text": hit["text"]}
        if identifier in existing or records.get(identifier) != actual:
            raise PolicyLookupError("Reference lookup requires unchanged, validated source passages.")
        existing.add(identifier)
    requested = policy_ids(result["question"])
    origins = {}
    if requested:
        mode = "question_policy_ids"
        for policy in requested:
            origins[policy] = [{"kind": "question_policy_id", "source_chunk_id": None}]
    else:
        mode = "references_in_semantic_passages"
        for hit in result["matches"]:
            for policy in policy_ids(hit["text"]):
                origins.setdefault(policy, []).append({"kind": "source_policy_reference", "source_chunk_id": hit["chunk_id"]})
    unknown, unsupported, skipped, selected, identifiers = [], [], [], [], []
    for policy in origins:
        if re.search(r"-V\d+$", policy):
            unsupported.append(policy)
            continue
        if policy not in by_policy:
            unknown.append(policy)
            continue
        missing = sorted(set(by_policy[policy]) - existing)
        # Keep a policy's missing sections together; do not silently truncate them.
        if len(selected) >= max_policies or len(identifiers) + len(missing) > max_chunks:
            skipped.append(policy)
            continue
        selected.append(policy)
        identifiers.extend(missing)
    return {
        "mode": mode, "policy_ids": selected, "origins": {key: origins[key] for key in selected},
        "requested_chunk_ids": identifiers, "unknown_policy_ids": unknown,
        "unsupported_version_ids": unsupported, "skipped_policy_ids": skipped,
    }


def follow_policy_references(index, result: dict, prepared: dict, settings: dict) -> dict:
    """Fetch missing records once; preserve original scores and never invent new scores."""
    started = time.perf_counter()
    retrieval = settings["retrieval"]
    plan = plan_lookup(result, prepared, settings["policy_lookup"], retrieval["vector_field"])
    updated = deepcopy(result)
    updated["retrieval_mode"] = "semantic_with_policy_lookup"
    updated["semantic_match_count"] = len(result["matches"])
    for rank, hit in enumerate(updated["matches"], start=1):
        hit["retrieval_method"] = "semantic"
        hit["semantic_rank"] = rank
        hit["lookup_origins"] = deepcopy(plan["origins"].get(hit["metadata"]["policy_id"], []))
    identifiers = plan["requested_chunk_ids"]
    fetch_units = 0
    fetch_seconds = 0.0
    if identifiers:
        records = {doc["_id"]: {key: value for key, value in doc.items() if key != retrieval["vector_field"]}
                   for doc in prepared["documents"] if doc["_id"] in identifiers}
        fields = sorted({key for doc in records.values() for key in doc if key != "_id"})
        fetch_started = time.perf_counter()
        response = index.documents.fetch(
            namespace=retrieval["namespace"], ids=identifiers, include_fields=fields,
            timeout=retrieval["request_timeout_seconds"],
        )
        fetch_seconds = time.perf_counter() - fetch_started
        if response.namespace != retrieval["namespace"] or set(response.documents) != set(identifiers):
            raise PolicyLookupError("Pinecone did not return every requested policy section from the expected namespace.")
        for identifier in identifiers:
            fields = response.documents[identifier].to_dict()
            if fields != records[identifier]:
                raise PolicyLookupError("A fetched policy's text or metadata differs from the approved local source.")
            fields.pop("_id")
            doc = Document(id=identifier, page_content=fields.pop("text"), metadata=fields)
            updated["matches"].append({
                "chunk_id": doc.id, "text": doc.page_content, "metadata": doc.metadata,
                "score": None, "semantic_rank": None, "retrieval_method": "policy_lookup",
                "lookup_origins": deepcopy(plan["origins"][doc.metadata["policy_id"]]),
            })
        fetch_units = response.usage.read_units if response.usage is not None else None
        if fetch_units is not None and (type(fetch_units) not in (int, float) or not math.isfinite(fetch_units) or fetch_units < 0):
            raise PolicyLookupError("Pinecone returned invalid policy-fetch usage information.")
    elapsed = time.perf_counter() - started
    updated["policy_lookup"] = {
        **plan, "added_chunks": len(identifiers), "fetch_read_units": fetch_units,
        "fetch_seconds": fetch_seconds, "total_seconds": elapsed,
        "lookup_complete_within_scope": not (plan["unknown_policy_ids"] or plan["unsupported_version_ids"] or plan["skipped_policy_ids"]),
    }
    search_units = result["pinecone_read_units"]
    updated["search_read_units"] = search_units
    updated["pinecone_read_units"] = search_units + fetch_units if search_units is not None and fetch_units is not None else None
    updated["total_seconds"] += elapsed
    updated["evidence_status"] = "candidates_require_review" if updated["matches"] else "no_candidates"
    return updated
