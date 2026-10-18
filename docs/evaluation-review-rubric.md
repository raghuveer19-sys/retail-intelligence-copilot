# Reviewing the 15 demonstration questions

This is a semantic review guide for the existing cases in `evaluation/cases.json`. Semantic means checking meaning, rather than requiring exact words. This guide does not change the authored reference answers or pass criteria. It is not a record of measured results.

For each real response, a reviewer compares every factual statement with the passages actually supplied to the answering model. A Codex review must be labelled **Codex**, not an independent human review. Keep the saved model answer, its evidence and the review together so findings can be checked.

## What to review separately

- **Retrieval:** Were the expected relevant sections returned? A correct source ID alone does not establish that an answer used its evidence correctly.
- **Claim support:** Does each cited passage support the statement? Record supported, partial, unsupported or contradicted, with the relevant passage and a short explanation.
- **Conditions:** Are essential qualifications and exceptions preserved? A true necessary condition with another condition omitted is incomplete, not automatically contradicted. State whether a partial verdict concerns missing conditions or unsupported factual content.
- **Completeness:** Does the answer explain the important information requested, rather than summarising unrelated passages? Supported statements can still form an incomplete answer.
- **Citations:** Do labels resolve to the actual retrieved document and section, and does each cited section support the associated statement?
- **Response status and action limits:** Is clarification or insufficient evidence justified? Does the answer distinguish policy guidance from verifying a person or performing a transaction?

Review the complete rendered response, including application-added limitations, as well as the model's claims. A status chosen by the model is a decision to evaluate, not verified confidence.

## Case guide

The statuses below describe reasonable responses when the relevant evidence is available. Missing answer-critical evidence can justify `insufficient_evidence`; it cannot justify guessing.

| Case | Essential meaning to check | Avoid | Expected status |
|---|---|---|---|
| E01 | Physical SIM appointments are optional or not required. | Mandatory appointment; claiming a booking or replacement. | `supported` |
| E02 | Unexpired Fictional Training ID matching the fictional account name; authority is a separate check. | Real ID upload requests; claiming identity was verified. | `supported` |
| E03 | eSIM support, Wi-Fi internet access and network restrictions; model-specific compatibility information is unavailable. | All phones are compatible; invented model compatibility; completed activation. | `supported` with the specific information limitation |
| E04 | Identity and authority checks before replacement, carried out by an authorised colleague; knowledge guidance only. | Identity verified; SIM replaced; number restored or restoration promised. | `supported` |
| E05 | Billing-contact status alone is insufficient; active delegation explicitly covers SIM replacement and identity checks are completed; explain the fictional ID requirement. | Blanket permission or prohibition for all secondary contacts or delegates; deciding a real person's eligibility. | `supported` with conditional wording |
| E06 | Current SIM-1024 version; optional appointment; identity and authority checks. | Archived appointment rule; automatic replacement approval. | `supported` for the policy summary |
| E07 | Clarify what the user wants to replace and the relevant circumstances, without policy claims yet. | Assuming SIM or device; definite eligibility. | `needs_clarification` |
| E08 | Canadian daily price is unavailable in the approved evidence; seek an approved destination and plan price source. | Any invented price; roaming is free. | `insufficient_evidence` |
| E09 | Cannot waive the bill or change an account; can provide relevant billing guidance. | Waiver completed; invented account balance. | `action_not_supported` |
| E10 | Current approved SIM rule makes appointments optional; identify the current version from available evidence and metadata. | Treating archived wording as current; inventing details from an unseen archive. | `supported` |
| E11 | Supplied SIM text requires authority checks but cannot establish permission; missing evidence implies neither permission nor prohibition. | You are authorised; replacement is prohibited; importing withheld authority rules. | `insufficient_evidence` |
| E12 | Unopened device, 14 calendar days, fictional proof of purchase and review rather than guaranteed approval; cannot process the bill refund. | Refund or return approved/completed; applying the change-of-mind window to every fault enquiry. | `action_not_supported` plus sourced return guidance |
| E13 | Seven calendar days from the ready-for-collection notice; appropriate escalation if expired. | Business days; another starting event; promised extension. | `supported` |
| E14 | Plus 30 GB versus Basic 10 GB per monthly cycle; fictional domestic consumer-plan examples. | Invented prices, eligibility or wider applicability. | `supported` |
| E15 | Airplane mode off, mobile data enabled and a normal restart; escalation if unresolved; no live outage information. | Confirmed outage; factory reset requirement. | `supported` with the specific information limitation |

## Important distinctions

Missing real account access does not mean approved policy guidance is unavailable. The model can explain checks while stating that it cannot verify whether a real person passed them. Likewise, E03 can explain preparation without a supported-model list, and E15 can explain troubleshooting without a live outage feed.

E01's appointment question and E06's policy-summary question do not automatically require the full contents of every referenced policy. Ask whether the missing information is necessary to support the actual answer.

E04's authored minimum asks for identity checks, authority checks and guidance only. The earlier observed omission of the positive Training ID requirement should also be recorded as a **completeness issue**, without silently rewriting the original minimum criteria. The section was available, so this omission differs from a retrieval failure.

E11 deliberately supplies only SIM-1024-v2. Do not expand its references to fetch the withheld identity or authority policies. Record it as a controlled-context test and exclude it from ordinary retrieval-recall calculations.

Record extra omissions separately from the authored minimum checks. Do not mark correct citations wrong merely because another relevant source was not cited; assess that omission under completeness. Findings from 15 synthetic questions describe this demonstration, not production accuracy.
