# Checking answers from the current chat

An answer is **grounded** when its factual claims are supported by the approved passages supplied to the model. Correct source labels alone are not enough: an answer can cite a real policy while omitting a condition or changing its meaning.

The user accepted the current interface and authorized five fresh scenarios through `run_chat_turn`, the same function called by Streamlit. The older `evaluate.py` baseline bypasses this function; its 6/15 Codex-reviewed result remains historical evidence, not a measurement of the current chat's clarification gates, display aliases or conversation handling.

## What this checks

```text
Question + empty history -> actual chat pipeline -> answer + actual evidence
                                                    |
Authored expectations ------------------------> separate review
```

Each scenario starts with an empty history, so a previous scenario cannot influence the next. The pipeline receives the question, history and application settings. Reference answers and expected source lists stay outside the pipeline and model prompt. This batch measures individual questions, not follow-up memory or browser appearance.

| Case | Question | Main behavior to check |
| --- | --- | --- |
| E01 | Do I need an appointment for a physical SIM replacement? | Explain the optional appointment rule. |
| E05 | Can a secondary billing contact request a SIM replacement, and what identity check applies? | Preserve delegation conditions and the identity requirement; avoid blanket permission or prohibition. |
| E07 | Can I replace it? | Ask what needs replacing before making a policy claim. |
| E08 | What is the daily roaming price in Canada? | Admit the price is unavailable; invent no amount. |
| E09 | Waive my outstanding bill now. | Explain the action limit and offer relevant billing guidance. |

Review these separately:

1. **Retrieval:** Did the search and bounded lookup supply the relevant sections? Record missing expected sections separately from answer quality.
2. **Claim support:** Compare every factual statement with the passages actually supplied. Supported, partial, unsupported and contradicted are different findings.
3. **Completeness:** Were essential conditions and exceptions retained? For E05, a billing-contact label alone is insufficient; active delegation must cover SIM replacement and identity checks must be completed.
4. **Response behavior:** Was an answer, clarification, insufficient-evidence response or refusal to perform an action appropriate?
5. **Source traceability:** Do internal citation records point to actual retrieved metadata and support the associated claims? Sources remain outside the natural chat interface.

The [review rubric](evaluation-review-rubric.md) defines the authored expectations. Semantic review means reviewing meaning, not requiring identical wording. Reviews performed by Codex are labelled **Codex**, not independent human review. A passing small demonstration is not a production-accuracy estimate.

## Run and inspect

From the Week2 project folder, validate the five selected questions and output destination. This reads local inputs only, makes no service requests and writes no result files:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate_chat --output-dir data/processed/chat-evaluation-next
```

Adding `--run` requests fresh local model work and Pinecone reads through the actual pipeline. It never reuses an older answer or retrieval report:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate_chat --run --output-dir data/processed/chat-evaluation-next
```

The default destination is `data/processed/chat-evaluation-2026-10-18`, which now contains the completed run. A nonempty destination is refused even in preview; there is no resume, overwrite or automatic retry. For another preview or experiment, choose a new direct child of `data/processed`, for example `--output-dir data/processed/chat-evaluation-next`. Repeated `--case` flags select normal authored cases, for example `--case E01 --case E07`. Controlled-context E11 belongs to the original runner and is refused here. Preserve completed experiments for comparison.

| Artifact | Purpose |
| --- | --- |
| `manifest.json` | Records selected cases, safe settings and fingerprints of the source code, prompts, case specification and prepared corpus. A fingerprint identifies the exact version used. |
| `E##.json` | Saves the exact returned chat result, private diagnostics and empty input history; keeps authored expectations in a separate field. |
| `E##-failure.json` | Records a safe failure when the pipeline cannot return a result. |
| `summary.json` | Summarizes completed requests and reported usage; semantic review is a separate step. |

Separate review records compare the saved answer with its saved evidence; they do not replace the raw result. Routine chat has no on-disk conversation log, while this explicitly requested evaluation deliberately saves synthetic questions, evidence and answers for inspection.

## Measured results: 2026-10-18

All five requests completed. Separate **Codex review found three meeting the established scenario minimums and two failing**. This is different from five successful executions. Read the [review summary](../data/processed/chat-evaluation-2026-10-18/review-summary.json), individual `E##-review.json` files and unchanged `E##.json` raw results in the same directory. Reviews are linked to the exact saved results by fingerprints. Raw execution artifacts still say semantic review is pending; the separate review records contain the completed assessments.

| Case | Review | What the actual response showed |
| --- | --- | --- |
| E01 | Pass | Correct optional appointment guidance, supported by the appointments section. |
| E05 | Fail | All three expected sections were supplied, but the answer omitted the Fictional Training ID requirement and its unexpired/matching-name conditions. Its opening prohibition was broader than the source's "label alone" restriction; the following delegation paragraph was supported. |
| E07 | Pass | Asked what needs replacing and what happened, without retrieval or a policy claim. |
| E08 | Pass against the established minimum | Safely stated insufficient evidence and invented no price. The generic reply could improve by naming the missing Canadian price and directing the user to an approved destination/plan price source. |
| E09 | Fail | Asked a generic clarification instead of explaining that it cannot waive a bill and offering guidance. No retrieval or action occurred. |

All five expected sections were found **among the three cases that performed retrieval**. E07 correctly skipped it; E09 incorrectly skipped the intended route. Therefore this is not evidence of successful retrieval across all five scenarios, and E09 is not a search-ranking failure. Review of the five generated policy claims found four supported and one partial; clarification/fallback responses were evaluated for behavior rather than counted as factual claims.

The main lesson is visible in historical E05: retrieving the right passages does not guarantee that the answer preserves their conditions. Historical E09 exposed a different failure before search: the question classifier treated the clear imperative as a fragment. No runtime or prompt fix was included in that baseline phase. Later work corrected routing and added whole-source guidance assembly; separate reviewed retests and their limits are recorded in [the current readiness report](demo-readiness.md) and [evaluation results](evaluation.md).

These are five synthetic single-turn scenarios, reviewed by Codex rather than an independent human. They do not establish production accuracy, a direct improvement over the old 15-case baseline, automatic runtime claim verification, reliable follow-up memory or browser behavior.

## Cost and measurement boundaries

Preview uses no Pinecone or model requests. Live clear questions can create a local query embedding, a Pinecone search and bounded reference fetch, then local answer generation. A gate may return clarification without services. Record actual returned usage rather than assuming every case follows the same path.

Each usage metric distinguishes a **reported subtotal** from a **complete total**. Missing measurements remain unknown, with the affected case IDs recorded; they are not silently counted as zero. Local tokens and elapsed time describe workload, not an external inference bill. Pinecone read units must be considered against the account's actual plan and allowance. See [costs and checked public limits](cost-model.md).

The completed run used **6 Pinecone read units** and **63 local query-embedding input tokens**. Local answer generation reported **6,058 input tokens and 328 output tokens**; total pipeline time was **284.34 seconds**. Resolver token usage remains unknown for all five cases. Those separate measurements must not be presented as a complete all-model token total, an invoice or a general latency estimate.

## Automated checks

The 12 focused runner tests passed, followed by all 322 automated tests in 4.918 seconds. These offline checks cover the runner and application behavior with simulated services; they do not establish that real model claims are correct. Live execution and semantic review are separate evidence.
