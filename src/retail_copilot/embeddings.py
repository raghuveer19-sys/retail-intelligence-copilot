"""Make one explicitly enabled embedding request using a LangChain Document."""

import math
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from langchain_core.documents import Document
from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from retail_copilot.token_report import build_token_report


def preview_embedding(chunk: Document, embedding: dict, pricing: dict) -> dict:
    """Check and estimate one exact input; no credential or service access."""
    dimensions = embedding["dimensions"]
    if type(dimensions) is not int or dimensions <= 0:
        raise ValueError("Embedding dimensions must be a positive whole number.")
    report = build_token_report([chunk], embedding, pricing)
    if not report["all_within_limit"]:
        raise ValueError("This chunk exceeds the input token limit. Review its boundaries before embedding.")
    return report


def check_live_allowance(report: dict, pricing: dict, max_cost_usd: Decimal | None) -> None:
    """Check an estimated allowance; this is not a provider-enforced billing cap."""
    if pricing.get("paid_service_use_enabled") is not True:
        raise ValueError("Live service use is disabled in config/pricing.yaml. Preview remains available.")
    if not isinstance(max_cost_usd, Decimal) or not max_cost_usd.is_finite() or max_cost_usd <= 0:
        raise ValueError("Live mode requires a positive --max-cost-usd allowance.")
    if report["estimated_usd"] > max_cost_usd:
        raise ValueError("The estimated request cost exceeds the supplied allowance. No request was sent.")


def validate_response(response, model: str, dimensions: int) -> tuple[list[float], dict]:
    """Reject missing, misidentified or unusable vectors instead of saving misleading results."""
    try:
        if response.model != model or len(response.data) != 1 or response.data[0].index != 0:
            raise ValueError("Unexpected model, result count or input index.")
        vector = response.data[0].embedding
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise ValueError("Unexpected vector length.")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
            raise ValueError("Vector contains invalid numbers.")
        if not any(value != 0 for value in vector):
            raise ValueError("A zero vector cannot support similarity search.")
        prompt_tokens = response.usage.prompt_tokens
        total_tokens = response.usage.total_tokens
        if type(prompt_tokens) is not int or prompt_tokens <= 0:
            raise ValueError("Missing valid input usage.")
        if type(total_tokens) is not int or total_tokens < prompt_tokens:
            raise ValueError("Missing valid total usage.")
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
        raise ValueError(
            "The embedding response failed validation (model, vector or usage). "
            "No result was accepted; check provider usage before retrying."
        ) from None
    return list(vector), {"prompt_tokens": prompt_tokens, "total_tokens": total_tokens}


def embed_one_chunk(
    chunk: Document, embedding: dict, pricing: dict,
    client: OpenAI, max_cost_usd: Decimal,
) -> dict:
    """Send one caller-selected eligible chunk; caller owns the client's lifetime."""
    report = preview_embedding(chunk, embedding, pricing)
    check_live_allowance(report, pricing, max_cost_usd)
    try:
        response = client.embeddings.create(
            model=embedding["model"], input=[chunk.page_content],
            dimensions=embedding["dimensions"], encoding_format="float",
        )
    except AuthenticationError:
        raise ValueError("OpenAI rejected authentication. Check the private API key and project access.") from None
    except RateLimitError:
        raise ValueError("OpenAI reported a quota or rate limit. Check account billing and usage before retrying.") from None
    except APITimeoutError:
        raise ValueError("The request timed out. It may have been processed; check provider usage before retrying.") from None
    except APIError:
        raise ValueError("The OpenAI request did not complete successfully. Check service access and usage before retrying.") from None

    vector, usage = validate_response(response, embedding["model"], embedding["dimensions"])
    usage_cost = Decimal(usage["prompt_tokens"]) / Decimal(1_000_000) * report["price"]["usd_per_million_input_tokens"]
    return {
        "schema_version": 1,
        "provider": "openai",
        "model": response.model,
        "dimensions": len(vector),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "chunk_id": chunk.id,
        "text": chunk.page_content,
        "metadata": deepcopy(chunk.metadata),
        "vector": vector,
        "local_input_tokens": report["total_tokens"],
        "usage": usage,
        "pre_request_estimate_usd": str(report["estimated_usd"]),
        "usage_based_cost_usd": str(usage_cost),
        "price_checked_on": report["price"]["checked_on"],
        "price_source": report["price"]["source"],
    }
