# Preparing a Pinecone record locally

Checked on 2026-10-15. This lesson describes our local vector mapper. All 33 real records have since been uploaded and verified using the current SDK's named-field format; see [actual indexing](pinecone-indexing.md). The table below is the intermediate vector mapping, not the final SDK 10 document request.

For precomputed vectors, Pinecone accepts `id`, `values` and optional `metadata`. Our application requires metadata to retain the original passage and source details. [Official upsert format](https://docs.pinecone.io/guides/index-data/upsert-data).

| Local result | Pinecone field | Purpose |
| --- | --- | --- |
| `chunk_id` | `id` | Identify the passage |
| `vector` | `values` | Compare with a question vector |
| `text` | `metadata.text` | Preserve exact evidence |
| Source metadata | Other fields inside `metadata` | Preserve policy, version, section and filename |

```text
Local embedding result -> to_pinecone_record -> id + values + metadata
                            implemented         intermediate vector format
```

Metadata must be flat: strings, numbers, booleans or lists of strings, without nested objects or null values. The mapper omits optional nulls such as an unspecified `effective_to`, but rejects missing required source labels. Dates remain strings; future date filtering must respect supported database operators. [Metadata rules](https://docs.pinecone.io/guides/index-data/indexing-overview#metadata).

The mapper checks configured provider/model/dimensions, finite nonzero vectors, source labels, conflicting text/ID fields and metadata types. It retains independent copies, includes passage text in a conservative 40,000-byte local ceiling and rejects oversized records without truncating them. Pinecone documents a 40 KB metadata limit. This is not validation of every remote API constraint, source authenticity, current eligibility or retrieval quality. Source freshness must be rechecked before upload. [Data modeling](https://docs.pinecone.io/guides/index-data/data-modeling).

Usage, timing and cost details remain in the local result. The namespace `telecom-demo-v1` is a corpus boundary selected on the upload request, not a record field or approval filter. It now contains 33 verified records.

Nine dedicated tests passed, including all 33 eligible chunks with dummy vectors, text/source retention, independent copies, missing-source rejection, malformed vectors, nested metadata and UTF-8 size boundaries. Test vectors were never uploaded or saved as real embeddings. The actual one-chunk Ollama result also passed local format checks.

## Actual indexing sequence

1. Generated all 33 real corpus embeddings locally.
2. Privately configured the Pinecone key and authenticated successfully. The user reports Starter; billing details and remaining quotas are not independently verified.
3. Created `retail-copilot-week2` in AWS `us-east-1`, matching 768 dimensions and cosine similarity.
4. Uploaded eligible records and verified their count, fetched text/source fields and vectors. Retrieval is next.

The user reports Starter, with Builder credits pending. Week2 has a working Pinecone key. The public Starter plan is free within limits; actual remaining quota and billing details have not been inspected. No subscription upgrade was made and credits are not assumed active. [Pricing checked 2026-10-15](https://www.pinecone.io/pricing/).

Local formatting incurs no API charge. Future uploads, storage and queries can consume allowances or create charges. Upserting an existing ID replaces that record within the namespace; stable IDs do not prevent repeat write usage or remove obsolete versions. [Upsert behavior](https://docs.pinecone.io/guides/index-data/upsert-data).
