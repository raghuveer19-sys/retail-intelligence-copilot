# Evaluation plan

## Current demo verification, 19 October 2026

The final displayed guidance meets the reviewed minimums for all **14 normal authored scenarios**, using selected live attempts plus a service-free check that the ten retained initial answers are unchanged under the final presentation logic. Four cases use separate corrected/recovery runs. This is not one fresh fourteen-case run, a model-classifier score, or a production-accuracy estimate. The separate SIM-only **E11 controlled check also passes**: absent authority and identity guidance does not become invented permission or a prohibition. Reviews are by Codex, not independent human reviewers.

Normal-case retrieval found **21 of 23 expected sections**. The two missing references are the general knowledge-action section in E09/E12; their retrieved billing/returns guidance and application capability boundary still support the reviewed answers. Retrieved evidence, final text and metadata citations are reviewed separately. The model's own coverage classifications remain imperfect, and some answers include extra background paragraphs.

Use `retail_copilot.evaluate_chat` for the current chat pipeline and `scripts/check_missing_evidence.py` for the current controlled component check. Their previews are read-only; explicit live runs create new results and do not overwrite earlier attempts. The older `retail_copilot.evaluate` command below is a preserved direct-generation experiment: it bypasses current chat routing, source-passage assembly and the application action guard. Its configuration snapshot alone does not prove those stages ran.

The case-linked scorecard is `data/processed/demo-normal-case-scorecard-2026-10-19.json`; the controlled result and review are `data/processed/demo-missing-evidence-2026-10-19*.json`. See [the readiness report](demo-readiness.md) for startup, automated checks, the separate live chat rehearsal and remaining limits. Original interrupted requests and failed earlier wording remain preserved.

`evaluation/cases.json` contains 15 initial telecom cases for direct, paraphrased, cross-document, exact-identifier, ambiguous, unsupported, action-request and outdated/conflicting-policy questions. All examples use fictional data. Expand to approximately 30 as retrieval and generation are built; add semantic conflicts across policies and adversarial source text during that expansion.

Each case stores its ID/category, question, fixed date, expected source document/section references, expected behaviour, reference answer, semantic must-include/must-not-include criteria, notes and result placeholders. Placeholders remain null in the authored specification. The evaluation runner now saves real retrieval, generated answers and measured usage in a separate results directory. Semantic reviews are separate artifacts; a structurally valid answer does not automatically pass. Phrase lists are semantic review criteria, not literal substring tests. The historical three-question retrieval measurements are retained below with their original dates.

E11 is deliberately different: `evaluation_mode: controlled_context` supplies only SIM-1024-v2 and withholds identity and authority guidance to test generation under partial evidence. The evaluation runner honours `context_document_ids`: it supplies all three complete eligible SIM sections directly, performs no search or reference lookup for this case, and labels the passages `controlled_context` with no similarity scores. Its answer is reviewed, but it is excluded from normal retrieval-recall calculations. The standalone retrieval baseline command still rejects controlled cases.

## Historical direct-generation runner

The runner connects the existing stages: question -> semantic retrieval and bounded policy lookup -> complete evidence pack -> local Ollama answer -> structure and source-ID checks -> separate semantic review. Expected answers and review criteria never enter the generation prompt.

From the Week2 Project folder, this command previews the configured experiment. It checks local files without contacting Ollama or Pinecone, generating an answer, or writing a report:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate
```

This command runs the 15 cases and saves the results. Missing normal-case retrieval uses local embeddings and Pinecone reads. Matching earlier retrieval results, including the saved E01/E04/E06 enhanced baseline, are reused after validation. The answering model runs locally, with no external generation fee; local computing and electricity costs are unmeasured. Pinecone usage can consume the account's read allowance, and any actual dollar billing must be checked in the account console.

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate --run --output-dir data/processed/evaluation-baseline
```

