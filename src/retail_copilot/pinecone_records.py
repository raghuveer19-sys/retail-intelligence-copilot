"""Prepare one Pinecone vector record locally; no SDK, credentials or network calls."""

from copy import deepcopy
import json
import math


# A conservative local ceiling below Pinecone's documented 40 KB metadata limit.
MAX_METADATA_BYTES = 40_000
SOURCE_FIELDS = (
    "document_id", "document_title", "policy_id", "version",
    "section_id", "section_heading", "source_file",
)


def to_pinecone_record(result: dict, embedding: dict) -> dict:
    """Map a validated embedding result to id/values/metadata without uploading.

    The caller must select eligible sources before embedding and recheck freshness
    before a future upload. This format check cannot prove vector meaning, source
    authenticity, current eligibility or compatibility with an actual remote index.
    """
    if not isinstance(result, dict) or not isinstance(embedding, dict):
        raise ValueError("Supply an embedding result and its model configuration.")
    dimensions = embedding.get("dimensions")
    if type(dimensions) is not int or dimensions <= 0:
        raise ValueError("Configured dimensions must be a positive whole number.")
    for field in ("provider", "model"):
        expected = embedding.get(field)
        if not isinstance(expected, str) or not expected.strip() or result.get(field) != expected:
            raise ValueError("The embedding provider and model must match the configuration.")
    if type(result.get("dimensions")) is not int or result["dimensions"] != dimensions:
        raise ValueError("The result's dimensions must match the configuration.")

    chunk_id = result.get("chunk_id")
    text = result.get("text")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        raise ValueError("A non-empty chunk ID is required for source tracking.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Keep the original passage text with its vector.")
    vector = result.get("vector")
    if not isinstance(vector, list) or len(vector) != dimensions:
        raise ValueError("The vector must contain the configured number of values.")
    try:
        usable = all(type(value) in (int, float) and math.isfinite(value) for value in vector)
    except OverflowError:
        usable = False
    if not usable or not any(value != 0 for value in vector):
        raise ValueError("The vector must contain finite numbers and cannot be all zeros.")

    source = result.get("metadata")
    if not isinstance(source, dict):
        raise ValueError("Source metadata is required alongside the passage.")
    for field in SOURCE_FIELDS:
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise ValueError(f"Source metadata needs a non-empty {field} for traceability.")
    if "text" in source:
        raise ValueError("Source metadata already uses text; resolve this before mapping the passage.")
    if "chunk_id" in source and source["chunk_id"] != chunk_id:
        raise ValueError("Metadata chunk_id must agree with the record's chunk ID.")

    metadata = {}
    for key, value in source.items():
        if not isinstance(key, str) or not key or key.startswith("$"):
            raise ValueError("Metadata keys must be non-empty strings without a leading $.")
        if value is None:
            continue  # Pinecone does not accept null; e.g. no specified effective_to.
        if isinstance(value, str) or type(value) is bool:
            pass
        elif type(value) in (int, float):
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError("Metadata numbers must be finite.")
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            pass
        else:
            raise ValueError("Metadata must be flat: use strings, numbers, booleans or lists of strings.")
        metadata[key] = deepcopy(value)
    metadata["text"] = text
    encoded = json.dumps(metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise ValueError("Text and metadata exceed our 40,000-byte limit; review the chunk, do not truncate it.")
    return {"id": chunk_id, "values": list(vector), "metadata": metadata}
