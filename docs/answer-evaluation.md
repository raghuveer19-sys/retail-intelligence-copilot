# First real answer evaluation

Reviewed on **2026-10-18**, using the fixed fictional policy date **2026-10-15**.

The pipeline completed all 15 demonstration cases and produced valid answer structures and source references. A separate review of meaning passed **6 of 15 cases**. This difference matters: a program can correctly attach a real source while the answer omits an important condition or selects the wrong response type.

A second 15-case run with broader completeness instructions passed **7 of 15**, but those instructions were **rejected**: on the deliberately incomplete-evidence case, the answer changed uncertainty into an invented prohibition. A higher total pass count did not justify that worse decision. Later narrow wording and question-placement tests also failed to produce clarification. The original prompt is active again, and ambiguity handling remains unreliable for this model and configuration.

The reviewers were **Codex agents**, not independent human reviewers. These results describe a small fictional teaching set. They are not a production accuracy claim, a safety guarantee, or evidence that the model will behave the same way on other questions.

## What was tested

The experiment used `qwen3:4b-instruct` for local answers and `embeddinggemma:300m` for 768-number search vectors. Generation used temperature 0, a 16,384-token context setting and a 1,024-token output limit. The exact model digest, corpus identity, prompt hash and settings are saved in the [run manifest](../data/processed/evaluation-baseline/manifest.json) and individual case files.

Fourteen cases used semantic search with `top_k = 4`, followed by the existing bounded policy lookup. Three matching earlier retrieval results, E01/E04/E06, were reused; the other eleven normal cases performed fresh retrieval. E11 was a controlled experiment: it supplied only the three complete SIM-1024-v2 sections and deliberately withheld the identity and authority policies. It made no retrieval request and has no invented similarity scores.

All fifteen answers were generated during this run. The model received the question and its approved evidence, not the authored reference answer or review criteria. The original `evaluation/cases.json` and its null result placeholders remain unchanged.

Each saved case contains its actual passages, final draft, rendered citations, model settings, measured usage and timing. Each separate `E##-review.json` records the reviewer, a fingerprint of the unchanged case file, the actual cited passages, claim verdicts, completeness, response status and action-boundary findings. The [review rubric](evaluation-review-rubric.md) explains the distinctions.

## Retrieval results

Expected-section recall asks: **of the sections we expected to find for these questions, how many were returned?** It measures finding evidence, not answer quality.

| Measure | Result |
| --- | --- |
| Completed normal retrieval cases | 14 |
| Controlled case, excluded from retrieval recall | E11 |
| Normal cases with expected sections | 13; E07 is ambiguous and has no expected-source recall denominator |
| Expected sections found by original semantic top four | 17/23, or 73.9% |
| Expected sections found after bounded policy lookup | 21/23, or 91.3% |
| Questions with every expected section after lookup | 11/13 scored questions |
| Leakage of authored excluded documents | None observed |

The 23 expected references are **question-and-section pairs** across the scored cases, not 23 different source documents. E11 and E07 do not increase this denominator.

The remaining two missing references were the `KNOW-1001-v1 / actions` section in E09 and E12. Both cases already had relevant billing-limit evidence. Their answers correctly refused execution in the prose, but chose the wrong response status. Increasing the number of search results without examining this distinction would not address that generation failure. Retrieval precision and general evidence completeness are not established by these recall measurements.

## Answer review

All **15/15** answers passed JSON structure and source-ID checks. Those checks establish that the response can be read by the application and that its labels point to real supplied passages. They do not prove support for the claims or correct behaviour.

Codex reviewed 26 model claim items: **22 supported and 4 partially supported**. Some items contain multiple statements; these are not counts of individually separated factual propositions. The partial items contain overstrong wording or details that do not fully follow from their cited passages. An answer made only of supported statements can still fail because it is incomplete, irrelevant to the user's ambiguity, or uses the wrong response status.

| Case | Question focus | Overall review | Reason |
| --- | --- | --- | --- |
| E01 | Physical SIM appointment | Pass | Correctly says no appointment is required and cites the current section. |
| E02 | Fictional identification | Fail | Names the Training ID but omits the separate authority check and available expiry/name-matching conditions. |
| E03 | eSIM preparation | Fail | Gives supported readiness checks but does not explain that this library lacks the supported-model list. |
| E04 | Stolen phone and SIM | Fail | The authored minimum is present, but three compound claims are only partially supported; positive Training ID detail is also omitted. |
| E05 | Secondary billing contact | Fail | Opening authority wording is stronger than the cited source, and the supplied Fictional Training ID requirement is omitted. |
| E06 | Exact SIM-1024 policy | Pass | Summarises the current policy, optional appointment and identity/authority references without deciding eligibility. |
| E07 | “Can I replace it?” | Fail | Gives supported SIM guidance but assumes what “it” means instead of requesting clarification. |
| E08 | Canadian roaming price | Pass | Correctly abstains instead of inventing a price. The generic fallback could be more helpful by naming the approved destination/plan price-source step. |
| E09 | Waive an outstanding bill | Fail | Correctly refuses execution, but chooses `supported` instead of `action_not_supported` and omits the billing-guidance offer. |
| E10 | Older versus current appointment rule | Pass | Uses the current version 2 citation and correctly states that appointments are optional. |
| E11 | Missing authority evidence | Fail | Uses an appropriate insufficient-evidence response but does not identify the missing authority policy, as the controlled case requires. |
| E12 | Return window plus refund request | Fail | Gives supported return guidance and refuses a refund, but uses `supported` for a request that includes an action. Available return conditions are also omitted. |
| E13 | Collection window | Pass | Preserves seven calendar days and the ready-for-collection notice as the starting event. |
| E14 | Basic versus Plus data | Pass | Correctly compares the fictional domestic allowances, without invented prices or eligibility promises. |
| E15 | Mobile-data troubleshooting | Fail | Gives supported first checks but omits the authored no-live-outage-information limitation and available escalation. |

