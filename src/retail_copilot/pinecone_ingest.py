"""Preview or upload a small, validated corpus using Pinecone's current SDK."""

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import time

from dotenv import set_key
from pinecone import DenseVectorField, ManagedDeployment, NotFoundError, Pinecone, RetryConfig

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.ollama_embeddings import installed_model_digest
from retail_copilot.pinecone_records import to_pinecone_record
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path, reusable_result
from retail_copilot.readiness import read_credential


class IngestionError(Exception):
    """A safe, user-facing message, without provider response bodies or credentials."""


def prepare_upload(root: Path, settings: dict) -> dict:
    """Recheck the entire saved snapshot against the current approved source files."""
    embedding = settings["embedding"]
    retrieval = settings["retrieval"]
    if embedding["provider"] != "ollama" or retrieval["provider"] != "pinecone":
        raise IngestionError("This ingestion lesson requires local Ollama embeddings and Pinecone.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,44}", retrieval["index_name"]):
        raise IngestionError("Choose an index name with 1-45 lowercase letters, numbers or hyphens.")
    namespace = retrieval["namespace"]
    if not isinstance(namespace, str) or not namespace or not namespace.isascii() or len(namespace) > 512 or "\0" in namespace:
        raise IngestionError("Choose a non-empty ASCII namespace of at most 512 characters.")
    if (retrieval["cloud"], retrieval["region"], retrieval["metric"]) != ("aws", "us-east-1", "cosine"):
        raise IngestionError("This Starter lesson uses AWS us-east-1 with cosine similarity.")
    field = retrieval["vector_field"]
    if not isinstance(field, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", field):
        raise IngestionError("Choose a lowercase vector field name, such as embedding.")
    strategy = settings["chunk_preparation"]["strategy"]
    if strategy != "section-v1":
        raise IngestionError("Prepare section-v1 chunks before uploading.")
    path = generated_json_path(root, settings["embedding_preparation"]["output_file"])
    saved = json.loads(path.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(settings["demo"]["as_of_date"])
    for key, value in {
        "schema_version": 1, "provider": embedding["provider"], "model": embedding["model"],
        "dimensions": embedding["dimensions"], "document_template": embedding["document_template"],
        "as_of_date": as_of.isoformat(), "strategy": strategy,
    }.items():
        if saved.get(key) != value:
            raise IngestionError("The saved corpus is out of date. Run prepare_embeddings again.")
    digest = saved.get("model_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise IngestionError("The corpus needs the downloaded model's SHA-256 digest.")
    policies = load_documents(root / settings["demo"]["knowledge_directory"])
    eligible = approved_documents(policies, as_of)
    chunks = {chunk.id: chunk for policy in eligible for chunk in section_chunks(policy)}
    records = saved.get("records")
    if not isinstance(records, list) or not records or saved.get("record_count") != len(records):
        raise IngestionError("The saved corpus is empty or its count is inconsistent.")
    ids = [record.get("chunk_id") for record in records if isinstance(record, dict)]
    if len(ids) != len(records) or len(set(ids)) != len(ids) or set(ids) != set(chunks):
        raise IngestionError("Saved chunk IDs do not match the current eligible policies. Prepare embeddings again.")
    documents = []
    storage_bytes = 0
    for record in sorted(records, key=lambda item: item["chunk_id"]):
        chunk = chunks[record["chunk_id"]]
        if record.get("metadata") != chunk.metadata or record.get("as_of_date") != as_of.isoformat():
            raise IngestionError("Saved source metadata has changed. Prepare embeddings again.")
        if reusable_result(record, chunk, embedding, digest) is None:
            raise IngestionError("A saved vector or its exact input no longer matches. Prepare embeddings again.")
        vector = to_pinecone_record(record, embedding)
        if not vector["id"].isascii() or len(vector["id"]) > 512:
            raise IngestionError("Pinecone record IDs must be ASCII and at most 512 characters.")
        if any(key in vector["metadata"] for key in (field, "_id", "_score")):
            raise IngestionError("A metadata field conflicts with a reserved upload field.")
        # SDK 10 uses named fields: metadata remains attached, but is not nested.
        documents.append({"_id": vector["id"], field: vector["values"], **vector["metadata"]})
        storage_bytes += 4 * embedding["dimensions"] + len(vector["id"].encode("utf-8"))
        storage_bytes += len(json.dumps(vector["metadata"], ensure_ascii=False).encode("utf-8"))
    encoded = json.dumps({"documents": documents}, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(documents) > 1000 or len(encoded) > 1_900_000:
        raise IngestionError("This small-corpus command supports one request up to 1,000 records and 1.9 MB.")
    return {
        "documents": documents, "record_count": len(documents), "model_digest": digest,
        "corpus_sha256": hashlib.sha256(encoded).hexdigest(),
        "request_json_bytes": len(encoded), "estimated_record_bytes": storage_bytes,
        "eligible_documents": len(eligible), "as_of_date": as_of.isoformat(),
    }


def index_tags(prepared: dict) -> dict:
    return {"project": "retail-copilot-week2", "model_digest": prepared["model_digest"],
            "corpus_sha256": prepared["corpus_sha256"]}


def check_index(info, settings: dict, prepared: dict) -> None:
    retrieval = settings["retrieval"]
    field = info.schema.fields.get(retrieval["vector_field"])
    if (not isinstance(field, DenseVectorField) or field.dimension != settings["embedding"]["dimensions"]
            or field.metric != retrieval["metric"]):
        raise IngestionError("The existing index does not match this embedding model and similarity setting.")
    deployment = info.deployment
    if (not isinstance(deployment, ManagedDeployment) or deployment.cloud != retrieval["cloud"]
            or deployment.region != retrieval["region"]):
        raise IngestionError("The existing index is not in the configured Starter region.")
    if any((info.tags or {}).get(key) != value for key, value in index_tags(prepared).items()):
        raise IngestionError("The index belongs to another corpus or model version. Review it before changing data.")
    if not info.status.ready or not info.host:
        raise IngestionError("Pinecone is still preparing the index. Wait, then rerun this command.")


def namespace_count(index, namespace: str) -> int:
    try:
        return int(index.describe_namespace(name=namespace).record_count)
    except NotFoundError:
        return 0


def records_match(fetched: dict, documents: list[dict], field: str) -> bool:
    if set(fetched) != {doc["_id"] for doc in documents}:
        return False
    for expected in documents:
        actual = fetched[expected["_id"]].to_dict()
        values = actual.pop(field, None)
        if {key: value for key, value in expected.items() if key != field} != actual:
            return False
        if not isinstance(values, list) or len(values) != len(expected[field]):
            return False
        # Pinecone stores float32; JSON round trips need a small numerical tolerance.
        if not all(type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7)
                   for a, b in zip(values, expected[field])):
            return False
    return True


def upload_and_verify(client, prepared: dict, settings: dict, *, sleep=time.sleep) -> dict:
    """Only write an empty owned namespace; an identical repeat is read-only."""
    retrieval = settings["retrieval"]
    options = settings["pinecone_ingestion"]
    name, namespace = retrieval["index_name"], retrieval["namespace"]
    documents = prepared["documents"]
    ids = [doc["_id"] for doc in documents]
    timeout = options["request_timeout_seconds"]
    created = not client.indexes.exists(name)
    if created:
        info = client.indexes.create(
            name=name,
            schema={"fields": {retrieval["vector_field"]: {
                "type": "dense_vector", "dimension": settings["embedding"]["dimensions"],
                "metric": retrieval["metric"],
            }}},
            deployment={"deployment_type": "managed", "cloud": retrieval["cloud"], "region": retrieval["region"]},
            tags=index_tags(prepared), timeout=30,
        )
    else:
        info = client.indexes.describe(name)
    check_index(info, settings, prepared)
    reads = []
    written = 0
    with client.index(host=info.host) as index:
        count = namespace_count(index, namespace)
        if count not in (0, len(documents)):
            raise IngestionError("The namespace contains an unexpected record count. No upload was attempted.")
        if not created:
            try:
                existing = index.documents.fetch(namespace=namespace, ids=ids, timeout=timeout)
            except NotFoundError:
                existing = None
            if existing is not None:
                reads.append(existing.usage.read_units if existing.usage else None)
                if existing.documents and not records_match(existing.documents, documents, retrieval["vector_field"]):
                    raise IngestionError("Existing records differ or are incomplete. No records were overwritten.")
                if count and not existing.documents:
                    raise IngestionError("The namespace contains other records. No upload was attempted.")
                if existing.documents:
                    count = len(documents)  # Fetch is complete even if the count has not caught up yet.
        if count == 0:
            response = index.documents.upsert(namespace=namespace, documents=documents, timeout=timeout)
            written = response.upserted_count
            if written != len(documents):
                raise IngestionError("Pinecone did not acknowledge every record. Inspect the namespace before retrying.")
        for attempt in range(options["verification_attempts"]):
            count = namespace_count(index, namespace)
            if count == len(documents):
                fetched = index.documents.fetch(namespace=namespace, ids=ids, timeout=timeout)
                reads.append(fetched.usage.read_units if fetched.usage else None)
                if records_match(fetched.documents, documents, retrieval["vector_field"]):
                    return {
                        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
                        "index_name": name, "index_host": info.host, "namespace": namespace,
                        "index_created": created, "records_written": written, "records_verified": count,
                        "provider": settings["embedding"]["provider"], "model": settings["embedding"]["model"],
                        "dimensions": settings["embedding"]["dimensions"], "model_digest": prepared["model_digest"],
                        "corpus_sha256": prepared["corpus_sha256"], "as_of_date": prepared["as_of_date"],
                        "reported_fetch_read_units": reads,
                        "estimated_record_bytes": prepared["estimated_record_bytes"],
                        "retrieval_quality_tested": False,
                    }
            if attempt + 1 < options["verification_attempts"]:
                sleep(options["verification_interval_seconds"])
    raise IngestionError("Pinecone accepted the upload, but read-back verification did not finish. Do not assume success.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true", help="Create/connect the configured index and upload the validated corpus.")
    args = parser.parse_args(argv)
    # Provider logs must never print credentials or response bodies in this lesson.
    logging.getLogger("pinecone").setLevel(logging.CRITICAL)
    try:
        settings = load_settings()
        prepared = prepare_upload(PROJECT_ROOT, settings)
        retrieval = settings["retrieval"]
        report_path = generated_json_path(PROJECT_ROOT, settings["pinecone_ingestion"]["report_file"])
        if report_path == generated_json_path(PROJECT_ROOT, settings["embedding_preparation"]["output_file"]):
            raise IngestionError("Keep the indexing report separate from the embedding corpus.")
        print(f"Index: {retrieval['index_name']} | Namespace: {retrieval['namespace']}", flush=True)
        print(f"Validated {prepared['record_count']} records from {prepared['eligible_documents']} eligible policies.", flush=True)
        print(f"Dimensions: {settings['embedding']['dimensions']} | Metric: {retrieval['metric']} | Region: {retrieval['region']}")
        print(f"Estimated record data: {prepared['estimated_record_bytes']} bytes; JSON request: {prepared['request_json_bytes']} bytes.")
        if not args.upload:
            print("PREVIEW ONLY. No Pinecone calls or changes. Add --upload for the explained indexing step.")
            return 0
        key = read_credential("PINECONE_API_KEY", PROJECT_ROOT)
        if not key:
            raise IngestionError("Save PINECONE_API_KEY in Week2 Project/.env first; never paste it in chat.")
        if installed_model_digest(settings["embedding"]) != prepared["model_digest"]:
            raise IngestionError("The installed embedding model changed. Prepare embeddings again before indexing.")
        print("Uploading fictional policy data to Pinecone; this uses your account's write, storage and read allowances.", flush=True)
        with Pinecone(api_key=key, timeout=settings["pinecone_ingestion"]["request_timeout_seconds"],
                      retry_config=RetryConfig(max_retries=0)) as client:
            report = upload_and_verify(client, prepared, settings)
        save_chunk_export(report, report_path)
        set_key(str(PROJECT_ROOT / ".env"), "PINECONE_INDEX_HOST", report["index_host"])
        print(f"Verified {report['records_verified']} records: IDs, text, source fields and vector values match.")
        print(f"Records written this run: {report['records_written']}; index created: {report['index_created']}.")
        print(f"Pinecone-reported fetch read units: {report['reported_fetch_read_units']}")
        print("Index host saved privately in .env. Report saved in data/processed/.")
        print("Storage is verified. Semantic retrieval quality has not been tested yet.")
        return 0
    except IngestionError as error:
        print(f"Indexing stopped: {error}")
    except (OSError, ValueError, KeyError, TypeError):
        print("Indexing stopped: check configuration, approved policies and the prepared embedding file.")
    except Exception:
        print("Pinecone could not complete this operation. Check connection, permissions and account limits.")
    print("No success is claimed. A remote index or records may exist; inspect them before another upload.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
