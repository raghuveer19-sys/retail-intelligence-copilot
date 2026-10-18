"""Prepare a complete local vector snapshot, reusing only matching saved results."""

from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path

from langchain_core.documents import Document

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.ollama_embeddings import document_input, embed_local_chunk, installed_model_digest
from retail_copilot.pinecone_records import to_pinecone_record
from retail_copilot.prepare_chunks import save_chunk_export


def generated_json_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to((root / "data" / "processed").resolve()) or path.suffix != ".json":
        raise ValueError("Embedding output and cache files must be JSON inside data/processed/.")
    return path


def load_cached_results(paths: list[Path]) -> dict[str, dict]:
    """Read generated files only; earlier paths take priority over the example fallback."""
    cached = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError("A saved embedding file could not be read; inspect it before preparing again.") from None
        if not isinstance(saved, dict):
            raise ValueError("A saved embedding file must contain a result or corpus object.")
        records = saved.get("records", [saved])
        if not isinstance(records, list):
            raise ValueError("A saved corpus must contain a records list.")
        seen = set()
        for record in records:
            identifier = record.get("chunk_id") if isinstance(record, dict) else None
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise ValueError("Saved embedding records need unique, non-empty chunk IDs.")
            seen.add(identifier)
            cached.setdefault(identifier, record)
    return cached


def reusable_result(cached: dict | None, chunk: Document, embedding: dict, digest: str) -> dict | None:
    """Match model version and exact input; refresh metadata from today's validated source."""
    if not isinstance(cached, dict):
        return None
    expected = {
        "provider": embedding["provider"], "model": embedding["model"],
        "dimensions": embedding["dimensions"], "model_digest": digest,
        "chunk_id": chunk.id, "text": chunk.page_content,
        "embedding_input": document_input(chunk, embedding),
        "document_template": embedding["document_template"],
    }
    if any(cached.get(key) != value for key, value in expected.items()):
        return None
    candidate = deepcopy(cached)
    candidate["metadata"] = deepcopy(chunk.metadata)
    try:
        to_pinecone_record(candidate, embedding)
        tokens = candidate["usage"]["prompt_tokens"]
        if type(tokens) is not int or not 0 < tokens <= embedding["max_input_tokens"]:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return candidate


def build_embedding_export(
    documents: list[Document], as_of: date, strategy: str, embedding: dict,
    cached: dict[str, dict], progress=None,
) -> dict:
    """Embed current eligible chunks in a sequential loop, never uploading anything."""
    if strategy != "section-v1":
        raise ValueError("Corpus embeddings require the section-v1 strategy.")
    eligible = approved_documents(documents, as_of)
    chunks = sorted([chunk for doc in eligible for chunk in section_chunks(doc)], key=lambda item: item.id or "")
    if not chunks or any(not chunk.id for chunk in chunks) or len({c.id for c in chunks}) != len(chunks):
        raise ValueError("Select at least one eligible chunk with a unique, non-empty ID.")
    digest = installed_model_digest(embedding)
    records = []
    pending = []
    for chunk in chunks:
        result = reusable_result(cached.get(chunk.id), chunk, embedding, digest)
        if result is None:
            pending.append(chunk)
        else:
            result["as_of_date"] = as_of.isoformat()
            records.append(result)
    reused = len(records)
    new_tokens = 0
    for index, chunk in enumerate(pending):
        if progress:
            progress(f"Embedding {index + 1}/{len(pending)}: {chunk.id}")
        # Keep the model warm between inputs; release it after the final one.
        result = embed_local_chunk(chunk, embedding, keep_alive="0s" if index == len(pending) - 1 else "5m")
        if result["model_digest"] != digest:
            raise ValueError("The installed model changed during this run; no corpus was accepted.")
        result["as_of_date"] = as_of.isoformat()
        new_tokens += result["usage"]["prompt_tokens"]
        records.append(result)
    # Recheck cached and newly produced records before the caller saves any output.
    for result in records:
        to_pinecone_record(result, embedding)
    eligible_ids = {doc.id for doc in eligible}
    return {
        "schema_version": 1, "provider": embedding["provider"], "model": embedding["model"],
        "model_digest": digest, "dimensions": embedding["dimensions"],
        "document_template": embedding["document_template"],
        "as_of_date": as_of.isoformat(), "strategy": strategy,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "loaded_documents": len(documents), "eligible_documents": len(eligible),
        "excluded_document_ids": sorted(doc.id for doc in documents if doc.id not in eligible_ids),
        "record_count": len(records), "reused_records": reused, "new_records": len(pending),
        "new_input_tokens": new_tokens,
        "corpus_input_tokens": sum(record["usage"]["prompt_tokens"] for record in records),
        "embedding_api_charge_usd": "0",
        "records": sorted(records, key=lambda item: item["chunk_id"]),
    }


def main() -> int:
    try:
        settings = load_settings()
        output = generated_json_path(PROJECT_ROOT, settings["embedding_preparation"]["output_file"])
        example = generated_json_path(PROJECT_ROOT, settings["ollama_example"]["output_file"])
        if output == example:
            raise ValueError("The corpus output must be separate from the one-chunk example.")
        cached = load_cached_results([output, example])
        demo = settings["demo"]
        documents = load_documents(PROJECT_ROOT / demo["knowledge_directory"])
        print("Preparing real embeddings locally; no OpenAI or Pinecone calls.", flush=True)
        result = build_embedding_export(
            documents, date.fromisoformat(demo["as_of_date"]),
            settings["chunk_preparation"]["strategy"], settings["embedding"], cached,
            progress=lambda message: print(message, flush=True),
        )
        save_chunk_export(result, output)
        print(f"Saved {result['record_count']} real embedding records from {result['eligible_documents']} eligible policies.")
        print(f"New: {result['new_records']} | Reused: {result['reused_records']} | Dimensions: {result['dimensions']}")
        print(f"Reported input tokens processed this run: {result['new_input_tokens']}; corpus total including reused inputs: {result['corpus_input_tokens']}.")
        print(f"Excluded: {', '.join(result['excluded_document_ids']) or 'none'}")
        print(f"Output: {settings['embedding_preparation']['output_file']}")
        print("Local format checks passed. Pinecone upload and retrieval quality remain untested.")
        return 0
    except (KeyError, TypeError):
        print("Embedding preparation could not finish: check the configured preparation and model fields.")
    except (OSError, ValueError) as error:
        print(f"Embedding preparation could not finish: {error}")
    print("No complete replacement was saved. Do not treat an earlier snapshot as this run's result.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