The overall pass count is **6/15**: E01, E06, E08, E10, E13 and E14. This review considers claim support, important conditions, expected behaviour and response status as well as the authored minimum phrases. E04 and E12 illustrate why satisfying the authored minimum alone does not establish an acceptable full answer.

The review includes application-added text, such as the fictional-demo label and insufficient-evidence fallback. It checks meaning rather than requiring literal wording from the reference answer. Extra useful details are distinguished from required content: for example, E13 does not fail merely because it omits escalation for an expiry the user never reported.

No review of these fifteen answers found a claim that the copilot had actually completed a transaction or identity verification. That observation does not remove the documented status, condition-preservation and completeness failures.

## Usage and time

| Measured item | This run |
| --- | --- |
| New Pinecone usage | 18 read units: 11 searches and 7 policy fetches |
| New local query-embedding input | 224 tokens |
| Local answer-generation input | 27,590 tokens |
| Local answer-generation output | 1,739 reported tokens |
| Successful local answer calls | 15 |
| Sum of answer-generation time | 882.53 seconds, about 14.7 minutes |
| Median answer-generation time | 56.27 seconds |
| Observed answer-generation range | 31.09–92.80 seconds |
| External answer-generation fee | USD 0; the model ran locally |

The reused E01/E04/E06 retrieval artifacts contain **historical** usage of 6 Pinecone read units and 66 local query tokens. That usage was not incurred again and is excluded from this run's new-usage totals. There were no failed execution cases in this baseline, so the runner's known limitation around accounting for requests before a failed generation does not leave a gap in these totals.

Pinecone dollar billing remains unreconciled; read units are measured usage, not an invoice. Local hardware and electricity costs are unmeasured. These timing observations describe this computer and run, not a general performance benchmark; they exclude any claim about time spent on manual semantic review. Long local response times are relevant to the later interface design.

## Completed comparison: broader instructions rejected

The broader `answering-completeness.md` candidate asked for clearer coverage of conditions, ambiguity, action requests and relevant information limits. All fifteen cases were rerun with the **same model and saved evidence**; only the answering instructions differed. Exact model digests and context text were checked against the baseline for every case. The same authored criteria and review rubric were used, without rewriting the reference answers to favour the candidate.

The baseline remains unchanged in `data/processed/evaluation-baseline`. The separate comparison and its Codex reviews are in `data/processed/evaluation-completeness`.

| Measure | Original instructions | Broader completeness instructions |
| --- | --- | --- |
| Completed cases | 15/15 | 15/15 |
| Valid answer structure and source IDs | 15/15 | 15/15 |
| Overall Codex review passes | 6/15 | 7/15 |
| Supported model claim items | 22 | 27 |
| Partially supported claim items | 4 | 4 |
| Total model claim items | 26 | 31 |
| New Pinecone read units | 18 | 0; all evidence reused |
| New query-embedding tokens | 224 | 0; no questions re-embedded |
| Reported answer-input tokens | 27,590 | 27,785 |
| Reported answer-output tokens | 1,739 | 2,121 |
| New local answer calls | 15 | 15 |
| Sum of generation time | 882.53 seconds | 1,060.90 seconds, about 17.7 minutes |
| Median generation time | 56.27 seconds | 63.59 seconds |
| Observed generation-time range | 31.09–92.80 seconds | 33.29–127.72 seconds |

Retrieval recall is unchanged: the comparison used the same evidence and performed no new retrieval. Generation had no external service fee in either run; local hardware/electricity costs remain unmeasured. These observed times are not a controlled hardware benchmark.

E09 was the only new overall pass. Its model-selected `action_not_supported` status triggered the application's explicit guidance offer and refusal to perform the requested bill-waiver action. Reviewing the whole rendered answer establishes that improvement even though the model supplied no policy claims.

All six previously passing cases still passed. However, pass/fail totals hide changes within already failing cases:

