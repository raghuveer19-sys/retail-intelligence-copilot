"""Inspect semantic retrieval of fictional policies; no answer generation or writes to Pinecone."""

import argparse
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import time

from langchain_core.documents import Document
from pinecone import DenseVectorQuery, Pinecone, RetryConfig

from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.ollama_embeddings import embed_local_query, query_input
from retail_copilot.pinecone_ingest import IngestionError, check_index, prepare_upload
from retail_copilot.policy_lookup import PolicyLookupError, follow_policy_references
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.prepare_embeddings import generated_json_path
from retail_copilot.readiness import read_credential


class RetrievalError(Exception):
    """A safe explanation; provider errors and credentials are never echoed."""


def retrieval_options(settings: dict) -> tuple[int, float]:
    top_k = settings["retrieval"]["top_k"]
    timeout = settings["retrieval"]["request_timeout_seconds"]
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise RetrievalError("For this small teaching corpus, set top_k to a whole number from 1 to 10.")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise RetrievalError("Set the retrieval request timeout between 0 and 120 seconds.")
    return top_k, timeout


def validate_matches(response, prepared: dict, settings: dict) -> list[tuple[Document, float]]:
    """Use returned evidence only after checking its identity and current approved source."""
    retrieval = settings["retrieval"]
    expected = {doc["_id"]: {key: value for key, value in doc.items() if key != retrieval["vector_field"]}
                for doc in prepared["documents"]}
    if response.namespace != retrieval["namespace"] or len(response.matches) > retrieval["top_k"]:
        raise RetrievalError("Pinecone returned an unexpected namespace or result count.")
    seen = set()
    matches = []
    for hit in response.matches:
        fields = hit.to_dict()
        score = fields.pop("_score", None)
        identifier = fields.get("_id")
        if not isinstance(identifier, str) or identifier in seen or identifier not in expected:
            raise RetrievalError("A returned passage has an unknown, excluded or repeated source ID.")
        if fields != expected[identifier]:
            raise RetrievalError("Returned text or source metadata differs from the approved local corpus. Review indexing.")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise RetrievalError("Pinecone returned an invalid similarity score.")
        seen.add(identifier)
        fields.pop("_id")
        text = fields.pop("text")
        matches.append((Document(id=identifier, page_content=text, metadata=fields), score))
    return matches


def retrieve_question(index, question: str, prepared: dict, settings: dict) -> dict:
    """Embed locally, search once, validate evidence and return an observable result."""
    top_k, timeout = retrieval_options(settings)
    started = time.perf_counter()
    embedded = embed_local_query(question, settings["embedding"], prepared["model_digest"])
    embedding_seconds = time.perf_counter() - started
    retrieval = settings["retrieval"]
    # Request evidence fields explicitly; never download stored vectors for a normal search.
    fields = sorted({key for doc in prepared["documents"] for key in doc
                     if key not in ("_id", retrieval["vector_field"])})
    search_started = time.perf_counter()
    response = index.documents.search(
        namespace=retrieval["namespace"], top_k=top_k,
        score_by=[DenseVectorQuery(field=retrieval["vector_field"], values=embedded["vector"])],
        include_fields=fields, timeout=timeout,
    )
    search_seconds = time.perf_counter() - search_started
    matches = validate_matches(response, prepared, settings)
    usage = response.usage.read_units if response.usage is not None else None
    if usage is not None and (type(usage) not in (int, float) or not math.isfinite(usage) or usage < 0):
        raise RetrievalError("Pinecone returned invalid usage information.")
    return {
        "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "question": question.strip(), "embedding_input": embedded["embedding_input"],
        "query_rewritten": False, "retrieval_mode": "semantic", "as_of_date": prepared["as_of_date"],
        "model": settings["embedding"]["model"], "model_digest": prepared["model_digest"],
        "dimensions": settings["embedding"]["dimensions"], "corpus_sha256": prepared["corpus_sha256"],
        "index_name": retrieval["index_name"], "namespace": retrieval["namespace"],
        "top_k": top_k, "metric": retrieval["metric"],
        "query_prompt_tokens": embedded["prompt_tokens"],
        "embedding_seconds": embedding_seconds, "search_seconds": search_seconds,
        "total_seconds": time.perf_counter() - started,
        "pinecone_read_units": usage, "embedding_external_charge_usd": "0",
        "pinecone_charge_usd": None, "answer_generated": False,
        "evidence_status": "candidates_require_review" if matches else "no_candidates",
        "matches": [{"chunk_id": doc.id, "score": score, "text": doc.page_content,
                     "metadata": doc.metadata} for doc, score in matches],
    }


