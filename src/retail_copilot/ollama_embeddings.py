"""Create an embedding on this computer using Ollama's documented HTTP API."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from langchain_core.documents import Document

from retail_copilot.pinecone_records import to_pinecone_record
from retail_copilot.runtime_power import keep_system_awake


class LocalOllamaError(ValueError):
    """A safe local-service error without provider response bodies."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise URLError("Redirects are disabled for local Ollama requests.")


def request_local_json(embedding: dict, route: str, payload: dict | None = None) -> dict:
    """Call only a loopback Ollama URL, without proxies, credentials or retries."""
    base = embedding["api_base_url"]
    address = urlsplit(base)
    if (address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost", "::1")
            or address.username or address.password or address.query or address.fragment
            or address.path not in ("", "/")):
        raise LocalOllamaError("Local Ollama requires an HTTP address on this computer.")
    timeout = embedding["timeout_seconds"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise LocalOllamaError("The local request timeout must be a positive number.")
    if route not in ("/api/tags", "/api/embed", "/api/show", "/api/chat"):
        raise LocalOllamaError("Choose a supported local Ollama endpoint.")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(base.rstrip("/") + route, data=body, headers={"Content-Type": "application/json"})
    try:
        with keep_system_awake():
            with build_opener(ProxyHandler({}), _NoRedirects()).open(request, timeout=timeout) as response:
                result = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise LocalOllamaError("Ollama could not find the model or endpoint; check the installed model and Ollama version.") from None
        raise LocalOllamaError("Ollama rejected the request. Check the model, supported options and input length.") from None
    except TimeoutError:
        raise LocalOllamaError("Local Ollama timed out before a complete response arrived. Review the timeout and CPU workload.") from None
    except (URLError, OSError):
        raise LocalOllamaError("Could not reach local Ollama or its connection failed. Check that Ollama is running.") from None
    except (json.JSONDecodeError, UnicodeError):
        raise LocalOllamaError("Local Ollama returned an unreadable response.") from None
    if not isinstance(result, dict) or "error" in result:
        raise LocalOllamaError("Local Ollama did not return a successful result.")
    return result


def document_input(chunk: Document, embedding: dict) -> str:
    """Apply the model's retrieval-document prompt without changing the saved text."""
    if not chunk.id or not chunk.page_content.strip():
        raise ValueError("Select a chunk with an ID and non-empty original text.")
    title = chunk.metadata.get("document_title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("The passage needs its source document title.")
    try:
        template = embedding["document_template"]
        if not isinstance(template, str) or "{text}" not in template:
            raise ValueError("The template must include the passage text.")
        return template.format(title=title, text=chunk.page_content)
    except (KeyError, ValueError, AttributeError):
        raise ValueError("Check document_template: it must format the title and passage text.") from None


def installed_model_digest(embedding: dict) -> str:
    """Identify the installed local model so saved vectors cannot mix model versions."""
    model = embedding["model"]
    if embedding["provider"] != "ollama" or not isinstance(model, str) or ":cloud" in model:
        raise ValueError("Choose a locally installed Ollama embedding model.")
    installed = request_local_json(embedding, "/api/tags")
    models = installed.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama returned an invalid model list.")
    match = next((item for item in models if isinstance(item, dict) and item.get("name") == model), None)
    if match is None:
        raise ValueError("The configured embedding model is not installed; download it with ollama pull first.")
    if match.get("remote_host") or match.get("remote_model") or not isinstance(match.get("digest"), str) or not match["digest"]:
        raise ValueError("This example requires an installed local model with a recorded digest.")
    return match["digest"]


def query_input(question: str, embedding: dict) -> str:
    """Mark this input as a search question, using the model's configured prompt."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Enter a non-empty fictional policy question.")
    try:
        template = embedding["query_template"]
        if not isinstance(template, str) or "{text}" not in template:
            raise ValueError("Missing question placeholder.")
        return template.format(text=question.strip())
    except (KeyError, ValueError, AttributeError):
        raise ValueError("Check query_template: it must include the question text.") from None


def embed_local_query(question: str, embedding: dict, expected_digest: str) -> dict:
    """Embed a search question, never treating it as a policy record to upload."""
    input_text = query_input(question, embedding)
    dimensions, limit = embedding["dimensions"], embedding["max_input_tokens"]
    if type(dimensions) is not int or dimensions <= 0 or type(limit) is not int or limit <= 0:
        raise ValueError("Query dimensions and input limit must be positive whole numbers.")
    digest = installed_model_digest(embedding)
    if digest != expected_digest:
        raise ValueError("The installed model differs from the indexed corpus. Review the model before searching.")
    response = request_local_json(embedding, "/api/embed", {
        "model": embedding["model"], "input": [input_text], "truncate": False,
        "dimensions": dimensions, "keep_alive": "0s",
    })
    vectors = response.get("embeddings")
    if response.get("model") != embedding["model"] or not isinstance(vectors, list) or len(vectors) != 1:
        raise ValueError("Ollama must return one question vector from the configured model.")
    vector = vectors[0]
    if not isinstance(vector, list) or len(vector) != dimensions:
        raise ValueError("The question vector must match the index dimensions.")
    try:
        valid = all(type(value) in (int, float) and math.isfinite(value) for value in vector)
    except OverflowError:
        valid = False
    if not valid or not any(value != 0 for value in vector):
        raise ValueError("The question vector must contain finite numbers and cannot be all zeros.")
    tokens, duration = response.get("prompt_eval_count"), response.get("total_duration")
    if type(tokens) is not int or not 0 < tokens <= limit or type(duration) is not int or duration < 0:
        raise ValueError("Ollama returned invalid question usage/timing or exceeded the input limit.")
    return {
        "vector": vector, "embedding_input": input_text, "model_digest": digest,
        "prompt_tokens": tokens, "provider_duration_seconds": duration / 1_000_000_000,
    }


def embed_local_chunk(chunk: Document, embedding: dict, *, keep_alive: str = "0s") -> dict:
    """Embed one eligible passage locally; eligibility selection belongs to the caller."""
    model = embedding["model"]
    digest = installed_model_digest(embedding)
    input_text = document_input(chunk, embedding)
    limit = embedding["max_input_tokens"]
    if type(limit) is not int or limit <= 0:
        raise ValueError("The model's input limit must be a positive whole number.")
    response = request_local_json(embedding, "/api/embed", {
        "model": model, "input": [input_text], "truncate": False,
        "dimensions": embedding["dimensions"], "keep_alive": keep_alive,
    })
    vectors = response.get("embeddings")
    if response.get("model") != model or not isinstance(vectors, list) or len(vectors) != 1:
        raise ValueError("Ollama must return one vector from the configured model.")
    tokens = response.get("prompt_eval_count")
    duration = response.get("total_duration")
    if type(tokens) is not int or not 0 < tokens <= limit or type(duration) is not int or duration < 0:
        raise ValueError("Ollama returned invalid input usage or timing, or exceeded the configured input limit.")
    result = {
        "schema_version": 1, "provider": "ollama", "model": model,
        "model_digest": digest, "dimensions": embedding["dimensions"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "chunk_id": chunk.id, "text": chunk.page_content,
        "metadata": deepcopy(chunk.metadata), "vector": vectors[0],
        "embedding_input": input_text, "document_template": embedding["document_template"],
        "usage": {"prompt_tokens": tokens}, "duration_seconds": duration / 1_000_000_000,
        "embedding_api_charge_usd": "0",  # Local computation; not a total operating cost.
    }
    to_pinecone_record(result, embedding)  # Reuse vector/source/format checks; no upload.
    return result
