# Decision log

## 2026-10-19 - Public code submission

Publish the standalone Retail Intelligence Copilot repository, as requested, with a fresh-install guide and locked dependencies. Include synthetic policies, authored evaluation cases, prompts, code, tests and learning documentation. Exclude private credentials, editor settings, installed environments, downloaded models and generated embeddings/transcripts. Retain historical measurements as dated observations rather than claiming a clone reproduces them automatically. No new framework, subscription, model call or deployment is part of this publication. The clean staged export passed all 398 tests; use the GitHub no-reply address for the initial commit.

## 2026-10-19 - scope idle-sleep protection to local requests

Use Windows `SetThreadExecutionState` only around local Ollama HTTP opening and response reading, restoring the previous thread state in `finally`. Do not request display/away mode, alter a power plan or override deliberate sleep/lid closure. Non-Windows systems use a no-op; power API failures must not replace service results. Stop the temporary verification helper before final E05 testing. [Official API checked 2026-10-19](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).

The full offline suite passed 394 tests in 12.824 seconds. Preserve every interrupted/failed artifact and identify the exact original, rerun or presentation-replay record used for each final verdict. Final live/controlled/rehearsal review remains pending; no single fresh final-version 14-case batch is claimed.

## 2026-10-19 - preserve uncertainty traces and make the demo operable

Allow an empty insufficient-evidence draft to select existing exact policy-ID passages only for a narrow policy-overview request. Use neutral framing for available source passages and a specific warning for missing referenced guidance; do not silently change the model's uncertainty status or claim its classifier is fixed. Preserve failed/interrupted artifacts and run comparisons in separate folders.

The full offline suite passed 385 tests in 12.235 seconds; final live results remain pending. Windows events verified idle-timeout Modern Standby during long test gaps. Keep presentation hardware awake and plugged in, and recover services before retrying. Use only a temporary bounded awake helper during verification, with no persistent power-plan change. Document this operating requirement rather than treating interrupted timings as model performance.

## 2026-10-18 - use whole supplied passages for the demo's policy guidance

Activate `prompts/answering-grounded-v2.md` and `[answering].presentation = "source_passages"` after prompt-only trials continued to lose conditions. Keep compact source labels/titles/headings/full text in the model input; retain complete metadata privately. Use validated source IDs to copy whole selected passages and supplied same-document/direct-reference passages. Expansion cannot leave the evidence pack or recurse through added passages; preserve limits and fail rather than truncate conditions. Retain the model draft, final passage draft and selection trace separately.

Do not treat text provenance as proof of relevance, complete coverage or correct status. Apply deterministic clarification/routing for bounded English patterns and a separate guard for recognised execution requests; neither component adds transactional powers or missing policy facts. Preserve historical evaluations and measure the new presentation through `run_chat_turn`, with a separate real AppTest rehearsal for session behavior.

Use the project Python launcher as the operating path because the existing PowerShell policy blocks `.ps1` execution. Do not change that policy, install/download automatically, or stop/reuse an unidentified process. Verified so far: 375 offline tests passed in 17.487 seconds; the launcher test on 8502 and owned server on 8501 returned HTTP 200, and the test instance was stopped. Final 14-case live results and six-turn rehearsal are pending; browser rendering remains unverified. See [the current readiness report](demo-readiness.md).

## 2026-10-18 - preserve a baseline from the actual chat pipeline

Evaluate E01/E05/E07/E08/E09 through `run_chat_turn` with isolated histories and fresh requests. Default to a read-only preview; require `--run` for execution. Refuse nonempty output folders, with no resume, overwrite or automatic retry. Save code/prompt/case/corpus fingerprints, actual evidence and usage in `data/processed/chat-evaluation-2026-10-18`; keep authored expectations outside the pipeline and semantic reviews separate, explicitly attributed to Codex.

All five requests completed, with three meeting established scenario minimums. Preserve E05's missing conditions/overbroad wording and E09's incorrect clarification route as open defects; E08's generic safe fallback is a pass with improvement opportunities. Do not present the expected-section matches in the three searched cases as success across all five, or this small run as production accuracy. The 12 runner checks and full 322-test suite passed; no runtime/prompt fixes were included. Next changes should target the demonstrated failures and repeat the cases in a new directory.

Public Starter pricing and the 1,000,000 monthly read-unit limit were verified from official sources on 2026-10-18; the account's remaining quota is unknown. Report the actual 6 RU and measured local token/time values, keeping missing resolver usage unknown. No subscription change, indexing write or paid inference provider was introduced. See [evaluation](chat-evaluation.md) and [cost model](cost-model.md).

## 2026-10-18 - accept the current interface and evaluate knowledge behavior

Record the user's acceptance of the current UI and move the next work to grounded knowledge scenarios. Preserve the historical 15-case baseline (6 passes, 9 failures; Codex review, not independent human review). Do not treat its results as measurements of the current chat: `evaluate.py` bypasses `run_chat_turn` and therefore its clarification/acknowledgement gates, aliases and bounded memory.

Evaluate the actual chat route using scenario expectations and retrieved evidence, reviewing claim support, complete conditions and response status separately from retrieval quality. User UI acceptance does not verify browser accessibility or answer correctness. No new evaluation results, tests or service calls are introduced by this decision.

## 2026-10-18 - separate social acknowledgements from policy requests

Return a short local reply for complete acknowledgements such as "OK thanks" before resolution, corpus/credential loading or service calls. Preserve them in visible history, but skip them within the latest three raw turns used for reference context; do not extend that window or cross a failure boundary. Mixed substantive requests and yes/no remain on the normal route.

The baseline did not reproduce the reported clearing of all history; it confirmed unnecessary resolution/clarification instead. All 70 focused offline checks passed (17 interface, 32 pipeline, 21 conversation), including the real acknowledgement pipeline with networking blocked and a subsequent follow-up. Do not describe these results as a verified fix for whole-history loss.

