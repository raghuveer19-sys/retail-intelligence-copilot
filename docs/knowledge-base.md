# Phase 1: fictional telecom knowledge base

Date: 2026-10-15. This phase builds the evidence library, before search or generation. All content was authored for this demonstration; it is not a real provider's policy or a legal requirement. No customer records, account numbers, contacts, activation codes or real identity documents were used.

## What goes in and what comes out

```text
12 fictional JSON documents with named sections and source details
    -> validate metadata, dates, identifiers and section structure
    -> select approved documents effective on the chosen date
    -> display 11 eligible documents; explain the excluded archive
```

JSON stores named fields, such as `title` and `version`, in a format Python can read. One file holds one document version. A corpus is the collection of documents used by the application. Metadata means information describing a source; it is not itself proof that the policy is correct.

The fixed demo date is 2026-10-15. Only local files and Python are used. There are no embedding, Pinecone or answer-generation calls and no API charges in this phase.

## The corpus

| Policy ID | Topic | Current document | Example learning use |
| --- | --- | --- | --- |
| SIM-1024 | Physical SIM replacement | SIM-1024-v2 | Optional appointments and prerequisite policies |
| ESIM-1001 | eSIM preparation | ESIM-1001-v1 | Device readiness versus actually activating a service |
| IDV-1001 | Fictional identity requirements | IDV-1001-v1 | Identity is separate from account authority |
| ROAM-1001 | Roaming preparation | ROAM-1001-v1 | Missing country prices must remain unknown |
| BILL-1001 | Billing enquiries | BILL-1001-v1 | Explain a process without waiving a bill |
| RET-1001 | Device returns and faults | RET-1001-v1 | Separate change-of-mind rules from fault assessment |
| COL-1001 | Click and collect | COL-1001-v1 | Collection window and missing substitute-collector rules |
| PLAN-1001 | Fictional consumer plans | PLAN-1001-v1 | Compare stated allowances without inventing prices |
| AUTH-1001 | Account authority | AUTH-1001-v1 | Check explicit delegation scope |
| TECH-1001 | Connectivity troubleshooting | TECH-1001-v1 | Basic checks without claiming live outage knowledge |
| KNOW-1001 | Evidence handling | KNOW-1001-v1 | Insufficient evidence, conflicts and action limits |
| SIM-1024 | Archived SIM guidance | SIM-1024-v1 (excluded) | Older appointment requirement must not become current guidance |

The earlier general-retail `data/policies.json` was superseded by `data/knowledge/`. The active loader now expects one document object per JSON file. It does not accept the earlier list-of-records format.

## Metadata design

The schema is the set of fields and rules a valid document must follow. These fields were designed before any cloud ingestion; the source files and loader implement the local schema now.

| Local field | Why it exists | Role |
| --- | --- | --- |
| `policy_id` | Stable policy identity across revisions, such as SIM-1024 | Exact-ID lookup; group versions |
| `document_id` | Specific policy version, such as SIM-1024-v2 | Unambiguous reference and deduplication |
| `title` | Human-readable name; becomes `metadata["document_title"]` in the container | Source labels |
| `category` | Topic such as sim_replacement or account_authority | Coverage reporting; possible future filters |
| `customer_segment` | Scope of the guidance; consumer in this corpus | Scope checks; possible future filters |
| `product` | Product covered, such as physical_sim | Possible future filters |
| `process` | Activity described, such as sim_replacement | Possible future filters |
| `version` | Revision label; positive integer stored as text | Governance and citations; not automatically a priority rule |
| `status` | approved, draft or archived | Evidence eligibility |
| `effective_from` | First day the policy applies | Date eligibility, inclusive |
| `effective_to` | Last applicable day, or null for open-ended | Date eligibility, inclusive |
| `owner` | Fictional team responsible for reviewing guidance | Governance and referral |
| `review_date` | Reminder for the next review | Governance; not automatic expiry |
| `synthetic` | Explicit declaration that content is fictional | Required demonstration safeguard |
| `disclaimer` | Human-readable fictional and guidance-only notice | Visible scope and limitations |
| `sections[].section_id` | Stable lowercase section identifier | Future passage references |
| `sections[].heading` | Human-readable section name | Future citation labels and chunking boundaries |
| `sections[].text` | Knowledge content for that section | Future evidence text |
| `source_file` (derived metadata) | Actual filename read by the loader | Source tracking; never trusted from a supplied JSON value |
| `chunk_id` (generated locally) | Specific passage after splitting, e.g. SIM-1024-v2:checks:section-v1 | Repeatable passage identity; future retrieval and citation linkage |

Identifiers illustrate a hierarchy: `SIM-1024` identifies the policy, `SIM-1024-v2` identifies its version, and `appointments` identifies a section within that version. Section IDs need only be unique inside their document; a complete reference includes the document ID. The local preparation command now combines document ID, section ID and strategy as `SIM-1024-v2:appointments:section-v1`. The ID stays the same across unchanged reruns; it identifies the passage location and method, not a guarantee that text has never been edited.

Do not include API keys, personal contact details, identity images, actual account information or activation codes in text or metadata. Do not add an unvalidated confidence probability or treat a synthetic flag as proof that arbitrary imported text is safe. The content was reviewed as deliberately fictional; automated checks verify declarations and structure, not personal-data detection.

## The LangChain Document container

At the user's request on 2026-10-15, loaded policies and chunks now use `Document` from the LangChain library. A container is a standard way to keep related information together. It does not read files, decide which policies are approved or create embeddings on its own.

