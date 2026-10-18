"""Preview one embedding by default; live use requires explicit cost and account setup."""

import argparse
import logging
import math
from datetime import date
from decimal import Decimal, InvalidOperation

from openai import OpenAI

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.embeddings import check_live_allowance, embed_one_chunk, preview_embedding
from retail_copilot.prepare_chunks import save_chunk_export
from retail_copilot.readiness import read_credential
from retail_copilot.token_report import load_pricing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview the configured fictional passage before embedding it.")
    parser.add_argument("--live", action="store_true", help="Request one real embedding; requires enabled service use and a key.")
    parser.add_argument("--max-cost-usd", help="Maximum estimated cost allowed for this one request, in USD.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        demo, embedding, example = settings["demo"], settings["openai_embedding"], settings["embedding_example"]
        if settings["chunk_preparation"]["strategy"] != "section-v1":
            raise ValueError("This lesson requires the section-v1 chunking strategy.")
        as_of = date.fromisoformat(demo["as_of_date"])
        eligible = approved_documents(load_documents(PROJECT_ROOT / demo["knowledge_directory"]), as_of)
        chunk = next((item for doc in eligible for item in section_chunks(doc) if item.id == example["chunk_id"]), None)
        if chunk is None:
            raise ValueError("The example chunk is not approved and effective for the configured demo date.")
        pricing = load_pricing(PROJECT_ROOT / "config" / "pricing.yaml")
        report = preview_embedding(chunk, embedding, pricing)
        print("OpenAI comparison lesson; the active project embedding path is configured separately.")
        print("One-chunk embedding example: " + ("LIVE REQUEST selected" if args.live else "PREVIEW ONLY"))
        print(f"Chunk: {chunk.id} | Source: {chunk.metadata['source_file']}")
        print(f"Input: {report['total_tokens']} tokens of exact page_content; no metadata sent.")
        print(f"Model: {embedding['model']} | Expected output: {embedding['dimensions']} numbers.")
        print(f"Estimated request cost: USD {report['estimated_usd']:.8f} (not an invoice).")
        print(f"Price checked: {report['price']['checked_on']} | {report['price']['source']}")
        if not args.live:
            print("Preview complete. No embedding API call, no vector and no result file created.")
            return 0

        try:
            allowance = Decimal(args.max_cost_usd) if args.max_cost_usd is not None else None
        except InvalidOperation:
            raise ValueError("--max-cost-usd must be a positive USD amount.") from None
        check_live_allowance(report, pricing, allowance)
        output = (PROJECT_ROOT / example["output_file"]).resolve()
        if not output.is_relative_to((PROJECT_ROOT / "data" / "processed").resolve()) or output.suffix != ".json":
            raise ValueError("The example output must be a JSON file inside data/processed/.")
        if output.exists():
            raise ValueError("An output file already exists. Inspect it before considering another paid request.")
        timeout = embedding["timeout_seconds"]
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be a positive number.")
        key = read_credential("OPENAI_API_KEY", PROJECT_ROOT)
        if not key:
            raise ValueError("OPENAI_API_KEY is missing. Add it privately to Week2's .env; never paste it into chat.")
        # Avoid verbose SDK/transport logs that could include request text or headers.
        for name in ("openai", "httpx2", "httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        print("Sending one fictional passage to OpenAI. Automatic retries are disabled.")
        with OpenAI(api_key=key, base_url=embedding["api_base_url"], max_retries=0, timeout=timeout) as client:
            result = embed_one_chunk(chunk, embedding, pricing, client, allowance)
        result["as_of_date"] = as_of.isoformat()
        # Reuse the existing complete-then-replace JSON writer for the generated record.
        try:
            save_chunk_export(result, output)
        except OSError:
            raise ValueError("The API returned a result but saving failed. Usage may be billed; inspect permissions before retrying.") from None
        print(f"Saved one validated vector of {result['dimensions']} numbers to {example['output_file']}.")
        print(f"Reported input usage: {result['usage']['prompt_tokens']} tokens.")
        print(f"Usage-based cost estimate: USD {Decimal(result['usage_based_cost_usd']):.8f}; verify provider billing.")
        if result["usage"]["prompt_tokens"] != result["local_input_tokens"]:
            print("Reported usage differs from the local count; inspect the difference before further requests.")
        print("Pinecone storage and retrieval quality are not tested by this example.")
        return 0
    except (KeyError, TypeError):
        print("Embedding example could not finish: check the demo, embedding and example configuration fields.")
        return 1
    except (OSError, ValueError) as error:
        print(f"Embedding example could not finish: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
