# Phase 3: finding evidence for a question

Implemented and tested on **2026-10-17**, using the indexed corpus and fixed policy date **2026-10-15**. This is our first measured retrieval baseline, before improvements.

**Later enhancement:** Optional [policy-ID/reference lookup](policy-lookup.md) has now been implemented and measured. It recovers the two missing sections in these cases, with extra passages and fetch usage. This page preserves the original baseline and k=8 experiment; the default remains semantic top_k 4.

```text
Fictional question -> local Ollama question embedding (768 numbers)
    -> Pinecone cosine search, top_k = 4
    -> validate returned evidence against eligible local sources
    -> display passages, source labels, scores, usage and timing
```

## What the command does

**Retrieval** means finding evidence. **Semantic retrieval** compares representations of meaning, so different wording can find related passages. It does not guarantee every necessary condition or exact policy reference will be found.

1. Read the configured question or one supplied in the terminal. Use fictional questions only; questions and results are saved locally.
2. Revalidate the saved corpus against current local sources and the fixed policy date. This reuses `prepare_upload`, a validation function that does not itself upload anything.
3. Check the remote index's dimensions, metric and project/model/corpus tags. Resolve the host through Pinecone's authenticated index description.
4. Embed the question locally using the same `embeddinggemma:300m` version as the documents. Apply `task: search result | query: {text}`. This prefix identifies the embedding task; it does not rewrite the question. Document input uses `title: ... | text: ...`. [Model-author instructions](https://huggingface.co/google/embeddinggemma-300m).
5. Send the vector to the configured namespace and ask for up to four candidates. Search names the `embedding` field and requests passage text and source fields explicitly, without downloading stored vectors. The question is not uploaded as a new policy. [Pinecone search](https://docs.pinecone.io/guides/search/semantic-search), [current SDK](https://sdk.pinecone.io/python/migration/v10-migration.html).
6. Reject unknown, excluded or duplicate IDs, changed text, missing metadata and invalid scores. Valid hits become LangChain `Document` containers with separate similarity scores. Source details come from the actual returned evidence, checked against local sources.
7. Print the passages and save a local JSON report containing model/corpus identity, exact question input, tokens, separate embedding/search times and reported read units. Credentials and query vectors are not saved.

Question embeddings disable truncation and check installed-model identity, vector shape, finite values and usage. Oversized input fails rather than silently losing text. [Ollama API](https://docs.ollama.com/api/embed).

## Real baseline results

Each of the three searches returned four candidates.

| Case | Question type | Expected sections found in top 4 | Missing expected evidence |
| --- | --- | --- | --- |
| E01 | Appointment question, direct wording | 1/1 (100%) | None |
| E04 | Stolen phone/SIM, paraphrased wording | 2/3 (66.7%) | `IDV-1001-v1 / training_id` |
| E06 | Exact policy ID `SIM-1024` | 1/2 (50%) | `SIM-1024-v2 / appointments` |

**Expected-source recall at k** is expected document/section pairs found divided by pairs expected. A different section from the same document does not count. These percentages are not overall application accuracy. Other retrieved passages may still be useful; relevance precision has not been scored.

E01 ranked **SIM replacement / Appointments and scope** first, with score **0.7687**. Its fictional text says a physical SIM replacement does not require an appointment. The command displayed that passage; it did not write a new answer. The score is not a 76.87% probability of correctness.

E04 found SIM checks and account roles but missed the detailed training-ID requirement. Referring to an identity policy is not the same as retrieving its requirements. E06 found SIM checks and eSIM guidance but missed appointments: semantic ranking does not guarantee complete policy-ID lookup. These gaps are recorded before choosing an improvement.

No archived source appeared in accepted results, and all returned source data matched the eligible corpus. This is not a comprehensive governance or adversarial-input evaluation.

| Case | Local input tokens | Embedding seconds | Search seconds | Reported read units |
| --- | --- | --- | --- | --- |
| E01 | 20 | 6.10 | 1.31 | 1 |
| E04 | 26 | 1.81 | 0.35 | 1 |
| E06 | 20 | 2.02 | 0.32 | 1 |

Totals: **66 local input tokens and 3 reported read units**. These single-run timings are not a benchmark. Reported total time covers embedding, search and result checks, excluding earlier file validation and index/client setup.

Local inference has no external API charge; hardware/electricity cost is unmeasured. Pinecone reads and response transfer consume allowances. Starter is user-reported; remaining quota and billing details are not independently verified. No index writes, subscription change or answer-generation request occurred. See [cost notes](cost-model.md).

## Try the first question

From the **Week2 Project** terminal, with Ollama running, this command embeds the configured appointment question, makes one Pinecone search, prints passages and saves `data/processed/retrieval-example.json`:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.retrieve
```

Expect up to four passages with titles, sections, scores and filenames. The observed first result is SIM appointments; rankings can change with model/corpus changes. Add a fictional question in quotation marks to search different wording. The `--baseline` option instead repeats the three configured evaluation cases and saves `data/processed/retrieval-baseline.json`, consuming three searches. The baseline has already run.

Generated reports are ignored by Git. `evaluation/cases.json` remains the authored specification, with its result placeholders unchanged; measured results live in the separate report. Failed runs do not replace the last complete report, so check its timestamp.

## Files, tests and limits

| File | Purpose |
| --- | --- |
| `ollama_embeddings.py` | Added question formatting and local query embeddings |
| `retrieve.py` | Search, source checks, terminal display and three-case baseline runner |
| `tests/test_retrieval.py` | 17 offline tests, including installed SDK request/response conversion |
| `config/settings.toml` | Top k, timeout, question, baseline cases and output paths |

All **144 automated tests passed**. New checks cover model mismatch, invalid vectors/usage, blank input, evidence fields, source/namespace validation, empty results, top-k bounds, section recall and sanitized errors. Simulated tests establish program behavior; the real searches separately measure retrieval.

If Ollama is unavailable, start it locally. If source/model/index checks fail, review the mismatch instead of bypassing it. Pinecone connection failures require checking access and limits without displaying keys. Missing evidence produces no invented passage or answer. SDK data requests can retry transient failures; our application does not loop over failed searches, and usage may still occur on a failed run.

The current command rejects returned evidence that differs from the approved local corpus; it does not add a Pinecone metadata filter, query rewriting, reranking or keyword search. It has no calibrated score threshold, completeness detector or answer-generation logic. The Streamlit app still shows the local document library.

## Learning and next step

### Experiment: four versus eight candidates, 2026-10-17

Repeated E01, E04 and E06 with `top_k = 8` in a temporary copy of the settings. The model digest, corpus hash, question input, namespace and fixed policy date matched the original baseline. The first four returned IDs stayed identical for all three questions. The original baseline and `settings.toml` were checked byte-for-byte and left unchanged.

| Case | Expected sections with k=4 | With k=8 | Diagnosis |
| --- | --- | --- | --- |
| E01, appointment | 1/1 | 1/1 | Expected appointments section remains rank 1 |
| E04, stolen phone/SIM | 2/3 | 2/3 | Detailed training-ID section is still outside the first eight results |
| E06, policy SIM-1024 | 1/2 | 2/2 | Appointments section appears at rank 6 |

A separate direct fetch of `IDV-1001-v1:training_id:section-v1` confirmed the identity passage exists in Pinecone and its text/metadata match the approved local source. Its absence from the top eight is therefore a retrieval-ranking/completeness problem, not a missing stored record. We did not measure its exact rank below eight.

The three searches reported 3 read units; the diagnostic fetch reported 1 more. Local query input total was 66 tokens. Returned passage words increased from 173 to 304 for E01, 173 to 321 for E04 and 156 to 322 for E06. Word counts describe the amount of passage text, not model token counts, billed data transfer or measured answer-generation cost. Search times were 1.15, 0.42 and 0.34 seconds; isolated runs do not establish a latency change.

**Decision:** Keep the application's default at 4 for now. Eight candidates recovered one missing section but still missed the identity requirement and returned substantially more text. This three-case experiment is insufficient to adopt a universal larger limit. Saved evidence: `data/processed/retrieval-top-k-8.json`, including comparison rows, all eight hits, source-presence check and original-baseline hash. No index, application code, original baseline or default settings changed.

The user correctly explained that four passages still require relevance and completeness checks. E04 and E06 demonstrate why.

The larger-k experiment showed that widening the candidate list was not sufficient for this corpus. Targeted lookup of explicitly named policy IDs has now been evaluated against these saved baselines; see [the implementation and comparison](policy-lookup.md). It is retained as an optional enhancement. Answer generation and unsupported/action-request behavior remain later work.
