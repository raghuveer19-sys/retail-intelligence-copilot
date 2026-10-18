"""Count proposed embedding inputs locally; never call an embedding service."""

import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import tiktoken
import yaml
from langchain_core.documents import Document

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import (
    PROJECT_ROOT, approved_documents, load_documents, load_settings,
)


def load_pricing(path: Path) -> dict:
    """Read the dated public rates, without reading credentials."""
    try:
        pricing = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ValueError("Could not read config/pricing.yaml as valid UTF-8 YAML.") from None
    if not isinstance(pricing, dict):
        raise ValueError("config/pricing.yaml must contain named pricing fields.")
    return pricing


def embedding_price(pricing: dict, model: str) -> dict:
    """Require a matching, dated USD standard rate; unknown never means free."""
    try:
        price = pricing["openai_candidates"]["embedding"]
        if pricing["currency"] != "USD" or price["billing_mode"] != "standard":
            raise ValueError("The estimate requires a standard USD embedding rate.")
        if price["model"] != model:
            raise ValueError("The embedding model and pricing model do not match.")
        checked_on = date.fromisoformat(price["checked_on"]).isoformat()
        source = price["source"]
        if not isinstance(source, str) or not source.startswith("https://"):
            raise ValueError("The embedding rate needs its official source URL.")
        rate = Decimal(str(price["usd_per_million_input_tokens"]))
        if not rate.is_finite() or rate <= 0:
            raise ValueError("The embedding rate must be a known positive number.")
    except (KeyError, TypeError, InvalidOperation):
        raise ValueError("The embedding price is missing or invalid; verify config/pricing.yaml.") from None
    return {"usd_per_million_input_tokens": rate, "checked_on": checked_on, "source": source}


def load_tokenizer(embedding: dict) -> tiktoken.Encoding:
    """Use the configured model's tokenizer; first use downloads its vocabulary."""
    if embedding["provider"] != "openai":
        raise ValueError("This local report currently supports OpenAI tokenizers only.")
    limit = embedding["max_input_tokens"]
    if type(limit) is not int or limit <= 0:
        raise ValueError("max_input_tokens must be a positive whole number.")
    try:
        expected = tiktoken.encoding_name_for_model(embedding["model"])
    except KeyError:
        raise ValueError("The selected model has no known tokenizer; verify its documentation.") from None
    if embedding["tokenizer_encoding"] != expected:
        raise ValueError("The configured tokenizer does not match the selected model.")

    # Keep the downloaded vocabulary in the ignored project cache by default.
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(PROJECT_ROOT / ".cache" / "tiktoken"))
    try:
        return tiktoken.get_encoding(expected)
    except (OSError, ValueError):
        raise ValueError(
            "Tokenizer files could not be loaded. First use needs internet access "
            "to download the vocabulary; check the connection and cache permissions."
        ) from None


def count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    """Measure exact text without trimming or treating special-looking text as control tokens."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must contain non-empty text.")
    return len(encoding.encode(text, disallowed_special=()))


def build_token_report(chunks: list[Document], embedding: dict, pricing: dict) -> dict:
    """Inspect already-eligible chunks without changing text, metadata or IDs."""
    if not chunks:
        raise ValueError("There are no eligible chunks to measure.")
    price = embedding_price(pricing, embedding["model"])
    encoding = load_tokenizer(embedding)
    rows = []
    seen_ids = set()
    for chunk in chunks:
        if not chunk.id or not chunk.id.strip() or chunk.id in seen_ids:
            raise ValueError("Every measured chunk needs a unique, non-empty ID.")
        seen_ids.add(chunk.id)
        tokens = count_tokens(chunk.page_content, encoding)
        rows.append({
            "chunk_id": chunk.id,
            "word_count": len(chunk.page_content.split()),
            "token_count": tokens,
            "within_limit": tokens <= embedding["max_input_tokens"],
        })
    total = sum(row["token_count"] for row in rows)
    return {
        "model": embedding["model"],
        "encoding": encoding.name,
        "max_input_tokens": embedding["max_input_tokens"],
        "input_text": "page_content only; no metadata or added headings",
        "chunks": sorted(rows, key=lambda row: row["chunk_id"]),
        "total_tokens": total,
        "all_within_limit": all(row["within_limit"] for row in rows),
        "estimated_usd": Decimal(total) / Decimal(1_000_000) * price["usd_per_million_input_tokens"],
        "price": price,
    }


def main() -> int:
    try:
        settings = load_settings()
        demo = settings["demo"]
        if settings["chunk_preparation"]["strategy"] != "section-v1":
            raise ValueError("This report requires the current section-v1 preparation strategy.")
        as_of = date.fromisoformat(demo["as_of_date"])
        documents = load_documents(PROJECT_ROOT / demo["knowledge_directory"])
        eligible = approved_documents(documents, as_of)
        chunks = [chunk for document in eligible for chunk in section_chunks(document)]
        pricing = load_pricing(PROJECT_ROOT / "config" / "pricing.yaml")
        report = build_token_report(chunks, settings["openai_embedding"], pricing)
    except (KeyError, TypeError):
        print("Token report could not finish: check the demo, embedding and chunk_preparation settings.")
        return 1
    except (OSError, ValueError) as error:
        print(f"Token report could not finish: {error}")
        return 1

    print("OpenAI comparison token report; these counts and prices do not apply to Ollama.")
    print("Local token report (no embedding or Pinecone API calls).")
    print(f"Freshly prepared from {len(eligible)} eligible policies out of {len(documents)} on {as_of}.")
    print(f"Model: {report['model']} | Tokenizer: {report['encoding']}")
    print(f"Measured input: {report['input_text']}")
    print(f"Per-chunk limit: {report['max_input_tokens']:,} tokens (not a target chunk size).")
    print("\nChunk ID | Words | Tokens | Size check")
    for row in report["chunks"]:
        status = "OK" if row["within_limit"] else "OVER LIMIT - review section boundaries"
        print(f"{row['chunk_id']} | {row['word_count']} | {row['token_count']} | {status}")
    counts = [row["token_count"] for row in report["chunks"]]
    print(f"\nMeasured {len(counts)} chunks: {report['total_tokens']:,} tokens; sizes {min(counts)}-{max(counts)}.")
    price = report["price"]
    print(f"Rate: USD {price['usd_per_million_input_tokens']} per million input tokens; checked {price['checked_on']}.")
    print(f"Price source: {price['source']}")
    print(f"Estimated cost to embed these inputs once: USD {report['estimated_usd']:.8f}")
    print("Estimate only, not a bill. Excludes questions, retries, generation, Pinecone, tax and currency conversion.")
    print("No vectors generated. Account access, request batching and retrieval quality remain unverified.")
    if not report["all_within_limit"]:
        print("STOP: one or more chunks exceed the limit. Review and re-chunk; no text was truncated.")
        return 1
    print("All chunks pass the configured per-input size check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
