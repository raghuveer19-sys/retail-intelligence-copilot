# Demo readiness report

Verification period: **18–19 October 2026**. The local demonstration milestone is complete: the accepted chat interface, local models and Pinecone integration are implemented and exercised. The selected answer reviews and targeted live conversation correction are complete. This is a bounded demonstration, not production certification.

A separate build and learning report was delivered privately as a Google Doc. This repository includes the architecture, source documents, active prompts, learning journal, decision log and evaluation documentation needed to understand the build. The private report link is intentionally omitted from this shareable copy.

## Current behavior

The active instructions are `prompts/answering-grounded-v2.md`, with `[answering].presentation = "source_passages"`. The model receives compact evidence containing source labels, titles, headings and complete text. It proposes a status and source IDs; the chat replaces its policy prose with whole selected passages, other supplied sections from the same documents and supplied passages named by direct references in the original selection. Expansion stays inside the current evidence pack and does not recurse or fetch additional policies.

This preserves source wording and conditions within displayed passages. It does **not** guarantee relevant selection, complete coverage of a question or the right uncertainty status. Extra paragraphs and cautious or incorrect status choices remain possible. The original model draft, selected/added IDs, final passages, metadata citations and reported usage remain available privately for review.

A narrow overview fallback can use exact matching passages already in the pack when a question such as "What does policy SIM-1024 say?" receives an empty insufficient-evidence draft. It does not apply to every mention of a policy ID and does not retrieve new evidence. When an insufficient-evidence draft contains guidance, the chat introduces the available passages neutrally instead of asserting an unverified evidence gap. Missing directly referenced policies still receive an explicit limitation. The original/final status remains inspectable; these changes do not fix or certify the model's status classification.

Deterministic rules handle complete acknowledgements, clear standalone requests and narrow clarification replies. For example, the explicit reply "A physical SIM" can fill "it" in "Can I replace it?" while retaining replacement intent. Some other follow-ups still use a bounded local-model rewrite. A separate application guard assigns the unsupported-action response for recognised execution requests; it grants no transactional capability and is not a universal language-understanding guarantee.

## Verified operating facts

| Check | Observed result | Boundary |
| --- | --- | --- |
| Automated regression suite | 398 tests passed in 15.914 seconds | Offline checks, including request-scoped power handling, self-service question routing and the controlled missing-evidence script; not a real-answer accuracy score. |
| GitHub submission check, 19 October | All 398 tests passed in 5.373 seconds from an isolated export of staged source files | Reused installed Python dependencies and cached tokenizer vocabulary; no `.env` or generated corpus/results were included. This does not verify a fresh installation of external services. |
| Python launcher | A real test server started on port 8502 and returned HTTP 200; that test instance was stopped | Confirms startup/health, not browser layout or account access. |
| Existing demo server | Port 8501 health returned HTTP 200 | The owned server remains available; health alone does not verify answer correctness. |
| Launch prerequisites | Local inputs/dependencies/private key presence passed; 33 chunks matched approved source data | Credential presence does not verify access or quota. |
| PowerShell policy | The optional `.ps1` launcher was blocked by the existing policy | The primary Python launcher works without changing that policy. |
| Standby investigation | Windows Kernel-Power events recorded Modern Standby due to idle timeout during long test gaps | Interrupted wall-clock timings do not establish normal model latency or the cause of every failure. The temporary bounded helper was stopped before final E05 verification. |
| Request-scoped idle-sleep guard | Local Ollama HTTP opening and response reading now run inside `runtime_power.py`'s Windows guard | Restores previous thread state on exit; does not change the power plan, keep the display on or prevent deliberate sleep/lid closure. Unsupported systems use a no-op. |

Use [the demo guide](demo-guide.md) for launch, recovery, representative questions and session limits. The primary command is:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --launch
```

An occupied port is refused without reusing or stopping another process; use the address of the known existing Week2 server or choose `--port 8502` when it is free.

## Answer-quality evidence

The historical 15-case generation baseline passed 6 cases under Codex review. The subsequent five-case current-chat baseline passed 3 established minimums; it exposed incomplete ID/authority wording and incorrect routing of a bill-waiver request. These records describe earlier implementations and remain preserved. Prompt-only trials, including compact v2 and question-part v3, still lost required conditions and motivated source-passage assembly.

The 14-scenario comparison combines preserved initial requests, separate fresh reruns and service-free replays through the final presentation logic. It must not be described as one fresh 14-case run of the final implementation. All **14 selected final displayed answers meet the reviewed demo minimums**, with model-status accuracy and extra-background caveats kept separate. The separate **E11 SIM-only controlled check passes** without inventing permission or prohibition. Original interrupted/failed records remain preserved. The case-linked report is `data/processed/demo-normal-case-scorecard-2026-10-19.json`; retrieval found 21/23 expected sections, independently of answer quality. Successful normal policy requests took 41.1–99.0 seconds in these selected attempts; ambiguity returned immediately. These are observations on this computer, not a service guarantee.

A separate six-turn live AppTest rehearsal exercised appointment guidance, follow-up, acknowledgement/history retention, clarification completion and the action boundary through the real app. Five turn checks passed initially. The model misclassified "Can I book one anyway?" as an execution request. A narrow application guard now distinguishes a clear question about the user's own options from a request directed at the copilot; it does not declare eligibility or promote the answer to verified completeness. A two-turn live retest confirmed correct available booking guidance and the thanks acknowledgement. Rerun/history retention and New chat checks passed in both runs. The final follow-up took 89.99 seconds. Original failure and corrected results remain separate.

All six intended behaviors are now covered across the original rehearsal and targeted retest, not a fresh six-turn rerun. Separate Codex reviews compare actual source claims and metadata citations. The final record is `data/processed/demo-final-verification-2026-10-19.json`; the latest guard was also checked to leave the 14 selected normal-case outputs unaffected. The rehearsal preview makes no service requests:

```powershell
.\.venv\Scripts\python.exe scripts/rehearse_demo.py
```

Adding `--run --output-dir data/processed/demo-rehearsal-new` requests real local-model/Pinecone work and saves synthetic transcripts in a new evaluation folder. It does not use fake pipeline responses. AppTest checks widget/session behavior, not rendered browser appearance. Review displayed passages against the actual evidence and expected conditions; exact source copying is not automatic semantic verification. Any Codex review must remain labelled as such, not independent human validation. See [the evaluation method](chat-evaluation.md) and [review rubric](evaluation-review-rubric.md).

## Demonstration limits

- The corpus is fictional and fixed to the configured policy date; the app performs guidance only.
- Ordinary chat is session-only: refresh/new sessions/process restarts can lose it. Saved evaluation transcripts are a separate, explicit testing artifact.
- Local-model latency varies; no response-time commitment has been established.
- Browser rendering/accessibility remains unverified because browser inspection is unavailable.
- Pinecone account allowance is unverified. Read usage and local computing cost must be reported separately; see [the dated cost model](cost-model.md).
- This report does not establish production readiness, reliable performance on arbitrary questions, or a universal guarantee against incorrect source selection and uncertainty decisions.
