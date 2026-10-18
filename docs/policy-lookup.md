# Following explicit policy references

Implemented and measured on **2026-10-17**. The fictional policy date remains **2026-10-15**. This is an optional retrieval improvement; answer generation is still pending.

## Why we built this

Semantic search finds passages with related meaning. Our stolen-SIM question found the SIM checks passage, but missed the identity requirements it refers to. Increasing the candidate limit from four to eight still missed that identity section. A separate direct fetch confirmed it was stored correctly.

**Policy lookup** means finding stored sections by their known identifiers. Imagine reading a procedure that says "consult IDV-1001" and then opening that policy. This helps only when the reference is explicit and the policy is present and approved; it is not a general understanding of every dependency.

```text
Question -> local question embedding -> Pinecone semantic search (up to 4)
    -> validate passages and source details
    -> optional policy lookup:
         Question names policy IDs? Use those IDs.
         Otherwise: read policy references in the original search passages.
    -> fetch missing approved sections once -> validate returned sources
    -> display original matches + separately labelled fetched passages

LATER: select sufficient relevant evidence -> construct context -> generate answer
```

## Step by step

1. Run the existing semantic search unchanged. Preserve each original passage, rank and score.
2. Look for complete policy IDs in the question. For "What does policy SIM-1024 say?", select SIM-1024. Question IDs take precedence: this run does not also expand references from the passages.
3. If the question contains no policy ID, inspect only the original returned passage text. For the stolen-SIM question, the SIM checks passage names IDV-1001 and AUTH-1001.
4. Resolve those policy IDs to section IDs in our validated eligible corpus. The local catalogue identifies what to request; passage content must still be fetched from Pinecone and validated. No locally invented replacement evidence is added after a failed fetch.
5. Use the configured limits: at most **two policies and six additional sections**. Skip a policy if all its missing sections will not fit; report the skipped ID. Sections already retrieved are not fetched twice. Policies are considered in their order of discovery.
6. Make at most one fetch request per question, requesting text/source fields without vectors. Reject missing/unexpected records, wrong namespaces or changed text/metadata. Source records become LangChain `Document` containers before reporting.
7. Do not follow references found in the newly fetched passages. This is **one-step expansion**, not a recursive chain of lookups.
8. Save the result separately from the original baseline. Each added passage records why it was selected and which original chunk named its policy, where applicable.

Unknown policy IDs are reported. Version-specific requests such as SIM-1024-v1 are marked unsupported, rather than silently converted into the current version. An unknown/version-specific question ID does not trigger fallback expansion from unrelated semantic hits. Ordinary semantic candidates may still be displayed, but no answer is generated from them.

## Why fetched passages have no similarity score

A **similarity score** measures the comparison between the question vector and a passage vector during search. A direct ID fetch performs no such comparison. Copying the SIM passage's score to an identity passage would invent a measurement.

| Passage | How it was found | Score shown |
| --- | --- | --- |
| SIM checks in the stolen-SIM example | Semantic search | Its actual score, 0.4897 |
| IDV training identification | SIM checks explicitly names IDV-1001 | No similarity score |

No score does not mean no value: the identity passage supplies a missing requirement. The result records its **provenance**, meaning the source and path by which we obtained it. Display order after the original search results is not a new relevance ranking.

## Measured comparison

The same questions, model digest, exact embedding inputs, corpus hash, namespace, policy date, cosine metric and top_k 4 were used. All first-four IDs and scores matched the original baseline. The original baseline and k=8 reports were verified unchanged; settings were unchanged during the live comparison.

| Case | Original top 4: expected sections found | After optional lookup | Passages before / after | Passage words before / after |
| --- | --- | --- | --- | --- |
| E01: appointment | 1/1 | 1/1 | 4 / 8 | 173 / 312 |
| E04: stolen phone/SIM checks | 2/3 | 3/3 | 4 / 8 | 173 / 312 |
| E06: policy SIM-1024 | 1/2 | 2/2 | 4 / 5 | 156 / 202 |

E04 recovered `IDV-1001-v1:training_id:section-v1`. E06 recovered `SIM-1024-v2:appointments:section-v1`. E01 gained no measured source-recall benefit despite more text. Total passage words rose from 502 to 826; these are words, not tokens or billed transfer size.