Use polling and run-on-save to support routine reruns, and retain disconnected sessions for 900 seconds within the same process. Runtime settings were verified and the restarted server's health endpoint returned HTTP 200. This is not persistence across refresh/new sessions or server restarts. Browser inspection remains unavailable; no live model or Pinecone requests were made.

## 2026-10-18 - honor removal of the customer-details reminder

Removed the visible customer-details reminder at the user's explicit request, superseding its earlier display requirement. Data handling and backend behavior are unchanged. The updated existing welcome-screen check passed; the restarted local server's health endpoint returned HTTP 200. No model or Pinecone requests were made. Preserve the earlier decision below as history.

## 2026-10-18 - keep the chat clear on narrow screens and during failures

Use Streamlit's native noninteractive gray "Policy guidance" badge and the highlighted reminder "Don't enter customer names, phone numbers, or account details." Stack full starter columns at widths up to 640 pixels, retaining each question caption beneath its button. Explicitly wrap plain-text messages and long words without enabling Markdown or HTML rendering.

Keep service/setup errors in colleague-facing language: retry or contact copilot support. Treat missing/unverifiable policy evidence separately, with a policy-owner/support referral. Add no policy-reference controls; evidence remains private under the current natural-chat preference. All 41 focused offline checks passed (15 interface, 26 pipeline), including preservation of the full long reply and wrap flag, clarification, unsupported actions, setup/service failures and reset. They do not establish visual layout or real model correctness. No live services were called. Browser rendering is unverified and final appearance remains reviewable.

## 2026-10-18 - correct contrast and separate display names from policy names

Honor the user's removal of fictional/demo labels from chat chrome, replacing them with "Your policy companion" and "Policy guidance" while retaining "Avoid sharing customer or account details." This supersedes the earlier interface-notice requirement; it does not alter synthetic corpus provenance or grant real transactional authority.

Target the actual `st.text` child span for white user-message text on teal, and set explicit input/placeholder contrast. Use configurable display aliases, Practice Basic → Connect Essential and Practice Plus → Connect Plus, without changing their 10 GB/30 GB allowances. Normalize question/history names before resolution/retrieval and apply display names after draft validation. Preserve canonical source/draft/citation data, synthetic flags, the Pinecone index and model settings. No re-indexing or charged service call is needed.

All 58 focused offline checks passed (12 interface, 22 pipeline, 6 plan-name and 18 conversation checks); a network-blocked check validated the 33 saved corpus records. No browser surface is available to verify rendering. These checks establish application behavior and record consistency, not live model quality or visual appearance. See [chat design](chat-design.md).

## 2026-10-18 - implement the authorized natural chat with bounded reference context

The user authorized building the interface from the agreed instructions. Implement the central chat with starters, New chat, native messages/input and graphical styling; preserve the explicit removal of source expansions and diagnostics. Keep the original library viewer as the separate `library_app.py` command. Final appearance remains available for user review before finalization, without repeating approval for already authorized implementation.

| Decision | Reason and limit |
| --- | --- |
| Use installed Streamlit 1.65.0 and native chat widgets | Keep ordinary interaction and AppTest coverage; no added framework or dependency. |
| Render user/model messages with plain text | Avoid interpreting their Markdown or HTML as links, images or page content. The stylesheet is project-owned. |
| Resolve references before fresh retrieval | A contextless "Can I replace it?" can request specifics before passages bias the model toward a topic. English routing rules and local rewrites still need broader evaluation. |
| Bound reference context to three recent user turns and 4,000 characters | Keep complete recent turns; exclude assistant answers and evidence. A failure breaks the window so older topics cannot be revived across it. A 1,000-character question limit bounds new input. |
| Retain at most 30 displayed exchanges in session memory | New chat clears conversation and private evidence. No disk chat logs, global conversation cache or persistent cross-session memory. |
| Keep evidence/citation metadata privately while displaying natural text | Honors the user's interface choice while preserving source validation and later inspection. It does not establish semantic claim support. |
| Request services only on submission, with no automatic retries | Reruns and New chat do not repeat queries. Current failures receive safe messages and do not reuse an earlier answer. |

The final full automated suite passed 281 tests after all code changes, including 12 UI, 17 pipeline and 18 conversation checks and the strengthened failed-turn boundary. A real network-blocked clarification call and successful Streamlit page/health HTTP responses are separate observations. Real appointment and follow-up requests returned supported answers in 94.1 and 137.5 seconds, with one private citation each and claims checked against the actual appointments section. Browser appearance and broader conversation quality remain unverified. Do not treat these two examples as fixing the original 6/15 answer-quality baseline. See [chat design](chat-design.md).

## 2026-10-18 - remove source controls from the chat experience

The user's latest instruction is a natural chat without source expansion. It supersedes the earlier UI requirement for expandable evidence. Remove inline S1/source buttons, source expanders, answer diagnostics and the policy-library toggle from the scripted preview. Keep the approved central conversation, starter questions, New chat, input, graphical styling and planned follow-ups.

Retain retrieved evidence, citation/source metadata and checks behind the scenes. Existing development commands, saved reports and the separate policy-library viewer remain available outside the chat; no new inspection tools are introduced. The actual app and backend are unchanged, and live chat/memory are still not implemented. The preview changes passed static structure checks and the local address serves the updated content; browser interaction remains unverified. Present the polished natural-chat design for review before finalization, honoring the user's earlier approval request. Preserve the prior design decisions below as history. See [chat design](chat-design.md).

## 2026-10-18 - preserve the approved layout and polish the visual design

The user approved the Focused chat layout and requested a graphically enhanced interface. Keep the central conversation with expandable sources; do not reopen the layout choice. Prepare a coordinated teal and ink palette, clearer typography and spacing, consistent Lucide icons, and distinct chat/source-panel styling. Show the polished preview for review before finalization, as the user previously requested.

