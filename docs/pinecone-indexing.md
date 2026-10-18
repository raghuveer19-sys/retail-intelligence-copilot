# Actual Pinecone indexing

Completed and checked on **2026-10-15**. This is a real upload, separate from our simulated automated tests.

## What we built

An **index** is Pinecone's searchable collection. A **namespace** separates one collection of records within that index; ours represents this fictional demo corpus. It does not replace approval checks or source metadata.

```text
12 fictional policies -> 11 eligible policies -> 33 complete sections
    -> local Ollama embeddings -> validate saved vectors against current sources
    -> Pinecone index -> read all records back and compare
```

| Setting | Verified value |
| --- | --- |
| Index | `retail-copilot-week2` |
| Namespace | `telecom-demo-v1` |
| Deployment | Managed, AWS `us-east-1` |
| Embedding model | Local Ollama `embeddinggemma:300m` |
| Vector length | 768 numbers per passage |
| Similarity method | Cosine: compares vector directions |
| Records uploaded and verified | 33 |
| Archived policy excluded | `SIM-1024-v1` |
| Verification fetch usage reported by Pinecone | 4 read units |

Cosine similarity will help rank passages when we implement search. A high similarity score alone does not prove that a passage answers a question.

## What each stored record contains

The current SDK uses a named vector field. The existing local mapper's information is preserved with these transport names:

| Local mapping | Current Pinecone document field | Meaning |
| --- | --- | --- |
| `id` | `_id` | Exact chunk identifier |
| `values` | `embedding` | The real 768-number vector |
| `metadata.text` | `text` | Original passage, unchanged |
| Other metadata fields | Same field names alongside `text` | Policy ID, title, version, section, filename and governance details |

There is no nested `metadata` object in this upload format. The source fields still serve as metadata. The vector itself contains only numbers; the surrounding record connects those numbers to readable evidence. The SDK's returned document is also distinct from the LangChain `Document` container used by our loader and chunker.

The implementation uses official Pinecone SDK **10.0.0**, `pc.indexes.create(schema=..., deployment=...)` and `index.documents.upsert(...)`. The schema declares only the searched `embedding` field; metadata fields are indexed when records arrive. We supply vectors computed locally, without using Pinecone's embedding inference. [Current SDK migration and schema reference](https://sdk.pinecone.io/python/migration/v10-migration.html).

## What was tested

All **127 automated tests passed**, including 13 ingestion tests with simulated Pinecone responses. They cover stale sources, invalid vectors, model/region mismatch, changed remote records, incomplete acknowledgements, delayed visibility, default preview, missing credentials and safe error messages.

Separately, the actual authenticated run created the index, wrote 33 records, confirmed the namespace count and fetched all 33 IDs. Every passage and source field matched. Every vector matched within a small tolerance for Pinecone's numeric storage precision. The generated report is `data/processed/pinecone-indexing-report.json`, ignored by Git. The index host was saved in the ignored `.env`; no credential was displayed.

This establishes successful storage and source retention. It does **not** establish semantic retrieval quality, answer correctness, citation quality or production readiness.

## How to operate it

From the Week2 terminal, this command validates the local corpus and previews the proposed upload. It makes no Pinecone request:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.pinecone_ingest
```

Expected preview: 33 records, 11 eligible policies, 768 dimensions, approximately 134,885 bytes of record data and 373,184 bytes of JSON request data. These byte counts describe this corpus, not an invoice.

The actual upload has already been completed. The same command with `--upload` contacts Pinecone. An unchanged existing corpus is checked and verified without another application-level upload. This repeat behavior is covered by local tests; the recorded real run was the initial upload. Different data, model tags or record counts stop the command rather than silently replacing records. Policy updates and old-version removal need a separate, explained synchronization step. Do not run concurrent ingestion processes.

Common messages:

- **Prepare embeddings again:** local text, metadata, eligibility or model settings no longer match the saved vectors.
- **Existing index/records differ:** inspect the destination before changing or removing anything.
- **Verification did not finish:** a write may exist but not yet be visible; inspect before retrying. An older local report is not proof of the latest run's success.
- **Connection, permissions or limits:** check Pinecone access and usage in the console; raw provider errors are not printed.

## Cost and limitations

The user reports Starter (free); the published Starter plan includes allowances. Authentication and indexing are verified, but billing-plan details, remaining allowance and Builder credits are not independently verified. No subscription upgrade was made. [Pricing checked 2026-10-15](https://www.pinecone.io/pricing/).

Writing records consumes write units; keeping them consumes storage; verification fetches consume read units and transfer data. The first verification reported 4 read units. Stored-record size is estimated locally at 134,885 bytes; billed size and write usage were not returned or independently reconciled. See [the cost model](cost-model.md) for formulas and monitoring. Local embeddings have no external inference charge; local computing costs remain unmeasured.

The application does not loop over failed uploads. Pinecone SDK data requests have their own default retry policy; retries after transient failures can repeat usage. The control client disables automatic retries. Do not interpret our CLI as a spending cap.

The corpus is eligible for the fixed demo date **2026-10-15**. It is not automatically refreshed when policies change. The command is intentionally limited to one small request, at most 1,000 records and a conservative 1.9 MB of JSON.

## What happens next

Pinecone will return relevant passages and source details. The language model will later write an answer using that evidence:

```text
Question -> same Ollama model, query prompt -> Pinecone search
         -> relevant passages + metadata -> language model -> answer + citations
```

For example, a question about a secondary contact replacing a SIM may require both SIM and account-authority passages. Our next lesson will test whether search finds those passages before we add answer generation.