**Expected-source recall** is the fraction of authored expected sections found. For expanded results, we do not label this "recall at four": more than four passages were returned. The report sets `expected_source_recall_at_k` to null and uses `expected_source_recall` with scope `semantic_plus_policy_lookup`.

Finding all expected sections in three cases does not establish complete answers or production accuracy. Precision (how much of the returned evidence is useful), broader case coverage, claim support and answer quality remain unmeasured. E06 fetches the named SIM policy only; identity dependencies may still be absent. `lookup_complete_within_scope` means no selected lookup was unknown, unsupported or skipped. It **does not mean sufficient evidence to answer or confirm eligibility**.

## Usage and timing

| Case | Local query tokens | Embedding seconds | Search seconds | Fetch seconds | Reported search / fetch read units |
| --- | --- | --- | --- | --- | --- |
| E01 | 20 | 1.72 | 1.24 | 0.34 | 1 / 1 |
| E04 | 26 | 1.22 | 0.35 | 0.29 | 1 / 1 |
| E06 | 20 | 1.23 | 0.32 | 0.33 | 1 / 1 |

This run used **66 local query tokens and 6 reported Pinecone read units**, separate from earlier runs. Fetching four, four and one missing records respectively reported one read unit each. Local Ollama has no external inference charge; hardware/electricity costs are unmeasured. Dollar billing and remaining Starter allowance are not independently verified.

Each lookup can add a recurring read request and response transfer. Published fetch metering is one read unit per ten returned records, rounded up with a one-unit minimum per request; there is no fetch when nothing is missing. Monitor API usage and the Pinecone console. Bounds, de-duplication and opt-in use limit needless requests; caching is not implemented. SDK retries can add usage, including on failures. [Official metering, checked 2026-10-17](https://docs.pinecone.io/guides/manage-cost/understanding-cost). The implementation uses the current [SDK documents fetch API](https://sdk.pinecone.io/python/migration/v10-migration.html).

The fetch times above measure that additional call. The isolated runs do not establish overall speed improvements or typical latency. No index write, plan change or generation request was made.

## Try one example

From the Week2 Project terminal, with Ollama running, this command searches the fictional stolen-SIM question and follows explicit references once. It makes one search and, with the current corpus, one fetch:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.retrieve "My phone and SIM were stolen. What checks would I need before getting a replacement?" --follow-references
```

Expect four semantic hits followed by four fetched sections, including Training identification. Fetched passages show "no similarity score". The result is saved to `data/processed/retrieval-policy-lookup-example.json`. Running without `--follow-references` keeps the original semantic-only behavior.

The measured three-case run used `--baseline --follow-references` and saved `data/processed/retrieval-policy-lookup-baseline.json`. A local comparison saved `data/processed/retrieval-policy-lookup-comparison.json`, including preserved-file hashes. Repeating a command consumes fresh read usage and replaces its corresponding generated report. Failed runs leave any previous report, so check timestamps.

## Files and validation

| File | Purpose |
| --- | --- |
| `src/retail_copilot/policy_lookup.py` | Plan bounded lookups, fetch, validate and record provenance |
| `src/retail_copilot/retrieve.py` | Optional flag, separate output, display and correctly scoped evaluation |
| `config/settings.toml` | Limits and separate output paths |
| `tests/test_policy_lookup.py` | 12 offline checks for lookup behavior and failures |
| `tests/test_retrieval.py` | 19 retrieval tests, including optional CLI integration and baseline protection |

All **158 automated tests passed**. The first full-suite attempt stalled and was interrupted; the completed rerun with normal temporary-folder access passed. Offline tests cover bounds, duplicate prevention, no recursive expansion, unknown/versioned IDs, excluded policies, changed/missing source data, score preservation, unknown usage and safe output separation. The three real searches/fetches are separate evidence of the observed retrieval improvement.

**Decision:** Retain lookup as an optional, measured enhancement. Keep default semantic top_k 4 while broader relevance checks are pending. The next lesson, [context construction](context-construction.md), now implements an offline evidence pack that preserves whole validated candidates and adds source labels. Semantic relevance selection is still unmeasured: more retrieved text is not automatically better context.
