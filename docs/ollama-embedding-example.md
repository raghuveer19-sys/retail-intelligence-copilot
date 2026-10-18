# Our first real embedding with Ollama

On 2026-10-15 the user chose local Ollama embeddings while an OpenAI key is unavailable. Pinecone remains the planned store. The user reports a Starter account and key, with Builder credits pending; that key is not yet visible to the local project.

## What changed

Downloaded `embeddinggemma:300m`, a dedicated text embedding model of about 622 MB. Ollama 0.40.4 reports a 2,048-token input context and 768 output dimensions. This is the 300M EmbeddingGemma model, not EmbeddingGemma 2. The installed model digest is recorded with the result. The existing `qwen3:4b` practice model is unchanged. [Ollama model](https://ollama.com/library/embeddinggemma), [specific Google model card](https://huggingface.co/google/embeddinggemma-300m).

| Measurement | Earlier OpenAI preview | Actual Ollama example |
| --- | --- | --- |
| Model | `text-embedding-3-small` | `embeddinggemma:300m` |
| Input | Passage body | Document prompt, title and passage |
| Input tokens | 50, counted locally | 63, reported by Ollama |
| Output | 1,536 values expected; not generated | 768 actual values saved |

Both tokenizer and input changed; the difference cannot be attributed solely to the title. OpenAI token counts and prices do not apply to this model.

```text
Eligible LangChain chunk -> document prompt -> local Ollama /api/embed
    -> validate vector -> save text + metadata + vector [completed]
    -> map Pinecone record [validated locally] -> upload [pending]
```

The configured document prompt is `title: {title} | text: {text}`. The later retrieval-query prompt is `task: search result | query: {text}`. These follow the model's instructions; the query path is not implemented yet. The original passage stays unchanged, while the exact formatted input is saved separately. [Prompt instructions](https://huggingface.co/google/embeddinggemma-300m#prompt-instructions).

## Files and operation

- `config/settings.toml`: `[embedding]` is active Ollama; `[openai_embedding]` retains the comparison lesson.
- `ollama_embeddings.py`: calls the documented local HTTP API using Python's standard library; no new Python dependency.
- `ollama_example.py`: selects one eligible chunk, generates and saves one vector.
- `pinecone_records.py`: validates and maps the result without uploading.
- `data/processed/ollama-embedding-example.json`: actual generated result, ignored by Git.

This command generates one real local embedding. It has already succeeded; rerunning now stops because the result file exists, encouraging inspection before replacement:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.ollama_example
```

The client accepts loopback HTTP addresses only, disables proxies and redirects, checks that the model is installed locally, reads no credentials and performs no automatic retries. Input truncation is disabled: an oversized input fails instead of silently losing a policy condition. The model is unloaded after the request. Missing models, unavailable Ollama, invalid responses and unsafe output paths produce errors. [Ollama API](https://docs.ollama.com/api/embed).

## Observed result

Chunk `AUTH-1001-v1:delegation:section-v1` produced **768 numbers**, with **63 reported input tokens** and **5.27 seconds** reported request duration. This single run includes startup overhead and is not a performance benchmark. First five values: `-0.126700, 0.077532, 0.012817, 0.010269, -0.027441`.

All **103 automated tests passed**: 85 existing checks, nine record-mapping tests and nine Ollama tests. Automated responses were simulated; the real local model run was a separate acceptance check. Saved text/source identity and vector shape were checked. No Pinecone API request, upload, query embedding, retrieval-quality evaluation or answer generation has run.

Local embedding has no per-token service bill. Hardware, electricity, storage and download traffic still use resources; their costs were not measured. The model download is reusable. Keep successful results to avoid unnecessary regeneration. See [cost notes](cost-model.md).

Subsequent progress: [all 33 corpus embeddings](corpus-embeddings.md) and [actual Pinecone indexing](pinecone-indexing.md) are complete. The index matches the active 768-dimensional model. Next comes question embedding and retrieval. Use the same model for document and question embeddings; equal vector length alone does not make different models compatible. [Ollama guidance](https://docs.ollama.com/capabilities/embeddings).