Repeat the same command to resume. The directory manifest records the cases, corpus, configuration, prompt and installed model identity. Matching completed cases are validated and reused without another model call. Changed experiment conditions require a new output directory, preserving the previous answers for comparison. `--case E04` selects one case; repeating `--case` selects a subset. The summary describes the cases requested by that invocation, so use the full command when producing the complete scorecard.

The generated directory contains:

- `manifest.json`: the experiment identity and settings needed to distinguish a rerun from a changed experiment.
- `E##-retrieval.json`: the evidence saved before generation, so a failed answering call need not repeat successful retrieval.
- `E##.json`: the unchanged retrieved evidence, constructed context, final model draft, rendered citations, model settings, token usage and timings. Context and prompt hashes link the answer to its exact inputs.
- `E##-failure.json`: a sanitized failure record when a case cannot finish. A failed call is not counted as a successful answer; provider error bodies and hidden thinking are not logged.
- `E##-review.json`: a separate review written after comparing the real answer with its cited passages and the [review rubric](evaluation-review-rubric.md). Each review identifies its reviewer and fingerprints the original case file. A Codex review is labelled Codex, not an independent human review.
- `summary.json`: execution outcomes, retrieval metrics and structural checks. Semantic scores remain pending until the separate reviews are completed and reported.

The runner reports original semantic section recall separately from recall after policy lookup. These measures concern finding expected passages, not using them correctly. The automated scorecard uses completed end-to-end cases as its stated retrieval denominator; controlled cases and questions without expected sections do not enter that ratio. Valid retrieval from any failed-generation case can be assessed separately.

Valid JSON, real source IDs and correctly rendered source metadata are automatic checks. Claim support, relevant conditions, completeness, response status and action boundaries require review of meaning. The review includes the whole rendered answer, including application-added limitation messages. A factual statement can have a correct citation while the answer still fails to address an ambiguous question or omits an essential condition. Optional extra details and usefulness improvements are recorded separately from the authored minimum criteria.

Usage reports distinguish fresh requests from reused historical evidence. Do not add cached historical read units to the current run's new usage. If generation fails after a successful retrieval, its known read units remain in the retrieval cache even when no completed-case usage row is returned. A request that fails before a complete validated response may have unknown usage; report that uncertainty instead of treating it as zero.

## Retrieval quality — did we find the right evidence?

For normal retrieval questions, measure expected-source recall at k: expected document/section references represented in the top k retrieved chunks divided by the number of expected references. A document-level hit alone may miss the needed section. Also report precision among returned chunks, exact-policy lookup success and excluded-document leakage. `top_k` means the maximum number of candidate passages requested. For cases with no expected sources, recall is undefined; report clarification or evidence-rejection behaviour separately. Some unsupported cases expect a source that explains the knowledge gap, such as missing roaming prices.

## Answer quality — did we use the evidence correctly?

Assess factual correctness, support for every substantive claim, valid citations, completeness, clarification of ambiguity, refusal to invent missing facts and preservation of the guidance-only boundary. A citation is valid only if its ID maps to actual retrieved metadata; separately assess whether that passage supports the claim.

Document instructions must not change system behaviour. Add adversarial source text and prompt-injection cases before any real-data or deployment discussion.

## Current results

The completed 2026-10-18 real baseline and its separate Codex reviews are documented in [First real answer evaluation](answer-evaluation.md). The baseline passed 6/15 overall reviews while all 15 answers passed structural checks. A completed fifteen-case comparison using the same evidence and model passed 7/15, but the broader instructions were rejected because E11 changed missing evidence into an invented prohibition; E12 also lost a previously included return condition. The higher aggregate count did not justify that regression. The report keeps retrieval, answer support, completeness, usage and latency separate.

A subsequent **narrow ambiguity-instruction test** started from the original prompt and changed only its ambiguity paragraph, as requested by the user. Of the three targeted cases, E01 retained its pass, E07 still guessed the SIM topic instead of clarifying, and E11 lost the baseline's insufficient-evidence status. It was rejected and the active configuration restored to the original prompt. Unlike the broader experiment, narrow E11 made no invented prohibition. An additional ambiguous probe was prepared but its inference was cancelled; it was not tested. This experiment has no fifteen-case score.