```python
from langchain_core.documents import Document
```

| Field | Loaded policy | Section chunk |
| --- | --- | --- |
| `page_content` | All section bodies joined with blank lines | One section's exact loaded text |
| `metadata` | Source filename, policy/version, dates and other details; local `sections` structure | Copied source details plus this section's ID, heading and word positions |
| `id` | For example, `SIM-1024-v2` | For example, `SIM-1024-v2:checks:section-v1` |

For an actual chunk named `chunk`, `chunk.page_content` reads the guidance and `chunk.metadata["source_file"]` reads its source filename. Metadata still uses a Python dictionary (named fields), as required by LangChain's container. [Official Document reference](https://reference.langchain.com/python/langchain-core/documents/base/Document), checked 2026-10-15.

The loader validates the original JSON before creating each policy container. We retain named section boundaries in the policy's local metadata so our chunker can preserve them. This duplicates section text locally, but chunks omit that full `sections` collection; each carries only its own passage and source details. Metadata is copied independently so changing one chunk's nested metadata cannot change the source or sibling chunks. Treat validated text and metadata as read-only evidence during processing; the generic container does not prevent later edits or enforce our governance rules.

Dates are stored as YYYY-MM-DD strings and converted to Python dates for eligibility comparisons. Saved JSON retains its existing `chunk_id`, `text`, `word_count` and `metadata` fields. The runtime container and the file format serve different purposes; using LangChain does not require changing the source files or export format.

## Governance rules implemented now

1. Required text must be present. Each source must declare `synthetic: true` and have a disclaimer beginning `FICTIONAL TRAINING CONTENT.`.
2. Policy IDs use the form SIM-1024; document IDs must match policy ID and version. Duplicate document IDs stop loading.
3. Sections require a unique local ID, heading and non-empty text.
4. Dates use YYYY-MM-DD. End dates cannot precede start dates, and a review date cannot precede the effective start.
5. Current evidence must be approved and within its effective dates. Drafts, archives, expired versions and future-effective versions are excluded.
6. Archived versions stay excluded even when viewing an earlier date. This is a current-guidance demonstration, not a historical policy engine.
7. Two eligible versions of the same policy stop processing. We do not silently select the highest version number.
8. An overdue review produces a visible reminder but does not automatically expire the document. Approval withdrawal or an effective end date must explicitly remove eligibility.

Approval and ownership here are simulated training metadata, not sign-off from a real policy authority. Contradictions across different policy IDs still require content review and later answer evaluation; the version-overlap check cannot detect every semantic conflict.

## Preparing for Pinecone later

Our source sections are nested JSON. The local chunk export now attaches text and a metadata dictionary containing the source filename, section, document details and governance fields. It preserves a missing `effective_to` as JSON `null` for inspection; it is not a Pinecone payload. Pinecone metadata supports strings, numbers, booleans and lists of strings, not nested objects or null values; the documented metadata limit is 40 KB per record. Omit a missing end date in the future payload. Sources checked on 2026-10-15: [metadata format and size](https://docs.pinecone.io/guides/index-data/indexing-overview#metadata).

Keep readable dates in source documents. If server-side date range filters are introduced, encode comparison dates as numbers: Pinecone's ordering operators support numeric values. That conversion and metadata-size check must be implemented and tested before upload. [Filter operators](https://docs.pinecone.io/guides/search/filter-by-metadata)

The planned namespace `telecom-demo-v1` identifies this corpus revision. A namespace selects a partition of the index; a metadata filter selects eligible records within that partition. Neither is a substitute for account permissions. The name is recorded in settings, but no namespace or index has been created. [Namespaces](https://docs.pinecone.io/guides/index-data/indexing-overview#namespaces)

## Check and inspect

From the Week2 terminal, the validator reads the documents and reports which can support current guidance:

```powershell
uv run --no-active retail-validate
```

Expected first lines:

```text
Loaded 12 synthetic documents.
Approved and effective on 2026-10-15: 11.
Excluded from current evidence: 1.
```

The Streamlit viewer displays each eligible document's sections, real filename, ID, version, owner and dates. The exclusion panel explains why the archive is absent. It is a document browser; it cannot yet answer questions.

Common errors: a missing-metadata message means a required source detail is blank; duplicate IDs mean sources would be ambiguous; conflicting approved versions mean the dates/approval state need resolution. Fix the source evidence rather than bypassing these checks.

## Learning and validation result

The user correctly selected the current approved policy over a closely matching archive. We explained why eligibility takes precedence over similarity. The policy-versus-document distinction also appeared during validation: initial evaluation references omitted version suffixes; the tests caught them and the references were corrected.

After correction, 27 automated tests passed: 16 document checks, 3 evaluation-specification checks and 8 credential-readiness checks. Three viewer scenarios passed: the default library/source details, a date with no eligible evidence, and overdue review reminders. The 15 authored evaluation cases have unmeasured result fields; no retrieval or model-answer quality has been established.

Phase 2 provides [a reusable local comparison and chunk preparation command](chunking-experiment.md). Preparation saves 33 complete sections from 11 eligible documents, with repeatable IDs and source metadata. The LangChain container migration passed 52 tests and retained the export's content. Three viewer scenarios passed their assertions with a separate Windows cleanup permission error at exit. The later [local token report](embedding-preparation.md) passed the expanded 68-test suite and measured 1,404 tokens, all within the configured per-input limit. Cloud ingestion, request-wide checks and retrieval quality remain pending.
