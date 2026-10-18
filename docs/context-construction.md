# Context construction: prepare an evidence pack

Built and checked locally on **2026-10-17**, using saved retrieval at the fixed fictional policy date **2026-10-15**.

## What context means

**Context** is the information supplied to a language model for a particular question. Here we prepare the question and selected policy passages, with source labels. Imagine handing a colleague a folder containing the question and the documents they should consult when drafting a response.

Finding a document and preparing that folder are different steps:

```text
Already built: question -> embedding -> Pinecone search -> optional policy lookup
This lesson:   saved passages -> validate -> remove duplicate IDs
                             -> retain whole sections -> label sources -> preview pack
Later:        evidence pack + answering instructions -> model -> checked answer/citations
```

This lesson does not call an answering model. The pack is evidence data, not a complete generation prompt. Instructions about grounding, insufficient evidence, action requests and treating source text as data are prepared in the following [answering lesson](answering-instructions.md).

## What goes into the pack

The default example is E04, the saved question:

> My phone and SIM were stolen. What checks would I need before getting a replacement?

The earlier search plus policy lookup returned eight passages. Our initial selection rule is **keep every validated, unique candidate in its original order**. We have not demonstrated a reliable relevance cutoff or reranker, so we do not discard low-scoring sections or reference-fetched passages with no score. This preserves evidence; it does not establish that every retained passage is necessary.

The builder:

1. Reads the configured saved retrieval report. It uses the case label E04 to find the result, but never uses expected sources, reference answers or evaluation scores to choose evidence.
2. Revalidates the local corpus, including source eligibility, exact text/metadata and saved model/corpus identity. It checks the result's policy date and destination against that snapshot. This is a local check, not a fresh inspection of Pinecone or its current remote state.
3. Rebuilds LangChain `Document` containers from the returned passages. Unknown, archived, incomplete or changed sources stop preparation.
4. Removes repeated copies of the same chunk ID only when the copies agree. Different IDs remain separate even if their text happens to match. Conflicting copies stop preparation.
5. Keeps every selected section intact. The default limits are ten sources and 12,000 characters for the complete formatted pack. Exceeding either limit stops preparation; it does not silently drop passages or cut off conditions.
6. Assigns labels S1, S2 and so on, and builds a **source registry**: a lookup table linking each label to its actual chunk ID and retrieved metadata.
7. Saves a separate preview and prints its source list. The original retrieval and embedding reports remain unchanged.

## The actual stolen-SIM example

| Label | Included section | Original source |
| --- | --- | --- |
| S1 | Appointments and scope | SIM-1024-v2.json |
| S2 | Required checks | SIM-1024-v2.json |
| S3 | Delegated SIM authority | AUTH-1001-v1.json |
| S4 | Account roles | AUTH-1001-v1.json |
| S5 | Identity and authority are different | IDV-1001-v1.json |
| S6 | Missing or mismatched details | IDV-1001-v1.json |
| S7 | Training identification | IDV-1001-v1.json |
| S8 | Missing authority evidence | AUTH-1001-v1.json |

S2 says that identity and account-authority requirements must be followed. S7 contains the fictional training-identification requirement. Both complete passages are preserved.

The link for S7 is created by code from retrieved metadata:

```text
[S7]
  -> IDV-1001-v1:training_id:section-v1
  -> IDV-1001-v1.json / Training identification
```

A future model can refer to S7; the application now has source-ID checks and citation rendering tested with hand-written drafts in the [answering lesson](answering-instructions.md). **A valid label does not prove the cited passage supports a claim.** Semantic claim support and real model responses remain untested. Labels apply within one pack; S7 is not a permanent global document identifier.

The evidence text is formatted as JSON, a structured text format, with separate question and source fields. It includes passage text and identifying details, but not vectors, similarity scores, evaluation answers or credentials. Search scores and lookup provenance remain in the preview's registry for inspection. A fetched passage's score remains null. JSON preserves boundaries and quotation marks; it is not, by itself, a defense against malicious instructions in source text.

## Size and completeness are different checks

The E04 pack has **eight sections and 5,266 characters**, below the 12,000-character limit. Its passages contain 312 words. Character count includes the question, source details and formatting. **Neither characters nor words are model tokens.** We have not chosen and integrated the answering model, so its token count and context-window fit are unmeasured. This character limit is an application guard, not a model limit or spending cap.

The builder also lists explicit policy IDs mentioned in the question/passages that have no policy passage represented in the pack. It does not fetch them. This is a limited notice, not a comprehensive dependency or sufficiency check: one section from a policy may still omit a needed requirement, and dependencies can be implicit.

All three saved examples were checked locally, preserving the original IDs and complete text:

| Saved case | Sources | Formatted characters | Passage words | Named policies with no passage |
| --- | --- | --- | --- | --- |
| E01: appointment | 8 | 5,238 | 312 | None detected |
| E04: stolen-SIM checks | 8 | 5,266 | 312 | None detected |
| E06: policy SIM-1024 | 5 | 3,285 | 202 | ESIM-1001, IDV-1001 |

These are packaging checks on saved retrieval, not new live searches or new retrieval-quality scores. E06 demonstrates why finding the expected SIM sections does not automatically supply every referenced requirement. All nonempty packs retain `evidence_sufficiency: not_assessed`, including those with no missing-reference notice. An empty result produces no source labels and is explicitly marked `no_retrieved_evidence`. Nothing here confirms real customer eligibility or transactional authority.

## Run the preview

From the Week2 Project terminal, this command reads the saved E04 result, checks the local sources, builds the pack and prints the full evidence text:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.context --show
```

Expect `Context construction: OFFLINE PREVIEW | E04`, eight labelled sections and 5,266 characters with the current saved example. It saves `data/processed/context-example.json`. Inside that file, `context_text` is the prospective evidence input and `source_registry` maps the labels to sources. Run without `--show` for the shorter source-list display. Neither Ollama nor Pinecone needs to be running for this command.

The `--case` option selects another case already present in the saved report. It does not search again. Reruns replace the generated context preview, while preserving input reports. Missing input files, changed corpus/model/date, inconsistent source copies or excessive size stop preparation. Inspect the problem before rerunning; an earlier preview may remain, so check its timestamp.

## Validation, costs and next step

Added `src/retail_copilot/context.py`, `[context]` settings and 19 context tests. **All 177 project tests passed.** Checks cover exact text and metadata, source labels, duplicates, changed/excluded sources, bounds, empty results, missing-reference notices, unknown/invented scores, output protection and keeping expected evaluation answers out of the pack. A text-escaping test establishes serialization behavior, not language-model resistance to prompt injection.

The actual preview and the three-case local check completed with network connections blocked. Hash checks confirmed the prior retrieval and embedding files were unchanged. Preparation made **zero service calls and incurred no external request charge**. Local computing costs are unmeasured; the earlier retrieval runs retain their own usage. No prices were changed or newly assumed in `config/pricing.yaml`.

Later, sending the pack to a hosted answering model can incur input-token charges, with output-token charges for its response. Measure the full prompt using the chosen model's tokenizer/usage, including answering instructions, rather than using this character count. Model choice, verified rates and generation limits remain future work.

The following [answering lesson](answering-instructions.md) now implements instructions, response-format/source-ID checks and citation rendering with hand-written drafts. A generation model is not connected yet. Semantic relevance selection, reliable evidence-sufficiency assessment, conflicting guidance and broader answer evaluation remain open work.