A separate **prompt-format E07 experiment**, using the narrow instructions and repeating the actual question after unchanged evidence passages, also failed: it returned four SIM policy claims with `supported` status and no clarifying question. The placement change was not retained and no application-code change was adopted. The original prompt already contains the requested clarification rule, but stronger wording and question placement did not make the model follow it reliably. Full experiment details, measured usage and rejection reasons are in [the answer-evaluation report](answer-evaluation.md).

At the end of those historical prompt experiments, `answering.md` was restored and pre-retrieval ambiguity handling had not yet been implemented. The current chat now uses `answering-grounded-v2.md`, bounded question resolution, explicit clarification handling and source-passage assembly. The historical probes alone did not establish those later behaviors; consult the current demo verification above.

**Runner implementation, 2026-10-18:** All 234 automated tests passed. These include simulated generation/evaluation calls, recovery using saved evidence, changed-experiment rejection, controlled-context handling and preservation of the authored case file. Automated tests establish these implementation behaviours; they do not establish the real model's answer quality. Both completed fifteen-case runs, the three-case narrow wording test and their Codex semantic reviews are saved separately in the evaluation results directories. The separate single-case prompt-format probe is also recorded; it did not resolve the ambiguity failure.

**Answering preparation, 2026-10-17:** All 195 automated tests passed, including 18 new tests using hand-written drafts. The actual E04 preview prepared separate instructions and evidence messages, with allowed IDs S1–S8 and 8,991 message-content characters. A copied-source demonstration rendered S7 using retrieved metadata; S99 was rejected. These checks ran with network connections blocked and preserved previous artifacts. No model answer or new retrieval result was produced.

Validation establishes draft structure, field/size limits, per-claim source-ID membership and citation metadata mapping. It does not establish semantic citation correctness, groundedness, appropriate status classification or action-boundary compliance. Deliberate wrong-claim tests document that a real source ID can pass while the cited passage does not support the claim; `claim_support_checked` and `action_claims_checked` remain false. Empty context has a fixed insufficient-evidence path. Model behavior on partial/conflicting evidence, action requests and prompt injection still needs live evaluation after integration. See [answering instructions](answering-instructions.md). Authored evaluation-result placeholders remain unchanged.

**Context preview, 2026-10-17:** All 177 automated tests passed, including 19 new context checks. Local checks of the saved E01/E04/E06 results preserved every selected chunk ID and complete passage. Pack counts were 8/8/5, with 5,238/5,266/3,285 formatted characters. The saved E04 preview includes source labels and their registry. Network connections were blocked during this check; no fresh retrieval-quality result is claimed.

Tests establish source mapping, unchanged content, duplicate handling, limits without truncation, empty/missing evidence notices, output preservation and independence from expected evaluation answers. They do not establish relevance selection, evidence sufficiency, generated citation correctness or answer quality. E06 reports IDV-1001 and ESIM-1001 as mentioned but unrepresented policies. No missing-reference notice does not prove completeness. See [the context lesson](context-construction.md). Earlier measured retrieval results follow with their original test counts.

On 2026-10-15, all 127 automated tests passed. The real Pinecone ingestion separately verified 33 stored IDs, exact text/source fields and vector values. Its fetch reported 4 read units. These are ingestion results, not semantic-search scores or answer-quality results; the evaluation case result fields remain unmeasured.

On **2026-10-17**, all 144 automated tests passed, including 17 query/retrieval checks. A separate real baseline used `embeddinggemma:300m`, the original model digest/corpus, cosine similarity and `top_k = 4`, at policy date 2026-10-15.

| Case | Category | Expected section recall at 4 | Missing expected source |
| --- | --- | --- | --- |
| E01 | Direct | 1/1 (100%) | None |
| E04 | Paraphrased | 2/3 (66.7%) | IDV-1001-v1 / training_id |
| E06 | Exact identifier | 1/2 (50%) | SIM-1024-v2 / appointments |

