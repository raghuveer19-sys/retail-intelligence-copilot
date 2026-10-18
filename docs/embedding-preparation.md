# Embedding preparation: count before sending

Date: 2026-10-15. This local step within Phase 2 creates no embeddings and makes no embedding or Pinecone requests.

**Current project update:** This is the retained OpenAI tokenizer/pricing comparison, now reading `[openai_embedding]`. The active model is local Ollama `embeddinggemma:300m`. Its first real example reported 63 tokens for a different formatted input and returned 768 values. Do not apply this page's OpenAI counts or prices to Ollama. See [the local example](ollama-embedding-example.md).

## The concept

A word is a unit we recognise when reading. A token is a piece of text recognised by the model's tokenizer: it may be a word, part of a word or punctuation. A tokenizer applies the chosen model's text-splitting rules. One word does not necessarily equal one token.

Our authority passage, `AUTH-1001-v1:delegation:section-v1`, contains **43 words but 50 tokens**. Across all 33 eligible sections, 1,169 words become **1,404 tokens** with the selected encoding. These measurements describe these passages, not a universal words-to-tokens ratio.

| Operation | Output | Purpose |
| --- | --- | --- |
| Tokenization, implemented locally | Token IDs and a count | Measure input size and estimate usage |
| Embedding, still pending | A vector: numbers representing relatedness | Compare a question with passages for retrieval |

Token IDs are vocabulary lookup numbers, not embedding vectors. The planned model's 1,536 vector dimensions are separate from its input token count; a 50-token passage does not imply a 50-number embedding.

```text
Policy JSON -> validate -> select approved, effective policies
            -> section-v1 LangChain Document chunks
            -> count page_content tokens locally [implemented now]
            -> review size and estimated cost
            -> embedding API [later, needs account access]
            -> Pinecone [later]
```

## What we count

The proposed embedding input is each chunk's exact `page_content`. Source metadata and IDs stay attached for tracking but are not included in the measured text. We add no headings, trim no text, and do not combine separate inputs before counting them. The total is the sum of each chunk's token count.

The report freshly validates source policies, applies the configured eligibility date, and uses the same `section_chunks` function as preparation. It does not read a potentially stale `chunks.json` or overwrite it. The current strategy must be `section-v1`. Any later uploader must use exactly the same input text or recalculate the counts. Whether adding titles improves retrieval is a later evaluation question.

## Model, limits and price

Settings select `text-embedding-3-small` and `cl100k_base`. We installed `tiktoken` 0.14.0 and declared PyYAML, the reader for our existing pricing file. The model-to-tokenizer mapping must match the configuration; unknown mappings stop the report rather than silently using a different encoding. [Official tokenizer guidance](https://developers.openai.com/api/docs/guides/embeddings).

The configured maximum is **8,192 tokens per input**, checked against the official reference on 2026-10-15. Exactly that count passes; a larger input is flagged and the command exits unsuccessfully. It does not truncate, split again or upload anything. Review an oversized section's rule and conditions before choosing new boundaries. This is a size ceiling, not an ideal retrieval chunk size. [Embedding input requirements](https://developers.openai.com/api/reference/resources/embeddings/methods/create).

The API also has request-wide limits, including 300,000 total tokens across inputs in one request. Corpus batching and account rate-limit handling remain future work. The later [one-chunk example](embedding-example.md) introduces an explicit per-attempt allowance and disables automatic retries. Passing this token report's per-input check does not establish account readiness to send API requests.

The standard public rate is **USD 0.02 per million input tokens**, rechecked on 2026-10-15 and recorded in `config/pricing.yaml`. The calculator requires a matching model, USD standard billing, a checked date, a source URL and a known positive rate. Unknown prices do not become zero-cost estimates. [Official model price](https://developers.openai.com/api/docs/models/text-embedding-3-small).

```text
One corpus pass = 1,404 / 1,000,000 × USD 0.02
                = USD 0.00002808
```

This estimates embedding these inputs once. It excludes question embeddings, changed documents, resubmissions, generation, Pinecone, tax and currency conversion. No paid requests were made. Future actual usage must be reconciled with returned API usage and provider billing. Reuse unchanged embeddings to avoid paying to submit the same inputs again. Public rates do not establish account access or credit eligibility.

## Run and read the report

From the Week2 PowerShell terminal, this command uses this project's Python, rebuilds eligible chunks in memory, and prints their counts and estimated cost:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.token_report
```

On a new environment, the README's `uv sync --no-active` installs the locked dependencies first. The tokenizer's first use downloads a public vocabulary; no policy text is sent with that download. Later runs use the cached vocabulary. By default it is in the ignored `.cache/tiktoken/` directory; an existing `TIKTOKEN_CACHE_DIR` environment setting takes priority. [First-use download behavior](https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken).

Expected measured summary for the current sources and demo date:

```text
AUTH-1001-v1:delegation:section-v1 | 43 | 50 | OK
Measured 33 chunks: 1,404 tokens; sizes 26-57.
Estimated cost to embed these inputs once: USD 0.00002808
All chunks pass the configured per-input size check.
```

The per-chunk columns are ID, words, tokens and size status. `OK` means the text fits the configured limit; it says nothing about retrieval relevance or answer correctness.

Common messages:

- `Tokenizer files could not be loaded`: first use needs internet and a writable cache; this is not a missing API key.
- `OVER LIMIT`: review the named section and preserve its conditions when deciding how to split it.
- `no eligible chunks`: check the demo date and approval metadata; do not bypass eligibility.
- A model/pricing mismatch or invalid rate: verify settings against official sources and correct the dated pricing file.

## Verification and next step

All **68 automated tests passed** on 2026-10-15, including 16 new checks. They cover the real corpus, a known tokenizer example, Unicode and special-looking text, unchanged content, empty input, IDs, exact/over-limit boundaries, pricing precision and invalid settings. A command test blocked network connections after loading the vocabulary and still passed. Existing document, chunking, preparation and readiness tests also passed. Streamlit checks were not repeated because its code was unchanged.

These are local counting and behavior results. No vector quality, live API acceptance, retrieval quality, account access or actual billed amount has been tested.

The user correctly explained that word counts cannot reliably predict token usage. The next distinction is between input tokens and vector dimensions. The [one-chunk integration lesson](embedding-example.md) now provides a preview and simulated request tests. The user confirmed that they still have no OpenAI API key and requested local work. Before actual embedding, establish API access, review costs and choose an allowance. This token-report command never sends embedding requests.