This decision authorizes visual refinement of the preview, not a claim that the live chat or bounded memory already works. The current Streamlit library viewer is unchanged, and model-quality gaps, including ambiguity handling, remain open. Preview checks must distinguish static inspection from browser runtime checks. No model or Pinecone requests are needed. See [chat design](chat-design.md).

## 2026-10-18 - measure model quality and keep the UI proposal separate

The complete baseline passed 6/15 separately reviewed cases. A broader completeness prompt passed 7/15, but is **rejected**: E11 changed cautious abstention into an unsupported prohibition when authority evidence was absent. E12 also lost an available proof-of-purchase condition. A higher total pass count does not justify a material regression. Both sets of raw answers and separate Codex reviews remain preserved; no independent human review is claimed.

The user then explicitly requested clarification for ambiguous questions such as "Can I replace it?". Prepare `prompts/answering-clarification.md` from the **original** instructions, changing only the ambiguity rule. Test this separately against the user's example, a new ambiguous question, a clear question and missing-evidence behavior. This does not adopt the rejected completeness prompt or imply that bounded chat memory has been implemented.

The narrow wording trial was also rejected after E07 still guessed a SIM and E11 lost the baseline insufficient-evidence status; E01 passed. The extra ambiguous probe was prepared but not run once this candidate failed. An isolated question-last format experiment on E07 failed too, and no format change was adopted. **Active instructions remain `prompts/answering.md`**, which already require clarification. Stronger wording is preserved as an experimental file, not a validated solution. A separate question-only check before retrieval is a future design candidate; its reliability and integration remain untested.

| Decision | Reason and limit |
| --- | --- |
| Preserve all E04 model/prompt comparisons | A faster or completed answer is not necessarily more complete or better grounded. The unsuccessful prompt trial was reverted. |
| Evaluate the separate non-thinking `qwen3:4b-instruct` candidate | The thinking-only model timed out; the smaller candidate completed but omitted conditions. The 4B comparison also has quality gaps, so it is a candidate rather than a proven improvement. |
| Explicitly configure false when this model omits thinking-control metadata | Its official Qwen card specifies non-thinking only, while the installed Ollama capabilities are incomplete. Known metadata takes precedence; unexpected thinking output is rejected and never saved. |
| Increase the template reserve to 4,608 for this candidate | Its 4,040-byte template exceeds the earlier allowance. Preserve complete evidence; the byte-based allowance remains a conservative estimate, not exact tokenization. |
| Keep one manifest per evaluation configuration | Reject stale/mixed model, prompt, settings, corpus and case expectations before resuming. Preserve original authored cases and record generated results separately. |
| Save retrieval before generation and keep the model warm briefly between cases | Reduce repeated Pinecone reads and model loading; report failures and unknown usage honestly. No automatic model retries. |
| Review support, citation support, completeness, status and actions separately | A structurally valid source ID cannot establish those semantic properties. Reviews are attributed to Codex, not described as independent human assessments. |
| Honour E11's controlled document subset | Test missing authority evidence without secretly supplying it; no invented scores and no ordinary retrieval-recall denominator. |
| Obtain explicit approval before finalizing the chat interface | The user selected Focused chat and bounded conversation memory, then specifically requested final approval. Show a concrete welcome/conversation preview first; the precise memory window and interface details remain proposals. The existing Streamlit library viewer is unchanged. |

The current local suite passed 234 tests. Live results and semantic reviews have separate artifacts and are summarized in [evaluation](evaluation.md). The interface proposal is in [chat design](chat-design.md).

## 2026-10-18 - connect local answer generation and preserve the review boundary

| Decision | Reason and limit |
| --- | --- |
| Use installed Ollama `qwen3:4b` for the first answering experiment | No OpenAI key is available; local inference avoids an external generation charge. CPU latency and answer quality still need measurement. |
| Reuse the saved, revalidated E04 context | Isolates generation from retrieval changes and avoids another Pinecone request. It is not a fresh end-to-end run. |
| Request structured claims and validate again in Python | Makes source attribution inspectable; schema validity alone is not evidence of factual support. |
| Keep a conservative byte-based prompt allowance, template reserve and explicit output cap | Preserve whole sections and stop rather than silently shorten evidence. The allowance is not an exact tokenizer count. |
| Discover the installed model's thinking controls and discard internal thinking | This model currently reports `true` only. Save final content and usage only; output usage includes internal thinking. |
| Require a normal stop, valid usage and known sources; preserve prior outputs | A partial or malformed draft must not appear to be a successful current result. No automatic inference retry. |
| Keep semantic-review flags false in automatic results | A separate claim review must assess actual cited support, completeness and guidance-only behaviour. |
| Add typed, safe local-service errors and increase generation timeout to 600 seconds after the first failed attempt | The initial attempt ended after roughly five minutes with a generic error. Timeout is suspected, not established for that original run. Future read timeouts are distinguished without logging provider bodies. |
| After a confirmed 600-second timeout, select smaller `qwen2.5:1.5b` | Downloaded approximately 986 MB from the official Ollama model registry. It reports completion without thinking capability, a byte-based tokenizer, a 32,768-token maximum and a 1,482-byte template. Use `think: false`, a 1,024-token output cap and a 300-second timeout; preserve the question/evidence for comparison. Quality still requires review. |

All 213 tests passed after the final code change, including 18 mocked generation tests. Local unit tests do not establish real model performance. Official chat, structured-output and thinking API references are linked in [the generation lesson](local-generation.md). Paid service use remains disabled; hardware/electricity costs are unmeasured.

## 2026-10-17 — separate answering instructions, reference checks and semantic evaluation

