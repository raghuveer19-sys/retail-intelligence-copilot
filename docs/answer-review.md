# First real answer and claim review

Reviewed on **2026-10-18 by Codex**, with a second Codex agent checking the assessment. This is not an independent human review or a calibrated automated judge. It covers **one question**, E04, using its saved evidence; no fresh retrieval occurred.

> My phone and SIM were stolen. What checks would I need before getting a replacement?

## Operational result

The installed `qwen3:4b` did not return an accepted answer with a 300-second request allowance. The server logged HTTP 500 at five minutes; the exact original cause was not confirmed. A second attempt with 600 seconds explicitly timed out. Neither produced an answer or usable token counts. Failure notes are saved separately.

Downloaded the smaller `qwen2.5:1.5b` model, approximately 986 MB. It reports no thinking capability. It successfully generated a structured answer from the same eight passages. The embedding model, index, question and evidence were unchanged.

| Experiment | Input tokens | Generated tokens | Generation time | Review result |
| --- | ---: | ---: | ---: | --- |
| Original instructions | 2,157 | 250 | 37.69 seconds | Supported statements; incomplete explanation of required checks |
| Revised instructions | 2,280 | 264 | 34.23 seconds | Better delegation condition and limitation; still incomplete, with an unnecessary insufficient-evidence fallback |

These are two local observations, not a speed benchmark or two separate evaluation cases. The model digest, evidence hash and generation settings matched across the successful runs. The changed input was the instruction text. Both runs used temperature zero, a 16,384-token context allocation and a 1,024-token output cap. No new Pinecone or OpenAI requests were made. Local inference has no external API charge; download, hardware and electricity costs are unmeasured.

## Baseline claim review

The baseline used six claims. Its source labels were all real, and its stated factual propositions were supported.

| Claim | Actual cited passage | Review |
| --- | --- | --- |
| A physical SIM replacement needs no appointment | S1, SIM-1024-v2 / Appointments and scope | Supported; optional background for this question |
| An authorised colleague must follow identity and account-authority policies | S2, SIM-1024-v2 / Required checks | Supported |
| A delegate needs an active record explicitly covering SIM replacement | S3, AUTH-1001-v1 / Delegated SIM authority | Supported as a necessary condition, but its condition coverage is incomplete: the same rule also requires completed identity checks |
| An account holder can request replacement after the checks | S4, AUTH-1001-v1 / Account roles | Supported |
| Identity does not establish account authority | S5, IDV-1001-v1 / Identity and authority are different | Supported |
| An expired, missing or mismatched training card requires referral | S6, IDV-1001-v1 / Missing or mismatched details | Supported |

The delegation statement is not a contradiction: saying a record is necessary does not explicitly say it is sufficient. Nevertheless, a useful policy explanation should keep the linked identity condition with that rule. The baseline mentions identity generally in another claim.

The main omission is **S7**, which was present in the evidence: use an **unexpired Fictional Training ID card whose name matches the fictional account record**. The answer discusses a missing or invalid training card without first explaining this positive requirement. This is an answer-completeness failure, not a failure to retrieve S7. All three E04 expected evidence sections were available.

No statement claimed that a SIM was replaced, identity was verified or service was restored. The fictional-guidance header and authorised-colleague wording establish a guidance frame, but the copilot's inability to perform checks should be clearer.

## Why the instruction comparison was not retained

The trial instructions asked the model to prioritise essential checks, use all supplied evidence rather than the first sources, preserve linked conditions and explain relevant limitations. They did not include a reference answer or identify a required source label.

The second draft preserved both delegation and identity conditions and explicitly stated the copilot limitation. However, it still omitted S7 and selected `insufficient_evidence`. That status is inappropriate here: the evidence can explain **which checks apply**, even though the copilot cannot decide whether a real person passes them.

We restored the original instructions because the trial did not resolve the core omission and introduced an unnecessary fallback. Both drafts and both reviews remain available for comparison. Neither is presented as a complete, ready-to-use answer. The next evaluation work should assess model choice and answer completeness before connecting a question screen; further prompt changes need measured comparisons.

## Non-thinking 4B model comparison

The separate `qwen3:4b-instruct` candidate returned a completed draft using the original instructions and the same evidence: 2,157 input tokens, 311 generated tokens and 131.40 seconds. This is not the earlier thinking-only `qwen3:4b` model. Its model card specifies non-thinking output; the local control setting and larger template reserve are documented in [local generation](local-generation.md).

A second Codex review found two fully supported claims and three partially supported claims. The draft strengthened the timing of a check beyond its cited passage, lost the qualification that a billing label **alone** does not establish permission, and broadened the Account Authority Team referral trigger to missing identity-policy evidence. It also omitted the positive Training ID requirement. The authored E04 minimum content checks alone would not catch all these problems.

The completed request therefore does not pass the quality gate. It is retained as a measured model comparison, not described as an improvement. The 15-case baseline measures the candidate more broadly before any further change.

## Inspectable records

- `data/processed/generation-example.json`: original final draft, evidence, settings and usage.
- `data/processed/generation-example-review.json`: every claim linked to full actual cited passages, support verdict and condition/completeness notes.
- `data/processed/generation-example-v2.json`: comparison draft with its exact trial instructions.
- `data/processed/generation-example-v2-review.json`: comparison review and rejection decision.
- `data/processed/generation-attempt1-failure.json` and `generation-attempt2-timeout.json`: unsuccessful larger-model attempts.
- `data/processed/generation-instruct-example.json` and `generation-instruct-example-review.json`: completed non-thinking 4B comparison and the separate claim review.

Generated records are local and ignored by Git. The generation code still records `claim_support_checked: false`: it performs structural checks, while these separate review records capture Codex's semantic assessment. The latest full suite passed 234 automated tests, including evaluation-runner checks; this is not an answer-accuracy score. The authored 15-case result placeholders remain unchanged.
