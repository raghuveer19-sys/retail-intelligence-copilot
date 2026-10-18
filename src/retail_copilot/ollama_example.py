"""Generate and save one real local embedding; never contact a cloud service."""

from datetime import date

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.ollama_embeddings import embed_local_chunk
from retail_copilot.prepare_chunks import save_chunk_export


def main() -> int:
    try:
        settings = load_settings()
        demo, embedding, example = settings["demo"], settings["embedding"], settings["ollama_example"]
        if settings["chunk_preparation"]["strategy"] != "section-v1":
            raise ValueError("This example requires section-v1 chunks.")
        as_of = date.fromisoformat(demo["as_of_date"])
        eligible = approved_documents(load_documents(PROJECT_ROOT / demo["knowledge_directory"]), as_of)
        chunk = next((chunk for doc in eligible for chunk in section_chunks(doc) if chunk.id == example["chunk_id"]), None)
        if chunk is None:
            raise ValueError("The example chunk is not approved and effective for the demo date.")
        output = (PROJECT_ROOT / example["output_file"]).resolve()
        if not output.is_relative_to((PROJECT_ROOT / "data" / "processed").resolve()) or output.suffix != ".json":
            raise ValueError("Save the local embedding as JSON inside data/processed/.")
        if output.exists():
            raise ValueError("A local result already exists. Inspect it before generating a replacement.")
        print("One real embedding using local Ollama; no OpenAI or Pinecone request.")
        print(f"Chunk: {chunk.id}")
        print(f"Model: {embedding['model']} | Expected dimensions: {embedding['dimensions']}")
        print("Input includes the model's document prompt, title and original passage. Truncation is disabled.")
        result = embed_local_chunk(chunk, embedding)
        result["as_of_date"] = as_of.isoformat()
        save_chunk_export(result, output)
        print(f"Saved one REAL vector with {len(result['vector'])} numbers to {example['output_file']}.")
        print(f"Ollama-reported input tokens: {result['usage']['prompt_tokens']} | Request time: {result['duration_seconds']:.2f}s")
        print("First five values: " + ", ".join(f"{value:.6f}" for value in result["vector"][:5]))
        print("Embedding API charge: USD 0. Local hardware, electricity and download costs are separate.")
        print("Pinecone format validation passed locally. No records uploaded; retrieval quality is not tested.")
        return 0
    except (KeyError, TypeError):
        print("Local embedding could not finish: check the demo, embedding and ollama_example settings.")
    except (OSError, ValueError) as error:
        print(f"Local embedding could not finish: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