| Decision | Reason and limit |
| --- | --- |
| Store readable rules in `prompts/answering.md` | Explain and inspect policy grounding, uncertainty, clarification and guidance-only behavior independently of provider code |
| Revalidate saved context before preparing messages | Reject changed evidence, mismatched labels and stale local corpus/model/date; this is not a remote-state check |
| Keep instructions and evidence in separate messages | Source text remains data; this separation alone does not prove prompt-injection resistance |
| Use structured claims with source IDs and a response status | Associate each claim with its proposed evidence and make uncertainty/action handling explicit |
| Build citation labels from retrieved registry metadata | The model selects IDs; it does not supply authoritative source names or links |
| Reject invalid drafts in full | Avoid displaying a partially validated draft after unknown IDs or malformed fields |
| Keep source membership distinct from claim support | A real appointments source does not justify an unrelated identity claim; semantic correctness remains unmeasured |
| Use a fixed response for empty context | No model request is needed when there is no retrieved evidence |
| Keep this step local and model-independent | Complete the instructions/checking lesson before model selection and external usage |

All 195 tests passed, including 18 hand-written draft/prompt tests. The actual E04 preview contains 8,991 message-content characters; no model token count is inferred. Manual S7 citation rendering and S99 rejection worked with network blocked. Existing context/retrieval/embedding artifacts were unchanged. No generation provider, pricing or account changes. See [answering instructions](answering-instructions.md).

## 2026-10-17 — construct context from saved evidence before calling a model

| Decision | Reason and limit |
| --- | --- |
| Reuse the saved enhanced E04 result for the first context preview | Isolate and teach packing behavior without additional service requests |
| Revalidate local eligibility and exact returned text/metadata | Reject stale, excluded or altered evidence; this does not check today's remote Pinecone state |
| Keep all validated unique candidates, in original order | No tested relevance cutoff exists; reference-fetched passages must not be discarded because they have no score |
| Deduplicate by agreeing chunk ID, not by similar text | Keep different sources traceable and stop on conflicting copies |
| Preserve whole sections and stop if bounds are exceeded | Avoid cutting a rule from a condition; ten sources/12,000 characters are application guards, not model token limits |
| Assign per-pack S1-style labels and a metadata registry | Prepare real source references without an LLM inventing them; claim support and generated-reference validation remain separate |
| Keep scores/provenance outside the prospective model evidence | Preserve diagnostics without presenting similarity as answer confidence |
| Notice explicit policy references without included passages | Make some gaps visible while retaining `evidence_sufficiency: not_assessed`; one included policy section does not establish completeness |
| Keep generation and semantic relevance selection pending | Package first, then explain/evaluate answering instructions, model choice and claim grounding |

All 177 tests passed. Saved E01/E04/E06 packs retained 8/8/5 sections and their exact text; E04 measured 5,266 characters. The actual preview ran with network blocked and made zero service calls. Previous retrieval/embedding files were unchanged. No pricing or model-provider choice changed. See [the lesson](context-construction.md).

## 2026-10-17 — retain bounded policy lookup as an optional enhancement

The original semantic baseline missed identity details for E04 and appointments for E06. Raising k to eight still missed identity details. Implemented explicit policy-ID/reference lookup and reran the same questions: expected-source recall improved from 1/1, 2/3, 1/2 to 1/1, 3/3, 2/2. First-four semantic IDs and scores stayed identical, with matching corpus/model/question input/date. All 158 automated tests passed; the live run separately reported 6 RU.

| Decision | Reason and limitation |
| --- | --- |
| Keep `--follow-references` opt-in; keep semantic top_k 4 | Two observed gaps were recovered, but E01 gained text without measured recall benefit; broader precision and answer quality remain unmeasured |
| Question IDs take precedence over passage references | Bound exact-policy lookup to what was named; this does not automatically retrieve every dependency needed for an eligibility answer |
| Follow original passage references once, at most two policies/six added sections | Bound extra evidence and read usage; skip/report a whole policy if its missing sections exceed the limit |
| Fetch source fields from Pinecone and validate against approved local records | Preserve the actual retrieved evidence; never substitute invented or stale source text |
| Preserve original scores; fetched passages have no similarity score | ID fetch does not measure similarity; retain provenance separately |
| Report unknown/version-specific IDs without silently switching policies | Current approved-policy lookup does not provide historical-policy answering |
| Evaluate expanded source recall separately from recall at k | The final lists have 8, 8 and 5 passages, not four semantic results each |
| Keep reports separate and record search/fetch usage independently | Preserve the baseline and make the cost of the enhancement visible |

Passage words increased from 502 to 826; these are not generation tokens or a bill. `lookup_complete_within_scope` reports lookup execution coverage, not evidence sufficiency. See [policy lookup](policy-lookup.md). Context construction and answer generation remain next learning stages.

## 2026-10-17 — keep the default after a larger-candidate experiment

Compared the same E01/E04/E06 questions at k=8 with the saved k=4 baseline, preserving corpus/model/query input and policy date. Expected-section results changed from 1/1, 2/3, 1/2 to 1/1, 2/3, 2/2. First four ranked IDs were unchanged. SIM appointments appeared sixth for E06. The missing E04 identity passage was verified in Pinecone by direct ID fetch but did not rank in the first eight.

Keep default k=4 pending a targeted improvement: doubling candidates recovered one gap but missed another and increased returned passage words from 502 to 947 across three questions. This is not a token/cost estimate or broad quality benchmark. The experiment consumed 4 reported read units including the diagnostic fetch. No application or index changes. Next evaluate explicit policy-ID/reference lookup with the same cases; do not add a framework or claim improved answer accuracy from this experiment.

## 2026-10-17 — establish retrieval before improving it