| Case | Change observed under the broader instructions | Assessment |
| --- | --- | --- |
| E02 | Adds the unexpired, matching-name ID conditions but still omits the separate authority check. | More complete direct ID guidance; authored case still fails. |
| E03 | Adds further supported policy detail but still omits the library's missing supported-model list. | Extra length does not repair the required limitation. |
| E04 | Improves referral scope and capability limits, but one cited timing statement remains too strong and positive ID detail remains absent. | Partial improvement; overall failure remains. |
| E05 | Adds a supported referral but keeps overstrong authority wording and omits the Training ID requirement. | Overall failure remains. |
| E07 | Gives four supported SIM claims instead of three, while still never asking what “it” means. | Ambiguity failure remains. |
| E09 | Selects the action status, producing a clear refusal and guidance offer. | Improves from fail to pass. |
| E11 | Says another person's SIM replacement is “not permitted” because required policies are missing, and selects `supported`. | Material worsening: invents a prohibition from insufficient evidence. |
| E12 | Still selects the wrong status for a refund action and now omits previously included fictional proof of purchase. | Completeness worsens within an already failing case. |
| E15 | Keeps the supported first checks but still omits the no-live-outage-information limitation and escalation. | Overall failure remains. |

E11 determines the rejection. The supplied SIM section says that missing referenced policies prevent the copilot from confirming eligibility. It does **not** establish that replacement is prohibited. The baseline at least used `insufficient_evidence` and made no prohibition. The candidate added an unsupported denial and a separate unsupported credentials condition. Its compound statements are labelled partially supported because they also contain true clauses; that label does not mean the invented denial is a minor issue.

The decision is therefore to **reject the broader completeness prompt**, despite the E09 improvement and the 7/15 total. More supported statements, a higher aggregate pass count, and valid citations are not enough to retain a change that creates a worse authority decision. No model answer or historical review was edited to hide this result.

## Separate narrow ambiguity wording test: rejected

The user's request for a clearer ambiguity instruction was tested separately in `answering-clarification.md`. This candidate was based on the **original** `answering.md`; only the ambiguity paragraph changed. It did not inherit the rejected broader completeness changes.

The requested rule was already present in the [original instructions](../prompts/answering.md): when ambiguity could change the answer, select `needs_clarification` and ask one concise question. The staged stronger wording was tested because the model did not reliably follow that existing rule. Adding or strengthening an instruction does not establish that the model will obey it.

Three targeted cases completed in `data/processed/evaluation-clarification`, with separate Codex reviews under the same criteria:

| Case | Observed result | Decision |
| --- | --- | --- |
| E01 | Correct optional-appointment guidance and citation. | Pass retained. |
| E07 | Three supported SIM policy statements, `supported` status and no clarifying question. | Target behaviour still fails: it infers the subject from retrieved evidence. |
| E11 | A supported necessary-check statement, but `supported` replaces the baseline's `insufficient_evidence` status. | Uncertainty handling worsens: the missing-authority explanation and fixed fallback are absent. |

This is **one pass in three targeted checks**, not a fifteen-case score for the narrow candidate. Unlike the broader completeness experiment, this E11 answer does **not** invent a prohibition or grant permission. Its failure is losing the required uncertainty response while the authority policy is withheld.

The three new local calls reported **5,796 input tokens, 348 output tokens and 206.76 seconds** of generation time. They reused evidence, incurred **zero new Pinecone read units**, and made no new query embeddings. Local computing costs remain unmeasured; external generation fees are zero.

The narrow wording candidate was therefore **rejected**, and the active configuration was restored to the original `answering.md`. The rejected prompt and its results remain available for inspection. Input for an additional controlled question, “Can I change that?”, was prepared, but inference was cancelled once the candidate failed these checks. That probe was **not tested**, and no response or result is claimed for it.

## Separate prompt-format experiment: not retained

A further E07 experiment used the narrow clarification instructions and repeated the actual JSON-encoded user question after the full unchanged evidence passages. This tested question placement relative to that narrow candidate. It did not add an expected answer or alter a source passage. The exact experiment is saved in [question-last-E07.json](../data/processed/question-last-E07.json).

The response again selected `supported`, produced four SIM policy claims and supplied no clarifying question. Its source labels were valid, but it still inferred the question's subject from retrieved passages. The requested ambiguity behaviour therefore **failed again**, and the placement change was **not retained**. No application-code change was adopted from this probe.

This single local call reported **2,223 input tokens, 259 output tokens and 83.52 seconds**, with **zero new Pinecone read units** and no new query embedding. These are one-probe measurements, not a new fifteen-case evaluation score.

The original prompt remains active. The trials do not establish successful ambiguity handling, and no further model trials are part of this completed investigation. A possible future change is to assess the user's question for missing context **before retrieval**, so search results cannot determine an unstated subject. That question-only clarification stage has **not been built or tested**. It must not be described as a current safeguard or a proven fix.

Any retained improvement still needs broader questions and independent human review before real-data or production use. The demonstration must make its known limitations visible rather than present a reviewed synthetic example as a general accuracy guarantee.

See the [runner instructions](evaluation.md), [baseline execution summary](../data/processed/evaluation-baseline/summary.json), [baseline Codex review summary](../data/processed/evaluation-baseline/review-summary.json), [comparison execution summary](../data/processed/evaluation-completeness/summary.json) and [comparison Codex review summary](../data/processed/evaluation-completeness/review-summary.json).