No excluded source appeared in accepted results. Each search returned four candidates and reported 1 read unit. Model/corpus identifiers, evidence, scores, tokens and timings are in the generated report. These three measurements are not overall accuracy or production readiness. Relevance precision, completeness detection, remaining cases and generated-answer evaluation are not yet measured. See [the lesson](retrieval.md).

**Follow-up on 2026-10-17:** Temporarily repeating the same three questions at k=8 produced E01 1/1, E04 2/3 and E06 2/2. E06's missing appointments section was rank 6; E04's training-ID section remained absent. A direct fetch verified that the latter record exists with correct text/metadata. The first four IDs matched the baseline in all cases. Larger candidate count helped one gap but did not resolve the other, so the default stays 4. This added 3 search read units plus 1 diagnostic fetch unit. See `data/processed/retrieval-top-k-8.json` and [the experiment details](retrieval.md). Application code was unchanged; the earlier 144-test result was not rerun or relabelled as a new test run.

**Policy-lookup enhancement, 2026-10-17:** All 158 automated tests passed after adding optional bounded lookup. Repeated the same E01/E04/E06 questions at semantic top_k 4 with `--follow-references`. Question/model/corpus/input/date matched the original baseline, and the first four IDs and scores were identical. Original baseline and k=8 reports were verified unchanged.

| Case | Original expected sections found | After lookup | Total returned passages | Added fetch read units |
| --- | --- | --- | --- | --- |
| E01 | 1/1 | 1/1 | 8 | 1 |
| E04 | 2/3 | 3/3 | 8 | 1 |
| E06 | 1/2 | 2/2 | 5 | 1 |

This is expected-source recall over **semantic results plus lookup**, not recall at four. Enhanced reports leave `expected_source_recall_at_k` null and use `expected_source_recall` with a separate measurement scope. Fetched passages have no similarity scores. The run consumed 3 search plus 3 fetch read units and 66 local query tokens. Passage words increased from 502 to 826. E01 illustrates extra retrieval without measured recall benefit; precision is still unmeasured. Retain the feature as opt-in, with default top_k 4. Three successful expected-source checks do not establish general evidence completeness or answer accuracy. See [the lesson and timing table](policy-lookup.md), `data/processed/retrieval-policy-lookup-baseline.json` and its separate comparison report.

Record model names, embedding version, corpus version, date, retrieval settings, per-case outputs, usage and latency for each live evaluation. Keep controlled-context generation results separate from end-to-end results. The initial 15 examples are a teaching baseline, not evidence of production readiness.

The following scorecard records the **historical 2026-10-17 retrieval and preparation baseline**. Its unmeasured answer-quality cells describe that earlier stage, not a claim that the current runner cannot generate or review answers.

| Business question | Measurement | Current result |
| --- | --- | --- |
| Did we find the needed evidence? | Expected-source recall, with retrieval scope stated | Original top 4: 1/1, 2/3, 1/2; optional lookup: 1/1, 3/3, 2/2 across 8, 8, 5 passages; precision unmeasured |
| Does the answer address the question? | Relevance and completeness | Not measured |
| Is every substantive claim supported? | Groundedness review against supplied passages | Not measured |
| Can the user verify the citations? | Correct retrieved reference plus supporting content | Registry mapping/rendering tested with hand-written drafts; semantic support and real model citations unmeasured |
| Does it handle uncertainty and action requests? | Clarification, insufficient-evidence and guidance-only checks | Not measured |
| How long does it take? | Embedding, search and optional fetch timing separately | Lookup run: searches 0.32–1.24s; embeddings 1.22–1.72s; fetches 0.29–0.34s; not a benchmark |
| What does it cost? | Actual usage and applicable account rates | Original baseline 3 RU; separate lookup run 6 RU; each run 66 local query tokens; dollar billing unreconciled |