| Decision | Reason | Evidence or limit |
| --- | --- | --- |
| Same local model digest and model-specific query prompt | Keep query/document vectors compatible | 768-dimensional queries; changed-model rejection tested |
| Retain cosine search and top_k 4 | Measure a baseline before tuning | E01 1/1, E04 2/3, E06 1/2 expected sections |
| Validate index and returned evidence without writes | Search the verified corpus and reject stale sources | Real read requests; source checks tested |
| Start in the terminal and use LangChain Document results | Keep this phase focused and observable | Streamlit search deferred |
| Separate authored cases from generated result reports | Preserve references and dated measurements | Generated JSON ignored; results documented |
| Measure section recall, not claim answer accuracy | Related text can omit essential evidence | Missing ID/appointment sections recorded; answer results null |
| Defer advanced retrieval until reviewing the gaps | Teach and compare one change at a time | No rewriting, reranking, hybrid search or remote metadata filter |

All 144 tests passed. Three searches reported 3 read units, with no paid inference or plan upgrade. Official API/model instructions and metering were checked on 2026-10-17. The policy date remains 2026-10-15.

## 2026-10-15 — store and verify the real corpus in Pinecone

| Decision | Reason | Evidence or limit |
| --- | --- | --- |
| Use official SDK 10.0.0 with named schema/document fields | Follow current API without hiding the storage steps | Created and fetched a real named-vector index successfully |
| Use AWS us-east-1, cosine and 768 dimensions | Starter-compatible region and active local embedding settings | Actual index configuration checked |
| Namespace `telecom-demo-v1` represents the demo corpus | Keep an explicit corpus boundary | 33 records verified; namespace does not replace eligibility rules |
| Revalidate source text, metadata, model digest and date before upload | Prevent stale local artifacts from entering storage | Local rejection tests and real corpus checks |
| Tag the index with project, model digest and corpus hash | Detect another model/corpus before writes | Changed destinations stop; synchronization is deferred |
| Verify unchanged existing data without another application-level write | Avoid needless overwrite usage | Simulated rerun test; real run was the initial upload |
| Fetch every ID and check count, text, metadata and vectors | An acknowledgement alone does not prove source retention | All 33 matched; fetch reported 4 read units |
| Keep generation and semantic retrieval for the next lessons | Storage correctness and answer quality are separate outcomes | Neither quality has been measured |

All 127 tests passed. Public Starter terms checked on 2026-10-15; account plan/remaining quota remain user-reported or unknown. No paid subscription change. The user requested a step-by-step explanation before further features; the next work should preserve that teaching pace.

## 2026-10-15 — prepare the complete local embedding corpus

| Decision | Reason | Verification or limitation |
| --- | --- | --- |
| Rebuild eligible sections from current sources and date | Prevent outdated exports from controlling ingestion | 33 sections from 11 policies; archived SIM excluded |
| Reuse only matching model digest, configuration and exact formatted input | Stable IDs do not detect content/model changes | Changed-passage/model tests; real unchanged rerun made no embedding requests |
| Refresh source metadata on reuse | Keep ownership and source labels current without needless computation | Metadata-only change tested; changed titles re-embed |
| Process one passage per request, keeping the model warm | Keep per-passage usage visible with minimal memory reloads | 32 real requests; final request unloads model; no parallel workers or new abstraction |
| Save only a complete validated snapshot | Preserve a prior complete artifact when a request fails | Failure-preservation test; partial progress is not checkpointed |
| Remove obsolete sources locally only | Avoid pretending local replacement updates remote storage | Remote deletion/version cleanup remains separate |

All 114 tests passed. The real corpus contains 33 vectors with 768 values and 1,808 reported input tokens; initial new usage was 1,745. No external model/Pinecone calls or pricing changes occurred during preparation.

## 2026-10-15 — local embeddings and Pinecone record preparation

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Follow the user's choice of local Ollama while no OpenAI key is available | Allow real embeddings now without a billed inference service | One real authority embedding saved; generation provider remains unchanged and unconfigured |
| Use embeddinggemma:300m with 768 dimensions | Dedicated downloadable text model supported by installed Ollama | Model/version-specific official sources checked; digest recorded; retrieval quality still needs evaluation |
| Use the model's document prompt/title and preserve original text separately | Match documented input format while retaining exact policy evidence | 63 reported tokens in the real example; older OpenAI counts are not reused |
| Retain OpenAI settings under openai_embedding | Keep previous lessons reproducible without confusing them with the active provider | Earlier commands explicitly identify themselves as comparisons; paid use remains disabled |
| Use the documented local HTTP API with Python's standard library | Avoid another dependency for two small requests | Loopback addresses only, no proxies/redirects, installed local model, truncation disabled, no retries |
| Map chunk_id to id, vector to values, and original text into metadata.text | Keep evidence and citations available with future search results | Flat types, source labels, dimensions and conservative metadata size checked locally |
| Keep API usage/cost records locally | Avoid putting operational accounting into retrieval metadata | Future application cost tracking remains separate |
| Target a 768-dimensional cosine index; keep Pinecone as the store | Index and query vectors must use the same model and dimensions | Index creation/upload not implemented; proposed namespace still telecom-demo-v1 |
| Record Starter as user-reported; do not assume Builder credits are active | Account existence and pending credits do not verify available quota or future charges | Private key not configured; actual plan/quota inspection needed before cloud writes |