def score_expected_sources(result: dict, case: dict) -> dict:
    """Source-section recall only, not answer quality or a complete relevance judgement."""
    if case["evaluation_mode"] != "end_to_end":
        raise RetrievalError("Controlled-context generation cases cannot be scored as normal retrieval.")
    if case["as_of_date"] != result["as_of_date"] or case["user_question"] != result["question"]:
        raise RetrievalError("The evaluation question and policy date must match the retrieval run.")
    expected = {(source["document_id"], source["section_id"]) for source in case["expected_source"]}
    found = {(hit["metadata"]["document_id"], hit["metadata"]["section_id"]) for hit in result["matches"]}
    matched = sorted(expected & found)
    missing = sorted(expected - found)
    return {
        "test_id": case["test_id"], "category": case["category"],
        "expected_count": len(expected), "matched_count": len(matched),
        "expected_source_recall_at_k": len(matched) / len(expected) if expected and "policy_lookup" not in result else None,
        "expected_source_recall": len(matched) / len(expected) if expected else None,
        "measurement_scope": "semantic_plus_policy_lookup" if "policy_lookup" in result else "semantic_top_k",
        "returned_chunks": len(result["matches"]),
        "matched_sources": [list(item) for item in matched], "missing_sources": [list(item) for item in missing],
        "excluded_source_leakage": sorted({hit["metadata"]["document_id"] for hit in result["matches"]}
                                         & set(case.get("excluded_document_ids", []))),
        "answer_groundedness": None, "citation_correctness": None,
    }


def baseline_cases(root: Path, settings: dict) -> list[dict]:
    cases = json.loads((root / "evaluation/cases.json").read_text(encoding="utf-8"))
    selected = settings["retrieval_example"]["baseline_case_ids"]
    if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
        raise RetrievalError("Choose distinct evaluation case IDs for the baseline.")
    by_id = {case["test_id"]: case for case in cases}
    if any(identifier not in by_id for identifier in selected):
        raise RetrievalError("A baseline case ID does not exist in the evaluation file.")
    result = [by_id[identifier] for identifier in selected]
    for case in result:
        if case["evaluation_mode"] != "end_to_end" or case["as_of_date"] != settings["demo"]["as_of_date"]:
            raise RetrievalError("Baseline cases must use normal retrieval and the configured demo date.")
    return result