Sources checked 2026-10-15: [Ollama model](https://ollama.com/library/embeddinggemma), [Google 300M model/prompt card](https://huggingface.co/google/embeddinggemma-300m), [Ollama API](https://docs.ollama.com/api/embed), [Pinecone record format](https://docs.pinecone.io/guides/index-data/upsert-data), [metadata constraints](https://docs.pinecone.io/guides/index-data/indexing-overview#metadata), [Pinecone pricing](https://www.pinecone.io/pricing/). All 103 tests passed plus one real local embedding acceptance run. No remote index, upload or paid use was enabled.

## 2026-10-15 — one-chunk embedding integration with local simulated tests

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Use the official OpenAI SDK directly with LangChain Document input | Keep the request visible while retaining the user's chosen container | SDK 3.31.0 installed and locked; no LangChain chain/agent added |
| Begin with AUTH-1001-v1's delegation section | It is a familiar approved example with measured 50-token input | One passage only; full-corpus batching and Pinecone remain later work |
| Default the command to preview | User has no API key and explicitly requested local preparation/testing | Default path reads no credential, creates no client and saves no vector |
| Make the existing service-use flag an actual live-mode gate | Keep paid calls disabled until account and cost review | False in the project; live mode also requires an explicit option and estimated allowance |
| Check per-input size and the estimate before calling | Avoid sending oversized input or exceeding the selected local allowance | Allowance is per attempt, not a provider/cumulative billing cap |
| Disable automatic retries and configure a 30-second timeout | Make the first example one visible request attempt | Timeout may still involve billable processing; inspect usage before another attempt |
| Validate response identity, length, numeric values and usage | Keep malformed results out of later storage | Structural validation cannot establish semantic quality |
| Preserve text, metadata, model/dimensions and both usage estimates | Support later tracing and cost reconciliation | Save only a successful response; no real output file exists yet |
| Stop if the target output already exists | Encourage inspection/reuse before another paid submission | Broader content-change detection and caching are deferred |
| Test the installed SDK with simulated HTTP responses and blocked sockets | Exercise the request/response boundary without credentials or charges | 85 tests passed; no live API acceptance or retrieval quality claim |

Official sources checked 2026-10-15: [embedding request/response](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create), [SDK retries and timeouts](https://developers.openai.com/api/reference/python), [model price](https://developers.openai.com/api/docs/models/text-embedding-3-small). The user confirmed that API access is still unavailable and requested local work; no paid service use was enabled.

## 2026-10-15 — measure embedding inputs locally before service integration

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Use `tiktoken` and the configured `cl100k_base` encoding | Apply the selected model's documented tokenizer instead of estimating tokens from words | Version 0.14.0 locked; reject unknown models or mismatched encodings |
| Count exact chunk `page_content` without metadata or added headings | Define a visible, repeatable baseline input | Any later text additions require recounting; evaluate retrieval quality before changing the input |
| Freshly prepare eligible section chunks for the report | Avoid measuring an older saved snapshot after source/date changes | Reuse validation, eligibility and section chunking; report does not overwrite the existing export |
| Check per-input token limits and flag oversized sections | Preserve rule/condition text and reveal a need to review boundaries | No truncation or automatic rechunking; request-wide limits remain a later integration task |
| Read a dated, model-matched USD standard rate from pricing YAML | Keep rates outside code and make the estimate auditable | Reverified USD 0.02 per million input tokens today; unknown or invalid prices stop the estimate |
| Use decimal arithmetic for the estimate | Keep a tiny nonzero amount visible | Show eight decimal places for the current report; do not label the rounded display as a measured bill |
| Add a separate local report command | Keep this learning step focused and usable without credentials | No embedding SDK, paid request, Pinecone upload or UI feature added |

Official sources checked 2026-10-15: [tokenizer guidance](https://developers.openai.com/api/docs/guides/embeddings), [input requirements](https://developers.openai.com/api/reference/resources/embeddings/methods/create), [model price](https://developers.openai.com/api/docs/models/text-embedding-3-small), [first-use vocabulary download](https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken).

Measured 33 chunks, 1,404 tokens and 26–57 tokens per input; all passed the configured 8,192-token limit. One corpus pass is estimated at USD 0.00002808, excluding all other application usage and costs. All 68 tests passed, including the 16 new checks. This is not a retrieval-quality score, provider bill or verification of account access.

## 2026-10-15 — adopt LangChain Document containers at the user's request

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Use `langchain_core.documents.Document` for loaded policies and chunks | User explicitly requested the LangChain library's container | Installed version 1.6.10 is locked in `uv.lock`; broader framework integration is not implied |
| Keep our validation, eligibility and chunking functions | Preserve the visible learning steps and policy rules | The container supplies structure, not governance or retrieval |
| Keep section boundaries in policy metadata and copy source details into each chunk | Preserve complete conditions and source tracking | Drop the parent's full section collection from chunks; metadata copies must be independent |
| Store dates as YYYY-MM-DD strings | Keep metadata readable and JSON-serializable | Convert to dates for eligibility; provider-specific metadata conversion remains future work |
| Store stable section IDs in `Document.id` | Identify the same passage across unchanged runs | Keep the existing policy/version/section/method scheme; fixed-window examples have no persistent IDs |
| Preserve the saved JSON contract | Avoid changing the user's inspected records or later input unnecessarily | Export `id` as `chunk_id` and `page_content` as `text`; full content matches the pre-migration snapshot |
| Record the explicit exception in Week2's instructions | Future work should honor the library choice without confusing it with a folder | No change to the separate practice project or root workspace instructions |

Official API checked 2026-10-15: [LangChain Document](https://reference.langchain.com/python/langchain-core/documents/base/Document). All 52 automated tests passed. The real preparation command retained 33 chunks and 1,169 body-text words. Three viewer scenarios passed their assertions, with a separate Windows temporary-folder cleanup permission error at exit. No embedding, Pinecone or hosted tracing integration was added; no API usage charge occurred. Metadata remains mutable, and these local checks do not establish retrieval quality.

## 2026-10-15 — select the first embedding model

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Select `text-embedding-3-small` for baseline evaluation | The project prefers OpenAI and this offers a lower input-token rate than `text-embedding-3-large` for our small English corpus | Model recorded in settings; retrieval quality and account access remain unverified |
| Keep the default 1,536 dimensions | Begin without adding a dimension-reduction experiment | Use the same model/dimension for questions and documents; configure the future index accordingly |
| Record `cl100k_base` and the documented 8,192-token input maximum | Make the next token-counting lesson model-specific | Specifications only; no tokenizer, limit enforcement or embedding client implemented yet |
| Record USD 0.02 per million input tokens, checked today | Keep the selected embedding price explicit and sourced | Actual bill depends on sent tokens and account terms; recheck before paid use |
| Complete selection before service integration | User is learning step by step and has reported no OpenAI API key | Next step is local token counting; credentials, account access and spend review precede API calls |

Official sources fetched on 2026-10-15: [small model and price](https://developers.openai.com/api/docs/models/text-embedding-3-small), [large model and price](https://developers.openai.com/api/docs/models/text-embedding-3-large), [vector dimensions and tokenizer](https://developers.openai.com/api/docs/guides/embeddings), [API input limits](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create). This is a baseline choice, not a measured superiority claim. No vectors, model requests, cloud resources or service charges were created.

## 2026-10-15 — local section-chunk preparation

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Apply the provisional `section-v1` strategy to eligible policies | Current sections are short; preserve the inspected rule and its conditions without fixed-window remainders | Local baseline, not proven retrieval quality; validate actual model limits before embeddings |
| Reuse validation, eligibility and section chunking in one preparation module | Keep the steps visible and avoid a second implementation or framework | No dependencies or service SDKs added |
| Identify a record by document ID, section ID and method | Make unchanged reruns repeatable and distinguish policy revisions | IDs identify passages, not content fingerprints; define a new scheme if chunk boundaries change |
| Save original loaded text with full source/governance metadata | Preserve evidence and allow later citations from actual source details | Local JSON with nullable dates; provider-specific serialization remains pending |
| Keep the strategy and output file in settings | Separate the preparation choice from code; comparison sizes stay teaching-only settings | Only `section-v1` is supported; output must be a JSON file inside `data/processed/` |
| Sort records and replace the full generated snapshot | Avoid duplicate appends and remove obsolete local records after a successful rebuild | Future Pinecone synchronization must separately handle obsolete vectors |
| Finish a temporary file before replacing the previous export | Avoid replacing a complete export with a partial write | Failure leaves any earlier output; command warns it is not evidence of current success |
| Reject empty eligible sets, duplicate chunk IDs and overlapping approved versions | Do not silently produce ambiguous or unusable preparation results | Resolve source/date/settings errors before continuing |
| Ignore `data/processed/` in Git | Sources and code can recreate the generated file | Regenerate after source or eligibility changes; no commit or publication performed |
| Preserve long sections without silently truncating them | Keep local inspection faithful while no model has been configured | Add model-aware token limits and an explained long-section policy before paid calls |

Verification: all 50 automated tests passed and the actual command saved 33 chunks from 11 eligible policies, excluding the archived SIM version. Text totals 1,169 words. See [the preparation lesson](chunking-experiment.md) for format, rerun behaviour and limitations. No cloud calls or charges occurred.

## 2026-10-15 — reusable comparison tool and provisional baseline

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Add a small Python module run with `python -m retail_copilot.chunking` | Make the teaching experiment repeatable without adding a framework or dependency | Local inspection only; no cloud integration |
| Keep example document, section and sizes in `settings.toml` | Separate teaching choices from splitting logic | Defaults reproduce the discussed 20-word/five-word example |
| Restart fixed-size splitting at section boundaries | Retain a single unambiguous section reference for each passage | Clearly distinguish this baseline from windows spanning an entire document |
| Keep references to the original document and section on each chunk | Preserve all source metadata for inspection and later citation design | Define flat upload records and persistent IDs before ingestion |
| Select one existing section per chunk as a provisional baseline for the current corpus | All 33 eligible sections are 21–46 words; this keeps the inspected authority rule intact and avoids tiny fixed-window remainders | Not validated for retrieval or answers; revisit long sections and actual model input limits |
| Keep the whole-section method uncapped in the comparison | Make the method's behaviour visible rather than silently introduce another splitting rule | Long-section test documents this limitation; not ready for unrestricted ingestion |

All 38 automated tests passed after this change. The [comparison report](chunking-experiment.md) records source text, library-wide counts and limitations. No API calls, index writes or inference costs were incurred.

## 2026-10-15 — first chunking lesson

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Begin with one 43-word authority section and a temporary local preview | The user requested slower, explanation-first learning | No application code changed |
| Compare 20-word chunks with zero/five-word overlap against the complete section | Make boundaries and duplicated words directly visible | Teaching values only; not runtime defaults |
| Treat whole-section chunks as a candidate for this structured corpus | This example keeps the full 28-word rule and its related limitation together; both fixed-size variants split it | Compare the wider library and long sections before selecting a baseline; measure retrieval later |
| Separate word duplication from latency and billing claims | Five-word overlap added 10 words here, but words are not billable token counts and response time was not measured | Measure real usage and latency when services are integrated |
| Retain direct Python while noting available LlamaIndex credits | Credits alone do not identify a needed service or change the learning objective | Verify service coverage and usefulness if integration is considered |

Actual output, source references and limitations are recorded in [the chunking experiment](chunking-experiment.md). No external API calls or resource changes were made.

## 2026-10-15 — Phase 1 corpus and metadata

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Use one JSON file per document version in `data/knowledge/` | Keep metadata and sections together, with a concrete source filename for each policy version | Replaces the general-retail `data/policies.json` format |
| Author 11 current documents and one archived SIM version | Cover ten telecom topics plus evidence handling and outdated guidance | Entire corpus is fictional; business accounts and real customer decisions are outside scope |
| Preserve named sections and version-specific document IDs | Prepare stable source references and a meaningful section-aware chunking comparison | No chunks or embeddings yet |
| Derive filenames from loaded files | Source labels must reflect actual evidence rather than a claimed source string | Covered by a source-spoofing test |
| Keep review dates separate from effective end dates | A review reminder does not itself revoke a policy | Viewer shows overdue reminders; explicit status/date changes govern exclusion |
| Reject overlapping approved versions | A higher version number alone is not a documented precedence rule | Semantic conflicts across distinct policy IDs still require review/evaluation |
| Record `telecom-demo-v1` as the planned namespace | Identify the corpus revision separately from record-level metadata filters | Only a local setting; no Pinecone index or namespace exists |
| Start with 15 evaluation specifications and grow to approximately 30 | Cover all eight question categories while keeping this learning step focused | Live results remain null; add semantic-conflict and adversarial cases later |
| Keep E11 as a controlled-context test | Test missing authority evidence even though the full corpus contains the authority policy | Future runner must withhold non-specified documents and score separately from retrieval |

Metadata constraints were checked against current official Pinecone documentation and are recorded in `docs/knowledge-base.md`. The future metadata serializer, SDK integration and model choices remain separate stages. This milestone made no external service requests.

## 2026-10-15 — local configuration readiness

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Continue local preparation while credentials are unavailable | The user has no OpenAI key and expects Pinecone credits; document design and chunking need neither | Cloud work still requires access, credit/plan review and a spending limit |
| Keep the planned OpenAI/Pinecone architecture | Missing credentials are a scheduling dependency, not a reason to silently switch providers | Model IDs and index details remain unset |
| Use python-dotenv for the local presence check | Its documented reader avoids a custom configuration parser | Version 1.2.4 installed and locked; service SDKs deferred |
| Read only Week2's `.env`, with process environment values taking priority | Avoid accidentally loading another project's credentials and preserve explicit environment settings | Covered by tests; blank environment values intentionally override file values |
| Report presence only and avoid network calls | A learner can inspect readiness without exposing values or incurring API charges | Does not validate credentials or enforce a budget |
| Initialise a separate Git repository in Week2 | Inspection found that Git otherwise used the home directory as its root | Local boundary created; ignore rules checked; first commit pending |
| Treat missing authority evidence as uncertainty | The user's SIM example highlighted a distinction between lack of evidence and evidence of a prohibition | Add a partial-evidence case when building the telecom evaluation set |

Official configuration-reader documentation checked on 2026-10-15: [python-dotenv usage](https://bbc2.github.io/python-dotenv/#load-configuration-without-altering-the-environment) and [API reference](https://bbc2.github.io/python-dotenv/reference/).

## 2026-10-15 — updated Week2 brief

| Decision | Reason | Status or revisit condition |
| --- | --- | --- |
| Target fictional telecommunications retail guidance | The user updated Week2 `AGENTS.md` with ten telecom knowledge areas | Content migration pending |
| Plan OpenAI embeddings and generation | The updated project brief explicitly prefers them | Supersedes the earlier provisional Ollama choice; account readiness and spending limit pending |
| Consider `text-embedding-3-small` and `gpt-6-luna` as initial candidates | Current official documentation lists low usage rates appropriate for a baseline experiment | Not configured or tested for this account; evaluate quality before finalising |
| Begin with orientation and documentation alignment | The user requests an explanation-first coaching sequence | No application code or external accounts changed in this phase |
| Preserve the runnable starter during migration | Domain, metadata and model changes should each be testable | Replace the generic corpus during Phase 1 with updated tests |
| Plan 30 evaluation questions, starting with a 15-question subset | The brief names both sizes in different sections | Record coverage and expand from the initial subset |
| Keep existing `app.py`, `src/retail_copilot` and TOML settings layout | The proposed structure is illustrative; the established layout is already small and understandable | Add modules when a concrete stage needs them |

Candidate prices were checked against official sources on 2026-10-15 and recorded in `config/pricing.yaml`. Public rates do not establish model access, answer quality or a paid-call authorisation.

## 2026-10-14

| Decision | Reason | Revisit when |
| --- | --- | --- |
| Keep Week2 separate from Langchain practice | Each project has its own purpose and Python environment | Only if the user changes scope |
| Use direct Python components | Make document loading, retrieval and generation visible while learning | Evaluation demonstrates a concrete need for additional orchestration |
| Build the evidence library first | Approval and source metadata must be trustworthy before retrieval | Adding new document formats |
| Use fictional Harbour & Lane policies | Demonstrate retail behaviour without real customer or business data | Remain synthetic throughout this learning project |
| Use a fixed, visible demo date | Make expiry checks reproducible | Introduce live-date behaviour with timezone tests |
| Reject overlapping approved policy versions | Avoid silently selecting a potentially incorrect rule | Define an explicit precedence and review process |
| Plan Pinecone retrieval | Required by the project brief | Account setup, quota review and embedding-dimension selection |
| Provisionally reuse Ollama for generation | A local model is already installed and the user has no OpenAI API key | Grounding, latency and answer-quality evaluation |
| Defer embedding model and index creation | Dimension and billing choices must be explained first | Next milestone, after account status is known |

The Streamlit package is the only application dependency needed for milestone 1. Pinecone and model SDKs will be added when those components are introduced and checked against current official documentation.

## 2026-10-19 - Final demo verification

Retain a narrow self-service guidance guard in conversation.py and pipeline.py after a real rehearsal misclassified "Can I book one anyway?" as execution. Change only that incorrect action status to insufficient_evidence with available source guidance; preserve the raw model draft and do not promote completeness. Explicit and mixed execution requests retain the action boundary. Two new conversation tests and two pipeline tests cover this distinction; the full 398-test suite and targeted real AppTest retest passed. Complete the bounded local demo milestone with original failures, separate reviews and usage subtotals preserved. A broader semantic classifier and production deployment are outside this change.