def print_result(result: dict) -> None:
    print(f"\nQuestion: {result['question']}")
    print(f"Policy date: {result['as_of_date']} | Semantic top k: {result['top_k']} | Total passages: {len(result['matches'])}")
    for rank, hit in enumerate(result["matches"], start=1):
        source = hit["metadata"]
        method = f"Similarity: {hit['score']:.4f}" if hit['score'] is not None else "Policy-reference lookup; no similarity score"
        print(f"\n{rank}. {source['document_title']} / {source['section_heading']} | {method}")
        print(f"Source: {source['source_file']} | Chunk: {hit['chunk_id']}")
        print(hit["text"])
    if not result["matches"]:
        print("No policy passages were returned; there is no retrieved evidence to use.")
    print(f"\nQuestion input: {result['query_prompt_tokens']} tokens | Pinecone read units: {result['pinecone_read_units']}")
    print(f"Local embedding: {result['embedding_seconds']:.2f}s | Pinecone search: {result['search_seconds']:.2f}s")
    if "policy_lookup" in result:
        lookup = result["policy_lookup"]
        print(f"Lookup added {lookup['added_chunks']} passages | Fetch read units: {lookup['fetch_read_units']} | Fetch: {lookup['fetch_seconds']:.2f}s")
        print(f"Policies: {', '.join(lookup['policy_ids']) or 'none'} | Rule: {lookup['mode']}")
        for key in ("unknown_policy_ids", "unsupported_version_ids", "skipped_policy_ids"):
            if lookup[key]:
                print(f"Lookup notice ({key}): {', '.join(lookup[key])}")
    print("Candidates only: scores are not confidence percentages. No answer was generated.", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", help="Use fictional policy questions only; results are saved locally.")
    parser.add_argument("--baseline", action="store_true", help="Run the configured direct, paraphrased and exact-ID cases.")
    parser.add_argument("--follow-references", action="store_true", help="Also fetch missing approved sections for explicit policy IDs, once.")
    args = parser.parse_args(argv)
    if args.baseline and args.question:
        parser.error("Choose either one question or --baseline.")
    logging.getLogger("pinecone").setLevel(logging.CRITICAL)
    try:
        settings = load_settings()
        _, timeout = retrieval_options(settings)
        prepared = prepare_upload(PROJECT_ROOT, settings)  # Validation only; this function never uploads.
        options = settings["retrieval_example"]
        cases = baseline_cases(PROJECT_ROOT, settings) if args.baseline else []
        questions = [case["user_question"] for case in cases] if args.baseline else [args.question or options["question"]]
        for question in questions:
            query_input(question, settings["embedding"])
        output_options = settings["policy_lookup"] if args.follow_references else options
        output = generated_json_path(PROJECT_ROOT, output_options["baseline_output_file" if args.baseline else "output_file"])
        protected = [settings[section]["output_file"] for section in ("embedding_preparation", "ollama_example", "embedding_example", "chunk_preparation")]
        protected.append(settings["pinecone_ingestion"]["report_file"])
        if args.follow_references:
            protected.extend([options["output_file"], options["baseline_output_file"]])
        if output in [generated_json_path(PROJECT_ROOT, name) for name in protected]:
            raise RetrievalError("Keep retrieval output separate from the corpus and indexing reports.")
        key = read_credential("PINECONE_API_KEY", PROJECT_ROOT)
        if not key:
            raise RetrievalError("Configure PINECONE_API_KEY privately in Week2 Project/.env.")
        print(f"Running {len(questions)} semantic search(es) with local Ollama and Pinecone read requests.", flush=True)
        if args.follow_references:
            print("Policy lookup enabled: each question may add one fetch request; original search reports are preserved.", flush=True)
        results = []
        with Pinecone(api_key=key, timeout=timeout, retry_config=RetryConfig(max_retries=0)) as client:
            info = client.indexes.describe(settings["retrieval"]["index_name"])
            check_index(info, settings, prepared)
            with client.index(host=info.host) as index:
                for position, question in enumerate(questions):
                    result = retrieve_question(index, question, prepared, settings)
                    if args.follow_references:
                        result = follow_policy_references(index, result, prepared, settings)
                    if args.baseline:
                        result["evaluation"] = score_expected_sources(result, cases[position])
                    print_result(result)
                    if args.baseline:
                        score = result["evaluation"]
                        print(f"{score['test_id']} expected sections found: {score['matched_count']}/{score['expected_count']}", flush=True)
                    results.append(result)
        report = {"schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(), "results": results} if args.baseline else results[0]
        save_chunk_export(report, output)
        print(f"Saved: {output.relative_to(PROJECT_ROOT).as_posix()}")
        return 0
    except (RetrievalError, IngestionError, PolicyLookupError) as error:
        print(f"Retrieval stopped: {error}")
    except ValueError:
        print("Retrieval stopped: check local Ollama, its installed model, input length and the prepared corpus.")
    except (KeyError, TypeError, OSError):
        print("Retrieval stopped: check the configured files and their fields. No complete result was saved.")
    except Exception:
        print("Pinecone search could not finish. Check connection, index access and account limits; raw provider errors are hidden.")
    print("No successful current result is claimed. Earlier output files may remain; check their timestamps.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
