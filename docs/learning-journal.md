# Learning journal

## 2026-10-19 - Preparing the GitHub submission

A shareable repository needs instructions for someone who does not have our prepared computer. Added a fresh-install guide covering the offline policy viewer, tests, model downloads, private environment configuration, corpus preparation, Pinecone upload and chat startup. Removed personal machine paths and the private report link from shareable documentation. Model downloads, credentials and generated results remain outside Git; authored policies and evaluation scenarios are included.

Validated an isolated export of the staged files: all 398 tests passed in 5.373 seconds using existing installed dependencies and cached tokenizer vocabulary, without the local `.env` or generated results. This checks the shareable source package, not new account provisioning or a fresh model download. The user chose a public GitHub repository for reviewer access.

## 2026-10-19 - protect local requests from idle sleep

Added a request-scoped Windows idle-sleep guard around local Ollama HTTP opening and response reading. It restores the previous thread state on success or failure, requests no display/away mode and leaves persistent power settings unchanged. Deliberate sleep and lid closure remain respected; unsupported platforms do nothing. The temporary test helper was stopped before final E05 verification. The lesson is to separate machine availability from model response quality.

The full offline suite passed 394 tests in 12.824 seconds. Final answer review links original requests, separate fresh reruns and service-free presentation replays; these are not a single new 14-case final-version batch. Final E05, controlled missing-evidence and six-turn app verification are still pending. Earlier failures remain preserved.

## 2026-10-19 - distinguish policy wording, uncertainty and operating conditions

The source-passage presentation now has a narrow named-policy overview fallback when the model returns no claims: it uses exact matching passages already retrieved. When guidance exists alongside an insufficient-evidence status, neutral introductory wording avoids asserting an unverified gap; missing referenced policies still receive an explicit limitation. Original model classifications remain recorded and are not claimed fixed. Exact wording, appropriate selection and correct uncertainty are separate checks.

The full offline suite passed 385 tests in 12.235 seconds. Windows Kernel-Power events confirmed Modern Standby from idle timeout during long live-test gaps. Keep the computer awake and plugged in; retry a failed request once the computer and services have recovered. A temporary bounded awake helper was used for verification without persistent power-plan changes. The live comparison, preserved reruns and app rehearsal still await final review; interrupted wall-clock timings are not normal model-latency measurements.

## 2026-10-18 - preserve source wording and prepare the runnable demo

The user authorized finishing the demonstration without further teaching-question blockers. Prompt-only experiments, including compact v2 and question-part v3, still omitted required conditions. The active chat now uses `prompts/answering-grounded-v2.md` with `source_passages`: validated model source IDs select whole supplied passages, with same-document and direct-reference expansion inside the current pack. Model policy prose is discarded from the displayed answer; original drafts and metadata remain privately inspectable.

The key lesson is that exact-source assembly preserves wording but does not guarantee relevance or complete coverage. It can add extra paragraphs or retain a cautious/incorrect status. Deterministic routing now handles clear requests and narrow clarification replies while preserving intent; a separate action guard enforces guidance-only behavior for recognised execution requests. These bounded rules still require live evaluation.

The full offline suite passed 375 tests in 17.487 seconds. The Python launcher started a real test instance on 8502 with HTTP 200 and that instance was stopped; the owned 8501 server also returned HTTP 200. PowerShell blocked the optional script, so the primary launcher runs Python directly without changing security policy. The fresh 14-case live comparison and six-turn real AppTest rehearsal still await final results. Historical 6/15 and 3/5 baselines are preserved, not relabelled as current quality measurements. See [demo readiness](demo-readiness.md) and [the operating guide](demo-guide.md).

## 2026-10-18 - evaluate five questions through the actual chat

Built an offline-preview/live-run evaluation command that calls the same `run_chat_turn` as Streamlit with an empty history for each case. Expected answers stay outside the pipeline. Fresh evidence, answers and usage are saved separately from the old baseline; Codex semantic reviews remain separate from execution records. All 12 focused runner checks and the full 322-test suite passed.

All five live requests completed; three met the established scenario minimums under Codex review, not independent human review. E05 received all required passages but omitted concrete ID conditions and overstated the billing-contact restriction. E09's clear action request was incorrectly classified as a fragment and clarified before search. E08 safely declined to invent a price but could name the missing Canadian price and give a more specific next step. This demonstrates why retrieval, claim support, completeness and response behavior need separate checks; these cases do not test follow-ups or production accuracy.

The user correctly identified that retrieving the right passage but omitting an essential condition is an answer-generation completeness failure.

The run reported 6 Pinecone read units, 63 query tokens, 6,058 generation input tokens, 328 generation output tokens and 284.34 seconds. Resolver token usage and monetary charges/electricity remain unknown, apart from no external local-generation API charge. The user-reported Starter allowance was not inspected. Next: focused E09 routing and E05 completeness corrections, followed by a preserved comparison run. See [results and review boundaries](chat-evaluation.md). No runtime/prompt fixes were made in this phase.

## 2026-10-18 - accept the UI and focus on grounded knowledge answers

The user said "UI part is fine" and asked how to check that knowledge scenarios produce correct, grounded answers. This accepts the current interface; browser rendering/accessibility remains independently unverified.

The saved historical baseline passed 6 of 15 cases, with 9 failures, under Codex review rather than independent human review. A valid citation can still accompany an incomplete answer: the E02 example omitted the unexpired/matching-name identification conditions and the distinction between identity and account authority. The next evaluation should inspect the actual scenario, retrieved evidence, each claim's support, completeness and response status.

The old `evaluate.py` route bypasses `run_chat_turn`, so it does not measure current chat gates, aliases or bounded memory. Plan to evaluate the actual chat route while preserving the historical baseline. This documentation update adds no evaluation results, tests or service calls.

## 2026-10-18 - handle acknowledgements without policy retrieval

**Observed and changed:** The user reported that "OK thanks" cleared the conversation. The baseline mocked interface test retained both exchanges/four messages, so that clearing was not reproduced. A separate baseline resolver check revealed an unnecessary model-resolution call and clarification. Complete acknowledgements now receive a brief local reply without resolution, corpus/credential loading, model or Pinecone calls. Mixed questions and yes/no still take the normal route.

**Memory and verification:** Acknowledgements stay visible but are skipped within the latest three raw turns when selecting reference context; skipping does not extend the window or cross a failed turn. All 70 focused offline checks passed (17 interface, 32 pipeline, 21 conversation). The interface test exercises the actual acknowledgement pipeline with networking blocked, preserves history and checks the next follow-up's context. This establishes acknowledgement behavior, not the cause or resolution of the reported whole-history loss.

**Session limitation:** Polling/run-on-save and the 900-second disconnected-session lifetime were verified at runtime; the restarted server's health endpoint returned HTTP 200. No durable storage was added; refresh/new sessions or process restarts can still lose history. Browser inspection is unavailable. No live model or Pinecone calls were made.

## 2026-10-18 - remove the requested interface reminder

The user explicitly requested removal of "Don't enter customer names, phone numbers, or account details." Removed its interface container and styling. This changes presentation only; data handling and backend behavior are unchanged. The updated existing welcome-screen check passed, and the restarted local server returned HTTP 200 from its health endpoint. No model or Pinecone requests were made. Earlier reminder decisions remain recorded below as history.

## 2026-10-18 - refine mobile layout, privacy guidance and failure messages

**Change and lesson:** "Policy guidance" is now a noninteractive native gray badge, and a highlighted reminder explicitly names customer names, phone numbers and account details. At 640 pixels or less, each starter button and its caption stack together at full width. Native chat text explicitly wraps; child-span styling handles long words and preserves paragraphs. A badge describes the experience rather than offering another action.

**Failure behavior:** Service/setup problems ask the colleague to retry or contact copilot support. Evidence problems instead direct the user to the policy owner or support channel. Public errors do not disclose technical configuration or raw provider details. The natural chat remains free of visible source controls.

**Verification boundary:** All 41 focused offline checks passed: 15 interface and 26 pipeline checks. AppTest retained the entire long reply, including the ending and an unbroken identifier, with wrapping enabled; clarification, unsupported-action, setup/service-failure and reset scenarios are covered. These are simulated-service checks, not proof of real model correctness. No browser surface is available, so mobile layout and final appearance are not visually verified. No live service calls or charges were introduced. Historical results below remain evidence for their earlier revisions only.

## 2026-10-18 - improve chat readability and presentation names

**User direction:** Remove fictional/demo labels from the chat's surrounding interface. The captions now read "Your policy companion", "Policy guidance" and "Avoid sharing customer or account details." This overrides the earlier visible-notice choice, while the corpus and its metadata remain synthetic.

**Change and lesson:** The dark user bubble needed a text-colour rule on Streamlit's child `span`, because the wrapper's colour was not inherited. CSS now gives user text white-on-teal contrast and explicitly sets dark input text, a visible placeholder and caret on white. Display aliases rename Practice Basic to Connect Essential (10 GB) and Practice Plus to Connect Plus (30 GB). Questions/history normalize to the canonical names before retrieval; displayed names are applied after validation. Source text, canonical drafts and metadata remain intact. A presentation name is not a new policy or commercial offer.

**Verification and cost boundary:** Installed frontend source and the edited files were inspected. All 58 focused offline checks passed across the interface (12), pipeline (22), plan names (6) and conversation (18) modules. A network-blocked consistency check also validated all 33 saved corpus records. Streamlit's temporary-folder cleanup required normal filesystem access; the pipeline tests required discovery to load their shared fixtures. No browser surface is available, so rendering remains unverified. No source/index/model change or charged service call was made for this correction. Prior full-suite counts and live examples below remain dated history.

## 2026-10-18 - connect the natural chat to the RAG pipeline

**User direction and teaching:** The user authorized building the interface using the agreed chat instructions. The central layout and graphical direction are retained, without source expansion or diagnostics. Explained the difference between visible chat history and bounded model context: recent user questions help identify "it" or "one", while fresh approved passages remain the only policy evidence. Final appearance remains reviewable as requested; implementation was authorized.

**Built:** `app.py` now uses native Streamlit chat controls, starters, New chat, teal styling and plain-text messages. `library_app.py` preserves the original local policy viewer separately. `conversation.py` resolves or clarifies the question before retrieval; `pipeline.py` joins fresh Pinecone retrieval, bounded reference lookup, context construction and local answer generation. The accepted draft, source metadata and measured usage remain private session records; the chat displays natural text. No new dependencies or paid provider were added.

**Limits and risks:** Keep at most three recent user turns and 4,000 combined history characters for resolution, 1,000 characters per question and 30 visible exchanges. A failed turn blocks reuse of preceding topics; only later successful or clarification turns remain in the reference window. New chat clears session turns and private evidence; ordinary chats are not logged to disk. Prior assistant answers never become policy evidence. The English resolver is conservative and can over-clarify or misinterpret a follow-up. Valid source IDs do not prove claim support. The original 6/15 real-answer baseline remains unchanged and its failures remain open.

**Verified:** The final full automated suite passed 281 tests after all code changes, including 12 UI, 17 pipeline and 18 conversation checks with simulated service responses and the strengthened failed-turn history boundary. A real pipeline call for "Can I replace it?" with network connections blocked returned a clarification question and no retrieval question. The actual Streamlit page and health endpoint returned HTTP 200 at `127.0.0.1:8501`. Real appointment and follow-up requests returned supported answers with one private citation each in 94.1 and 137.5 seconds. "Can I book one anyway?" resolved to a question about an appointment for a physical SIM replacement; both claims matched the actual appointments section. These establish the tested code/state behavior, two specific live pipeline examples and server availability. They do not establish browser rendering, accessibility, general latency or broad follow-up quality; no browser surface was available. No live token/read-unit totals were printed by that check, so none are invented.

**Understanding check:** The user correctly said that prior conversation should "Understand the question, then retrieve fresh policy evidence". This demonstrates the distinction between reference context and approved evidence; it does not establish model quality or that every follow-up will be understood correctly.

**Cost and operation:** Opening chat, ordinary reruns and New chat make no service requests. Clear submissions use local model work and can use Pinecone query/fetch read units; resolving a follow-up may add local inference. No automatic retries are configured. Local electricity/hardware cost and actual Pinecone billing remain unknown; no new rate or plan change was introduced. Start chat with `.\.venv\Scripts\python.exe -m streamlit run app.py`, or the separate viewer with `library_app.py`. See [chat design and operation](chat-design.md) and [cost model](cost-model.md).

## 2026-10-18 - keep evidence handling behind a natural chat

**User direction:** The user requested a natural chat without source expansion. This supersedes the earlier choice to display expandable supporting policies in the chat. Preserve the central conversation, starter questions, New chat, input, graphical styling and planned follow-ups; remove source buttons, evidence expansions, answer diagnostics and the policy-library toggle from the preview.

**Design lesson:** The interface can present a straightforward conversation while the RAG process still retrieves approved evidence and retains source/citation metadata. Source-reference checks and semantic support evaluation remain necessary. Existing development commands, saved reports and the separate policy-library viewer provide inspection outside the chat; this design change does not introduce a new tool or remove backend citations.

**Scope and verification:** Removed source buttons, expandable evidence, diagnostics and the library toggle from the scripted preview, together with their obsolete handlers and styling. Static checks passed for markup, IDs, selector attributes, UTF-8 and absence of service calls. The same local preview address returned HTTP 200 with the updated content. Browser interaction remains unverified. The actual library app and backend are unchanged. Live chat, bounded memory and reliable ambiguity clarification remain unimplemented. No model or Pinecone requests were made. The polished appearance still needs user review before finalization. Earlier design choices and checks remain recorded below as history.

## 2026-10-18 - approve the chat layout and improve its appearance

**User direction:** The user is happy with the Focused chat layout and asked for a graphically enhanced interface. Keep that approved layout and prepare the polished appearance for review before finalization, honoring the earlier approval request.

**Design lesson:** A coordinated teal and ink palette, readable type, generous spacing, consistent icons and clearer message/source panels should help users identify where to ask, read and inspect evidence. These are presentation choices; attractive styling does not establish answer accuracy.

**Scope and verification:** Updated the scripted preview with the new palette, icons, spacing and distinct message/source panels. Markup and encoding checks passed, and eight checked colour pairings exceeded 4.5:1 text contrast in both themes. Manual review found no blocking selector or interaction-code issue. Windows denied the local browser rendering attempt, so runtime interaction and rendering are not verified. Streamlit remains the policy-library viewer; live chat, bounded memory and reliable ambiguity clarification are not implemented. No model or Pinecone requests were made. See [chat design](chat-design.md) for the review and validation boundaries.

## 2026-10-18 - evaluate real answers and discuss the chat design

**User direction:** Expedite real generation and the initial evaluation, then move to Streamlit. Discuss an intuitive chat layout before configuring it. The user selected natural follow-up questions with bounded conversation memory and the Focused chat direction. They subsequently explicitly requested approval before the interface is finalized, with further discussion to make it more intuitive. This layout selection is not final design approval.

**Teaching:** Distinguished a completed response, a real citation, a supported claim and a complete answer. The E04 comparisons show why those are different: the smaller model omitted the positive Training ID requirement; a generic prompt trial did not fix it and introduced an unnecessary fallback; the non-thinking 4B candidate also broadened some policy conditions. Results and exact cited passages are preserved in [the answer review](answer-review.md).

**Built and checked:** Added the 15-case evaluation runner and controlled-context support. The full local suite passed 234 tests. The runner records case/model/prompt/corpus identities, reuses matching saved evidence and answers, preserves per-case failures and keeps semantic reviews separate. E11 supplies only the authored SIM document, makes no retrieval request, and is excluded from retrieval recall. Expected answers never enter the generation prompt. Real baseline results are recorded separately in [evaluation](evaluation.md).

**Chat proposal:** The user chose focused chat with expandable sources after comparison with a persistent evidence panel. A scripted design preview demonstrates the layout, not a live backend. Proposed memory uses a bounded set of recent user turns to resolve references, then fresh approved retrieval. Previous assistant answers are not policy sources; New chat clears the conversation. The three-turn limit is a proposal, not a deployed setting. Prepare a revised, reviewable interface and obtain explicit user approval before finalization; the design details remain open. See [chat design](chat-design.md). Streamlit has not been changed.

**Cost:** Local model comparisons use hardware, electricity and model downloads, with no external generation charge. The additional non-thinking 4B model download was about 2.5 GB. Evaluation may use new Pinecone read units for missing retrieval; reused historical usage must not be counted as new. No account-plan upgrade is made.

**Baseline result:** All 15 real model requests completed. Semantic search found 17/23 expected sections; bounded lookup increased that to 21/23. Separate Codex reviews passed six complete cases and identified omissions, ambiguity handling and status errors in the others. Of 26 written claims, 22 were supported and four partially supported. These are development observations on synthetic questions, not production accuracy. The baseline used 18 new RU and 224 new query tokens; answer generation reported 27,590 input and 1,739 output tokens. Full evidence and reviews are preserved.

**Focused improvement:** Prepared a separate instruction variant that emphasizes actual criteria, linked conditions, source-declared limitations and response categories based on user intent. A local size check caught an overlong draft; repeated instructions were tightened, without cutting policy sections or increasing model limits. All 15 final instruction/evidence combinations passed the conservative input allowance. The comparison reuses the same model and evidence, with separate output files and no new Pinecone searches. Results are recorded in [answer evaluation](answer-evaluation.md).

**Comparison outcome:** All fifteen comparison requests completed. Seven cases passed separate Codex review, versus six in the baseline; the improvement was the bill-waiver response. Nevertheless, reject this variant: the controlled missing-authority case turned uncertainty into an invented prohibition. The pass count hid a more serious failure within an already failing case. The comparison consumed zero new Pinecone reads, with 27,785 local input and 2,121 output tokens. This illustrates why regression review matters as well as a total score.

**User-directed clarification:** The user asked the model to request specifics for an ambiguous question, giving "Can I replace it?" as an example. Explained that the existing general instruction had not been followed in the actual test. Prepared a stronger ambiguity paragraph on top of the original instructions, preserving its other grounding rules. The intended response asks what the user means and what happened, with no premature policy claims. A separate targeted test is required before claiming it works; chat memory and final interface approval remain separate work.

**Actual clarification results:** The stronger wording was tested on E01, E07 and E11. E01 still answered the clear appointment question correctly. E07 still assumed a SIM and gave policy claims rather than asking for specifics. E11 lost its baseline insufficient-evidence response, although it did not invent the broader trial's prohibition. Reject the stronger wording and restore `prompts/answering.md` as the active prompt. A further isolated E07 experiment repeated the actual question after the unchanged evidence; it also failed, so no application-format change was adopted. The prepared additional question "Can I change that?" was not sent to the model after the candidate failed these checks. These are recorded failures, not a working clarification feature. A question-only clarification check before retrieval is a future candidate, not implemented or verified here.

**Verification boundary:** The full suite passed 234 automated tests earlier in this change; after the instruction experiments, the 18 answering and 23 generation tests passed again. These establish code/format behavior with simulated responses, not model compliance. The stronger clarification wording also passed local input-size checks for all fifteen evidence packs; fitting the model's input limit did not make the behavior correct.

## 2026-10-18 - connect a local answer writer and make progress visible

**Teaching:** Explained the different jobs of the embedding model (searchable numbers) and answering model (a written draft), then showed the files before editing. The user asked how much work remains. Described five milestones: real generation and review, evaluation, the question interface, complete-journey checks, and the final learning/operating walkthrough. These milestones complete a fictional demonstration, not production deployment.

**Built:** `generate.py`, local generation settings, shared loopback transport support for model inspection/chat, safe error messages, 18 generation tests and [the local-generation lesson](local-generation.md). The command revalidates evidence, uses structured responses, renders metadata citations and preserves earlier files. Empty evidence makes no model requests. Hidden thinking is neither saved nor printed.

**Verified:** All 213 automated tests passed. They use simulated responses to verify code behaviour, including failure handling and a deliberately false claim whose valid source ID must not be mistaken for semantic support. The preview ran successfully against the saved E04 context. The first real CPU attempt ended after roughly five minutes without an accepted answer; no output was saved. It is not counted as a successful generation or claim-support test. The timeout message was improved and a separate retry uses a 600-second allowance.

**Learning check:** Asked whether a correct stolen-SIM answer also establishes correct behaviour on missing evidence and action requests. Response pending; understanding is not assumed.

**Follow-up:** The 600-second retry explicitly timed out too. Explained the latency problem and downloaded the smaller non-thinking `qwen2.5:1.5b` model for the same saved-evidence experiment. This changes the answering model, not the embedding model, Pinecone index or RAG design. Its quality is not assumed equivalent.

**Cost:** This increment uses local inference and saved evidence. No new Pinecone or OpenAI requests or plan changes were made. The smaller model download used approximately 986 MB of internet transfer and local storage. Local computing cost is unmeasured, including unsuccessful attempts. Real model observations and claim review must be recorded separately from the automated test result.

## 2026-10-18 — distinguish a valid reference from a supported claim

The user correctly answered that a real appointments citation does not make a claim about identity verification trustworthy: we must check whether the passage supports that claim. This demonstrates understanding of the distinction between source-reference validity and semantic claim support. The current draft checker verifies source IDs and renders metadata citations; actual model claim support still requires evaluation. No code, model settings or service usage changed for this learning check.

## 2026-10-17 — prepare answering rules and check citation references

**Teaching:** After confirming that oversized sections should be reviewed rather than cut, the user approved the next step. Explained the difference between instructions, a model draft and source-reference checks. Showed the flow and proposed files before editing. Asked whether a real appointments citation supports a claim that identity verification is unnecessary; the user answered on 2026-10-18, recorded above. Source existence and claim support must remain separate concepts.

**Built:** `prompts/answering.md`, `answering.py`, `[answering]` limits and 18 tests. The local preview revalidates the context, keeps application instructions separate from evidence, and defines supported/insufficient/clarification/action statuses. Drafts need per-claim source IDs; malformed fields, unknown/repeated IDs, inline citations/URLs and exceeded limits are rejected. Citation names and sections come from the actual registry. Empty context uses a fixed insufficient-evidence fallback without preparing a model request.

**Verified:** All 195 tests passed. The actual E04 preview has S1–S8 and 8,991 message-content characters. A manual example copied the training-identification passage and rendered its S7 citation; an invented S99 was rejected. These are hand-written demonstrations, not generated model answers. Deliberate wrong-claim tests show that valid source membership alone does not verify claim support or transactional assertions. Those semantic checks are explicitly unmeasured.

**Cost and preservation:** Preview and demonstration ran with network connections blocked; zero service calls and no external request charge. Previous context, retrieval and embedding files passed unchanged-hash checks. Local computing cost and future model tokens are unmeasured. No new prices, API keys, provider choices or account changes were introduced. Saved `data/processed/answering-preview.json` separately.

**Next:** Choose and connect an answering model, explain its costs/limits, and evaluate real drafts against evidence. Existing absence of an OpenAI key remains relevant; no new key status has been assumed. See [the answering lesson](answering-instructions.md).

## 2026-10-17 — prepare a labelled evidence pack locally

**Teaching:** The user asked for a slower explanation of policy lookup before context construction, then approved proceeding. Explained context as the evidence folder handed to an answer writer: question plus whole passages and source labels. Showed the flow and file plan before implementation. When asked whether an oversized section should be cut or reviewed, the user correctly chose to stop for review because the ending may contain an essential condition. This demonstrates understanding of why the current builder stops rather than silently truncating a policy section.

**Built:** `context.py`, `[context]` settings and 19 tests. The command selects a saved case by label, revalidates the local corpus and returned source records, removes only agreeing duplicate IDs, preserves whole sections and creates a per-pack source registry. It keeps all validated candidates; semantic relevance filtering has not been evaluated. It stops on excessive size or changed evidence. The default guard is ten sources/12,000 characters, not a model token limit. Expected evaluation answers never enter the pack.

**Verified:** All 177 tests passed. The actual E04 preview contains eight sections and 5,266 formatted characters, with SIM checks labelled S2 and training identification S7. Local checks of E01/E04/E06 preserved IDs and exact text; their sizes were 5,238/5,266/3,285 characters. E06 flags IDV-1001 and ESIM-1001 as referenced without an included passage. Every nonempty pack still says sufficiency is unassessed. Tests and these saved-result checks establish packaging behavior, not answer accuracy or new retrieval performance.

**Cost and preservation:** Preview/checks ran with network connections blocked: zero service calls and no external request charge. Prior retrieval and embedding files passed unchanged-hash checks. Local computing cost and future generation token usage are unmeasured; no current price was newly assumed or altered. Saved `data/processed/context-example.json` separately.

**Next:** Review the pack, then explain answering instructions and source-reference validation before connecting a model. A source label can identify a passage without proving that it supports a particular claim. See [context construction](context-construction.md).

## 2026-10-17 — follow explicit policy references once

**Built:** Optional `--follow-references` retrieval, `policy_lookup.py`, configuration limits (two policies/six extra sections), 12 lookup tests and two additional retrieval CLI tests. Explicit question IDs take precedence; otherwise original semantic passages supply the references. Fetch missing approved sections once, preserve provenance, reject changed/missing records and avoid duplicates or recursion. Original baselines have separate protected output paths.

**Teaching:** Explained semantic search versus opening a named policy, the extra request and limits, and proposed files before implementation. The user suggested giving a fetched identity passage the same score as the referring SIM passage. Clarified that the score measures one question/passage comparison; copying it would invent a measurement for the fetched passage. A reference-fetched passage receives no score and can still contain essential guidance. The user's understanding of this correction has not yet been checked.

**Measured result:** All 158 automated tests passed. An initial full-suite attempt stalled and was interrupted without claiming success; a completed rerun with normal temporary-folder access passed. Three separate real searches/fetches found E01 1/1, E04 3/3 and E06 2/2 expected sections, compared with 1/1, 2/3 and 1/2 originally. First-four IDs/scores and question/model/corpus/date/input matched. Baseline and k=8 report bytes remained unchanged. Saved enhanced results and a comparison report under `data/processed/`.

**Tradeoff and costs:** Final counts were 8, 8 and 5 passages; words rose from 502 to 826 across the questions. This is not a model token count. The run reported 6 RU (3 search + 3 fetch), with 66 local query tokens. No remote writes, external generation or plan changes. Fetches took 0.29–0.34 seconds in this run; this is not a latency benchmark. No dollar bill is inferred.

**Decision and next:** Keep lookup optional and default semantic top_k 4. E01 gained extra text without measured recall benefit. Finding the authored expected sections does not establish sufficient evidence for every claim or customer eligibility. Next teach evidence selection and context construction before generation. See [the step-by-step lesson](policy-lookup.md).

## 2026-10-17 — diagnose missing evidence by increasing top k

**Concept:** A passage may exist in the index but rank below the candidate limit. Increasing the limit can recover it, while also returning more text. A direct fetch by ID tests storage presence separately from semantic ranking.

**Experiment:** Repeated the same three baseline questions at k=8 using a temporary settings copy and the existing retrieval functions. Model digest, corpus hash, exact query input, namespace and policy date matched. First four IDs remained identical. Original settings/baseline were verified unchanged.

**Results:** E01 remained 1/1, E04 remained 2/3 and E06 improved from 1/2 to 2/2 expected sections. E06 appointments ranked sixth. E04 training_id remained outside eight; a separate direct fetch confirmed its stored text/metadata. Its exact lower rank was not measured. This demonstrates a ranking/completeness issue rather than an absent stored identity record.

**Costs and tradeoff:** Three searches reported 3 read units; one diagnostic fetch reported 1. Local query inputs totalled 66 tokens. Across the three questions, returned passage words rose from 502 to 947; these are words, not tokens or a generation bill. Single-run times do not establish a speed change. No paid inference or subscription change.

**Decision and next:** Keep default k=4; a blanket increase did not recover all required evidence. Explain targeted lookup of explicit policy references next, then evaluate against the same questions. Saved `data/processed/retrieval-top-k-8.json` and updated the lesson/evaluation notes. No application-code change, so no additional automated test suite was needed; actual search results and source-presence assertions were checked. The user has not yet independently explained this experiment's outcome.

## 2026-10-17 — first semantic retrieval baseline

**Built:** Added question embeddings to `ollama_embeddings.py`, `retrieve.py`, settings and 17 offline tests. The command checks eligible sources and index/model identity, searches Pinecone and validates returned text/source fields. It uses LangChain Document containers internally and displays evidence, scores, tokens and separate embedding/search timing. No answer is generated.

**Teaching:** Explained the query-to-vector-to-search pipeline and top_k 4 as a candidate limit. The user correctly answered that four passages still need relevance and completeness checks. Retained the 2026-10-15 policy date. Similarity scores are not confidence percentages.

**Results:** All 144 automated tests passed. Real searches found expected sections as E01 1/1, E04 2/3 and E06 1/2. E04 missed IDV training_id; E06 missed SIM appointments. E01 ranked appointments first, score 0.7687. All returned text/source fields matched eligible sources. Passing code tests does not establish complete retrieval.

**Costs:** Queries used 66 local tokens and 3 reported Pinecone read units. No remote writes, paid inference or subscription change. Public terms/metering checked on 2026-10-17; remaining quota/billing unverified. Observed timings are in the lesson/report, not a benchmark.

**Next:** Review the missing evidence and teach one measured improvement before answer generation. No score threshold or completeness detector exists yet. Streamlit still displays the local library. See [retrieval lesson](retrieval.md).

## 2026-10-15 — real Pinecone indexing and role clarification

**What we built:** Installed official Pinecone SDK 10.0.0, added `pinecone_ingest.py`, 13 offline tests and index settings. The preview checks the complete saved corpus against current eligible sources. The live command creates/connects a compatible index, uploads only into an empty owned namespace and compares fetched records. Current SDK named fields preserve the chunk ID, vector, exact text and metadata.

**Actual result:** Authentication succeeded; the account project initially had zero indexes. Created `retail-copilot-week2` in AWS `us-east-1`, using 768 dimensions and cosine similarity. Uploaded 33 records into `telecom-demo-v1`. Namespace count and read-back of all 33 IDs passed, with exact text/source fields and matching vectors within numeric tolerance. The verification fetch reported 4 read units. Saved a dated ignored report and the index host privately in `.env`.

**Tests and limits:** All 127 automated tests passed; the 13 ingestion tests use simulated responses. The real initial upload/read-back is separate acceptance evidence. Repeat-upload avoidance is tested locally, not a second live upload. No semantic search or answer-generation test has run. Changed corpora stop for review; remote stale-version removal is not automatic.

**Teaching:** Explained index, namespace, source retention, record formats and verification versus retrieval quality. The user answered that Pinecone should return a complete final answer. Clarified with a SIM/account-authority example: Pinecone returns relevant evidence; a language model later drafts an answer, and our code renders citations from retrieved metadata. The user then requested a slower, complete explanation of everything since connection. Added that walkthrough to the architecture and indexing guide. Understanding of this distinction is not yet independently confirmed.

**Cost:** Starter is user-reported, with credits pending. Public free allowances were checked, but billing-plan details and remaining quota were not independently verified. No subscription upgrade. Local record-size estimate is 134,885 bytes; JSON request size is 373,184 bytes, not billed storage. Actual write usage and dollar cost remain unreconciled. Paid OpenAI use stays disabled.

**Next:** Teach and test question embedding and semantic retrieval before adding answer generation. See [indexing walkthrough](pinecone-indexing.md).

## 2026-10-15 — complete local embedding corpus

**What we built:** Added `prepare_embeddings.py` and eleven tests, an output setting, and reusable installed-model identification/keep-alive support in the local client. The command rebuilds eligible sections, reuses only exact matching model/input results, refreshes metadata and saves only a complete validated snapshot. Changed inputs re-embed; removed/ineligible sources leave the local snapshot. No remote deletion is implied.

**Actual results:** Generated 32 new embeddings and reused the authority example, producing 33 vectors from 11 policies. All have 768 values. New input usage was 1,745 tokens; corpus usage including the reused input is 1,808, with per-chunk counts 36–70. Saved `data/processed/embedding-corpus.json`. An acceptance rerun reused all 33, processed zero new tokens and kept every record identical, while a guard prohibited new embedding calls. The latest snapshot reflects that rerun.

**Verification:** All 114 tests passed. New tests cover exact-input/model cache matching, metadata refresh, changed passages, source removal, model changes during a run, empty/unsupported selections, malformed caches, output paths and failure preservation. Every real record was separately matched to current source text/metadata, mapped locally to Pinecone format and confirmed in an ignored output file. No retrieval-quality claim follows from these checks.

**Teaching and user progress:** Explained corpus-wide preparation and why stable IDs alone are insufficient for reuse. The user asked where the Pinecone key belongs; guided them to Week2's private `.env`. They replied "saved", and the subsequent presence check reported the Pinecone key present without printing it. Model dimensions/input-format/reuse concepts still need independent explanation by the user.

**Cost and limits:** No external inference or Pinecone calls in this step. Local computing resources were used; pricing rates were unchanged. Failure does not checkpoint partially generated vectors, and local snapshot cleanup does not delete remote records. Next: authenticated Pinecone setup, index creation, upload and source/count verification. See [the corpus lesson](corpus-embeddings.md).

## 2026-10-15 — local Pinecone record mapping and first real Ollama embedding

**User direction:** Asked when actual indexing would happen. Explained that preview-only output cannot be indexed as a real vector. The user confirmed a Pinecone account/key, pending Builder credits, chose local Ollama embeddings, and subsequently confirmed the account is Starter (free). Week2's private presence check reports no configured OpenAI/Pinecone key or index host; no values were exposed.

**What we built:** Added a local `id`/`values`/`metadata` mapper, preserving original text inside metadata for future retrieval. Then selected Ollama `embeddinggemma:300m` under the active embedding settings, retaining the OpenAI settings and preview/token commands as comparison lessons. Added a local HTTP embedding function, one-chunk save command and tests. Downloaded the approximately 622 MB model; the existing qwen3 practice model was unchanged. No new Python dependency or Pinecone SDK was installed.

**Concepts:** The same record components have different field names in Pinecone. Flat metadata cannot contain nested objects or null values, and its size includes text. EmbeddingGemma uses a model-specific document prompt/title. Changing the model changes the output dimension to 768 and changes tokenization; previous 50-token/1,536-dimension OpenAI figures do not describe this local request. The original passage remains unchanged and the exact formatted input/model digest are saved separately. The user has not yet independently explained these new distinctions.

**Actual result:** One local Ollama request embedded `AUTH-1001-v1:delegation:section-v1`. Reported usage was 63 input tokens, vector length 768, duration 5.27 seconds. Saved `data/processed/ollama-embedding-example.json`, ignored by Git. This is a real vector, not a simulated fixture. It passed local mapping checks; no Pinecone index or upload exists. The one-run duration is not a latency benchmark.

**Verification:** All 103 automated tests passed: the previous 85, nine mapping checks and nine Ollama checks. Mapping tests cover all 33 eligible chunks with dummy vectors, source identity, copying, invalid metadata/vectors and size boundaries. Ollama tests cover exact formatted input, disabled truncation, local-only addressing, installed-model checks, response errors and protected output. The real local request was a separate acceptance check. Source/text identity and saved vector shape were also inspected. Retrieval quality and answer quality remain unmeasured; no UI behavior changed.

**Costs and next step:** No billed external inference or Pinecone requests. Local download/computation uses resources; their cost is not measured. Public Starter pricing was checked again, but the actual plan/quota has not been inspected. Next: generate the remaining corpus embeddings, privately configure Pinecone access, review the index settings and account limits, then upload and verify stored records. Do not assume pending Builder credits are active or that local mapping tests prove remote acceptance.

## 2026-10-15 — inspect the preview and link vectors to evidence

**User-observed result:** The user pasted a completed preview showing the authority delegation chunk, 50 input tokens, 1,536 expected output dimensions and a recorded-price estimate of USD 0.00000100. Its final line explicitly reported no embedding API call, vector or result file. This confirms the user ran the preview successfully; it does not demonstrate a real API response or retrieval quality.

**Lesson:** Explained the four linked parts of a future saved result: chunk ID for identity, exact text for evidence, metadata for source tracking and governance, and a vector for similarity comparison. Checked that the existing `embed_one_chunk` result retains these fields. Used the real fictional authority section's source details without inventing vector values. Only text is embedded; metadata stays linked locally. A close match is a candidate, not proof of a complete or eligible answer. Future citations must come from the metadata associated with the retrieved evidence.

**Documentation:** Added a small record walkthrough and future retrieval diagram to `embedding-example.md`. No application behavior, model configuration or storage design changed, so no new design decision was required. No automated tests were rerun for this documentation-only lesson, and no external services were called.

**Understanding check:** Asked whether retaining a vector but discarding the original text would allow reliable quotation of exact policy conditions, the user answered no and said the vector should contain text, metadata and chunk ID to point to exact guidance. This demonstrates recognition that source text and traceability must be retained. Clarified the container terminology: the vector itself is only a list of numbers; our saved record holds the vector, text, metadata and chunk ID together. A vector is not a reliable way to recover the original policy wording. The correction has been explained; the user's independent use of this distinction remains to be confirmed.

**Next:** Prepare the mapping from our local result to a storage record in a separate small lesson. Real embedding generation and Pinecone storage remain pending. This understanding-check update changed documentation only; no application tests or service calls were run.

## 2026-10-15 — prepare and locally test one embedding request

**User direction:** The user asked to proceed and confirmed, "I still don’t have an API key—prepare and test locally." The configuration-presence command also reported the OpenAI key and Pinecone values missing without displaying any credentials. No account or paid service work was attempted.

**What we built:** Installed the official OpenAI Python SDK 3.31.0. Added `embeddings.py` for one checked request and response validation, and `embed_example.py` for a preview-first command. Extracted the existing private environment-file reader so a future enabled live run can use the same Week2-only file and process-environment precedence rules. Added the example selection, endpoint and timeout to settings. Live service use remains disabled in pricing configuration.

**Learning focus:** The authority chunk is 50 input tokens, while the configured embedding output has 1,536 dimensions (numbers). Token count measures input size; dimensions describe the vector's length. Different-length passages use the same vector length under the same configuration. The whole vector supports comparison; individual numbers are not labelled retail concepts. Asked whether the 50-token and 57-token chunks should produce equal-length vectors, the user said they were unsure and requested an explanation. Reinforced that both outputs have 1,536 values because the model configuration fixes the output size; the values represent the text and can differ even when their counts match. Used a fixed set of map coordinates as an analogy for comparing different inputs in a shared representation, while noting that embedding dimensions do not have simple human-readable labels. Understanding remains to be confirmed in the user's own words. This coaching update changes documentation only; no tests or API calls were run.

**What runs now:** The default preview selects an approved, effective source, measures exact `page_content` and displays the expected output shape and estimate. It reads no credential, creates no API client, sends no embedding request and saves no vector file. The actual command printed 50 tokens, 1,536 expected numbers and USD 0.00000100 estimated cost. The project's embedding-example output file does not exist.

**Future live behavior:** An explicit live option, enabled service-use setting, positive estimated allowance and private key are required. A live request sends one passage with zero automatic retries. The response must match the model, input index and dimension, contain finite numeric nonzero content and provide valid usage. Only an accepted response is saved with text, independently copied metadata, usage and dated cost estimates. Existing output prevents another attempt. Timeout, malformed-response or save failures can follow billable processing, so error messages advise reviewing provider usage before resubmission.

**Tests:** All 85 tests passed: the previous 68 plus 15 embedding and two credential-reader checks. The installed SDK processed simulated HTTP responses through a mock transport while socket connections were blocked. Tests covered request fields, source retention, allowances, disabled live calls, malformed responses, usage differences, sanitized API errors, zero retries, protected output and save failures. Fictional test vectors were used only in temporary test folders. These tests do not establish vector meaning, retrieval quality, live API access or actual billing. Streamlit was unchanged and UI checks were not repeated.

**Cost:** Rechecked the public standard rate of USD 0.02 per million input tokens on 2026-10-15. One 50-token request is estimated at USD 0.000001, excluding all other application costs and taxes/conversion. The local allowance is per attempt and estimate-based, not a provider or cumulative account cap. No paid calls or charges occurred. [Official price](https://developers.openai.com/api/docs/models/text-embedding-3-small).

**Next:** Inspect the preview and explain tokens versus dimensions. Once API access is available, review costs and run one authorised real example before extending to the full corpus and Pinecone. See [the request walkthrough](embedding-example.md).

## 2026-10-15 — count embedding input tokens and estimate one corpus pass

**What we built:** Added `token_report.py` and 16 tests; installed and locked `tiktoken` 0.14.0 and declared PyYAML as a direct dependency for reading our pricing file. The command rebuilds eligible LangChain section chunks from current sources and settings, counts their exact `page_content`, checks the configured per-input limit, and prints a dated cost estimate. It does not read or overwrite the saved chunk export.

**Learning focus:** Tokens are model-specific pieces of text, not necessarily words. Token IDs identify pieces in the tokenizer vocabulary; embeddings are separate numerical vectors used to compare related text. The familiar authority passage has 43 words and 50 tokens. Asked whether 43 words necessarily means 43 tokens, the user correctly explained that word count cannot reliably predict model usage. This demonstrates recognition that there is no fixed words-to-tokens conversion. Reinforced the reason: a word can split into several tokens, and punctuation can contribute tokens too. The distinction between token IDs and embedding vectors still needs the user's explanation. This coaching update changed documentation only; no tests were rerun.

**Measured result:** Eleven eligible policies produce 33 chunks with 1,404 tokens; individual inputs contain 26–57 tokens. All fit the configured 8,192-token maximum. At the reverified standard rate of USD 0.02 per million input tokens, embedding these body-text inputs once is estimated at USD 0.00002808. No embedding request was made and no vectors or API charges were produced. Source metadata and added headings are not included in the proposed input; changing the input requires recounting.

**Evidence:** All 68 automated tests passed, comprising the existing 52 plus 16 token-report checks. Tests cover real corpus/source consistency, the archived-policy exclusion, empty and Unicode inputs, special-looking text, unchanged inputs, IDs, exact/over-limit boundaries, configuration mismatches and cost precision. An 8,192-token input passes and 8,193 is flagged without truncation. The command also passed with network connections blocked after the vocabulary was cached. Streamlit was unchanged and its UI checks were not repeated.

**Cost and dependencies:** Package installation and first tokenizer use download software/vocabulary; the policy text stays local. Cached token counting has no API usage charge. The estimator reads a model-matched standard USD rate, source and checked date from pricing YAML; an unknown or invalid price stops the report. The estimate excludes question embeddings, resubmissions, generation, Pinecone, tax and conversion. Future API usage must be checked against returned usage and provider billing, with unchanged embeddings reused when possible.

**Limitations and next step:** These checks establish local input size and estimated usage, not retrieval quality or live API acceptance. The configured date still controls eligibility. Request grouping, request-wide limits, account access and spending controls remain pending. The next lesson should inspect the report, then establish account readiness before a small actual embedding request. The user has previously reported no OpenAI API key; access has not been reverified. See [the walkthrough](embedding-preparation.md) for the command and [official input requirements](https://developers.openai.com/api/reference/resources/embeddings/methods/create).

## 2026-10-15 — use the LangChain Document container

**User request:** Use LangChain's document container instead of our custom Python containers. The user clarified that LangChain means the library, not the separate practice folder. This explicit request supersedes the earlier preference against adding that framework for this container use.

**Concept:** A container keeps related information together. LangChain's `Document` has `page_content` for text, `metadata` for descriptive/source fields and `id` for identity. Metadata remains a Python dictionary inside this standard container. It does not itself load, approve, split, embed or retrieve anything. [Official Document reference](https://reference.langchain.com/python/langchain-core/documents/base/Document), checked 2026-10-15.

**What changed:** Installed and locked `langchain-core` 1.6.10; replaced our custom policy, section and chunk classes with policy/chunk `Document` objects and local section metadata. Updated the loader, chunker, exporter, Streamlit viewer and tests. Our own validation, eligibility and splitting functions remain visible. Whole-section IDs live in `Document.id`; saving maps this to `chunk_id` and `page_content` to `text` in the existing export.

**Source tracking:** Full policies retain their named sections locally. Each chunk receives an independent copy of source details plus its own section information, excluding the parent's full section collection. Dates use YYYY-MM-DD strings and are converted for comparisons. Copies prevent one chunk's metadata changes from affecting its siblings or source; the container still permits edits, so processing should treat validated evidence as read-only.

**Verification:** All 52 automated tests passed, including actual LangChain object types, a JSON round trip, metadata independence and existing eligibility, text-preservation and stable-ID checks. The real preparation command saved 33 chunks from 11 eligible policies, excluding SIM-1024-v1. Its complete parsed JSON matched the pre-migration snapshot: same text, IDs and metadata. Body text remains 1,169 words, with section sizes of 21–46 words. Three viewer scenarios passed assertions: default library/source details, no eligible evidence and overdue reviews. Windows reported a temporary-folder cleanup permission error at process exit; moving test temporary files into the workspace did not remove that cleanup issue. A request for broader permissions timed out in automatic approval review. These results establish local behavior, not retrieval or answer quality.

**Cost and scope:** Package installation required a download. Constructing these containers makes no service requests and incurred no API usage charge. No hosted tracing or new provider integration was configured. Source policies, embedding selection and export format remain unchanged. The separate practice project was not changed.

**Next:** Walk through `page_content`, `metadata` and `id`, then resume local token counting and model-limit checks before any embedding calls. The user's distinction between library and folder is confirmed; understanding of the new fields still needs their explanation.

## 2026-10-15 — token concept and embedding model selection

**User question:** "ok lets choose the embedding model...so does the embedding starts from here". Explained that model selection begins the embedding stage, while actual embedding happens when text is processed by that model and numerical vectors are returned. Selecting a name in settings does not generate vectors.

**Concepts:** A token is a piece of input text; it may represent a word, part of a word or punctuation. Our 43-word authority passage does not necessarily contain 43 tokens. A tokenizer applies the model's text-splitting rules. An embedding is a vector, a list of numbers useful for comparing related text; it is not the final written answer. A dimension is one number in that list. Understanding of these concepts still needs a user explanation, not only acknowledgement.

**Selection:** Recorded `text-embedding-3-small`, its default 1,536 dimensions, `cl100k_base` encoding and documented 8,192-token input limit in settings. This is an initial baseline for the small English corpus. The limit is not a target chunk size and is not enforced by the current preparation command. Exact token counts and retrieval performance are still unmeasured. [Official embedding guide](https://developers.openai.com/api/docs/guides/embeddings), [API input limit](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).

**Cost:** Official model pages were fetched on 2026-10-15: small is USD 0.02 per million input tokens; large is USD 0.13. Chose the lower-cost baseline and retained the larger option for a later evaluation-led comparison. The rate and selection status are recorded in `config/pricing.yaml`; billing is input tokens / 1,000,000 x the verified rate. Public prices do not establish account access or credit eligibility. Future passage/query requests incur usage; selecting the model does not. [Small model](https://developers.openai.com/api/docs/models/text-embedding-3-small), [large model](https://developers.openai.com/api/docs/models/text-embedding-3-large).

**Scope:** Configuration and documentation changed only. No tokenizer or API SDK was installed, no credentials were read, no content was sent for embeddings, and no vectors or paid service charges were produced. The answer-generation model remains unset. The reported lack of an OpenAI key remains relevant for later API calls; local preparation can continue.

**Validation:** Loaded the updated TOML through the existing settings reader and checked the selected model, dimension, encoding and documented limit. All 11 existing chunking comparison tests passed, and all 23 local documentation link targets existed. No new tests were added for this configuration-only change; the broader suite's 50-test result remains the earlier chunk-preparation run. These checks do not verify model access or embedding quality.

**Next:** Implement and explain local token counting and input-size checks, then estimate costs using measured tokens. Review account access and spending before the first real embedding call. Questions and documents must use the same embedding model/dimension when retrieval is implemented.

## 2026-10-15 — prepare and save the eligible section chunks

**What we built:** Added `prepare_chunks.py`, `[chunk_preparation]` settings and 12 preparation tests. The command reuses the existing loader, eligibility selector and whole-section chunker, then saves `data/processed/chunks.json`. Generated output is ignored by Git. No new framework, dependency, model integration or interface change was introduced.

**Learning focus:** The user confirmed the comparison runs in their terminal and agreed to proceed after the remaining essentials were explained. We introduced the `for` loop as visiting each document/section, distinguished words from model tokens, and explained why preserving a complete section does not automatically supply the other policies it references. Keep the next lesson focused on a single output record.

**Identity and metadata:** Each saved record contains text, a word count, source/governance metadata and an ID such as `SIM-1024-v2:checks:section-v1`. The three components identify a policy version, section and chunking method. An unchanged rerun uses the same ID; a new policy version uses a different ID. IDs identify passages, not a fingerprint proving unchanged contents. Editing text under the same identifiers changes the saved text but retains the ID; policy revisions should be versioned and future cloud updates must account for changed/removed records.

**Architecture:** Local policy files -> validation -> approval/date selection -> complete sections -> IDs and metadata -> saved JSON snapshot. This prepares evidence for a later embedding stage; it does not embed, retrieve or generate answers. The local export permits nullable dates and is not a Pinecone upload payload.

**Measured result:** The actual command loaded 12 policies, selected 11 eligible on 2026-10-15, excluded `SIM-1024-v1` and saved 33 chunks. Body text totals 1,169 words, with chunk sizes of 21–46 words. All 50 automated tests passed: the existing 38 and 12 new checks for full source preservation, stable/unique IDs, eligibility, conflicting versions, long text, repeated saves, removed sections and save/configuration failures. Streamlit checks were not rerun because the UI was unchanged.

**Reruns and errors:** Records are sorted; unchanged inputs/settings produce identical output bytes. Successful runs replace the snapshot rather than append records. A temporary file is completed before replacing the previous export. Errors stop the command and warn that an earlier export must not be treated as a successful current result. The snapshot records the configured demo date; later ingestion/retrieval will need fresh eligibility checks.

**Cost and limits:** No API calls or paid service charges. No token counts, model limits, retrieval scores or latency have been measured. Long sections remain intact for local inspection; add the selected model's size check before service calls. Provider metadata serialization and cloud update/deletion handling are still pending.

**Understanding check:** The user correctly predicted that rerunning the same section-aware, fixed-size or overlapping method produces the same results when its inputs and settings are unchanged. They suggested results change only with the strategy. Clarified that source text, versions, eligibility date and settings such as size/overlap can also change the output. For our saved section records, repeatable IDs let us recognise the same passage across runs. An ID identifies document version, section and method; editing text in place can change its contents without changing that ID, so policy revisions should receive a new version. The comparison's fixed-size variants do not yet have persistent ID schemes. The answer demonstrates repeatability understanding; the purpose and limits of IDs were explained, not independently demonstrated yet.

**Saved-record walkthrough:** Inspected the actual `AUTH-1001-v1:delegation:section-v1` record and explained text, source metadata, ID and its 43-word count. Asked whether this passage could answer which identity documents a delegate must provide. The user replied, "chunk along with metadata as it contains source tracking as well". This recognises metadata's tracing role. Clarified that the authority passage refers to IDV-1001 but does not list the required identity documents; source tracking cannot supply missing policy content. A future retriever must obtain the relevant approved identity-policy passage and check that it answers the question. If sufficient evidence is unavailable, the copilot must state the gap rather than guess. This cross-document evidence distinction still needs confirmation. No code was changed or tests rerun for this coaching update.

**Next:** Reinforce the difference between tracing a source and having enough evidence, then explain model tokens and limits before adding embedding work. The full ingestion phase remains incomplete.

## 2026-10-15 — reusable local chunking comparison

**What we built:** Added `src/retail_copilot/chunking.py`, a `[chunking_experiment]` configuration section and 11 focused tests. The module can be run again from the terminal to display the three variants for an eligible document section. It defaults to the familiar 43-word authority example with 20-word windows and five-word overlap. No dependency, SDK, source-policy or interface change was needed.

**Concept:** A reusable function turns the same procedure into named instructions that can be called with different input. `step = words_per_chunk - overlap_words` gives the next starting position: 20 minus 5 equals 15. Stop once the last source word has appeared to avoid an overlap-only trailing passage.

**Inputs and outputs:** The command reads the configured demo date, selects approved evidence and obtains the chosen document/section. Functions return `Chunk` objects containing text, inclusive one-based word positions, and the original document/section references. This retains provenance, meaning the ability to trace a passage to its source. Fixed-size splitting restarts at every section boundary; it does not combine sections. The output is an inspection format, not an upload record.

**Settings and boundaries:** Sizes remain clearly labelled teaching values. Positive whole-number sizes and non-negative overlap smaller than the size are required. Fixed windows normalise whitespace but preserve word order, case and punctuation. Complete-section chunks preserve loaded text, including internal line breaks, and have no size cap yet. Future ingestion must check actual model limits and call eligibility selection before splitting.

**Results:** On 2026-10-15, all 38 automated tests passed, comprising 11 new chunking tests and the existing 27 tests. The command reproduced 3/43, 3/53 and 1/43 passage/combined-word counts for the authority example. Tests covered short/exact/long boundaries, overlap, no duplicated trailing-only passage, empty input, invalid settings, source references, word preservation across all eligible sections and command rejection of the archived document. Streamlit checks were not rerun because its implementation was unchanged.

**Wider comparison:** Eleven eligible documents contain 33 sections and 1,169 source words. Fixed 20-word windows without overlap produced 74 passages; five-word overlap produced 86 passages and 1,434 combined words (265 repeats). Whole sections produced 33 passages containing 1,169 words; sizes were 21–46 words. These are body-text measurements, excluding headings or future prompt wrappers.

**Decision and limitations:** Use one existing section per chunk as a provisional baseline for this short structured library: it preserves the inspected authority conditions and avoids one-word remainder passages. This does not prove better retrieval or answer quality. Persistent chunk IDs, upload serialization, longer-section policy and model-aware limits are still pending. No live model evaluation or latency measurement was performed.

**Cost:** No model or Pinecone calls and no external API charges. Word duplication is observable, but it is not a billable-token estimate. Pricing configuration remains unchanged.

**Next lesson:** Inspect the fixed-size function a few lines at a time and trace its output metadata. Keep that explanation separate from the next implementation step.

## 2026-10-15 — paced walkthrough and first chunking comparison

**Learning pace:** The user asked to slow down after the Phase 1 build. We walked through reading JSON, validation and eligibility separately before starting chunking. Keep future changes small enough to inspect and explain before progressing.

**Understanding observed:** The user correctly distinguished policy guidance from metadata describing the document. During the chunking lesson, the user identified that a split can separate a rule from its conditions, and that overlap can still be too small to restore the whole condition. They connected larger overlap to latency; we clarified that duplicated text can add work, but a latency increase must be measured rather than assumed.

**What we did:** Ran a temporary local comparison on the approved AUTH-1001-v1 `delegation` section. Compared 20-word passages without overlap, 20-word passages with five-word overlap, and the complete section. Saved the actual passages and findings in [the chunking experiment](chunking-experiment.md). No reusable chunker or application setting was added in this lesson.

**Measured text results:** The original section has 43 words and its first rule sentence has 28. No overlap produced three passages containing 43 combined words. Five-word overlap produced three passages containing 53 combined words, including 10 repeats. Keeping the whole section produced one 43-word passage. Only the complete-section variant contained the entire original first rule sentence in one passage.

**Checks and limits:** Source-span and complete word-coverage assertions passed for all three variants. No words were lost across a variant's full set of passages, although individual fixed-size passages contained incomplete statements. This distinction is separate from whether a later search will retrieve all needed passages. No retrieval or answer evaluation, token billing calculation or latency measurement was performed. The prior 27-test suite was not rerun because application code was unchanged.

**Cost and architecture:** No API requests or external service charges. The comparison previews the chunking stage using one eligible section. Cleaning/chunking application code, embeddings, Pinecone writes and retrieval remain pending. Twenty and five are explicit teaching values, not chosen production settings.

**Additional user context:** The user reports LlamaIndex credits available for possible later use. Service coverage and credit terms have not been checked. Direct Python remains the current approach; no LlamaIndex integration has been selected.

**Next:** Explain and implement a small local chunking function with source metadata, then inspect its output across the approved library before deciding on a baseline strategy.

## 2026-10-15 — Phase 1: fictional telecom evidence

**What we built:** Twelve separate JSON documents covering the ten requested telecom topics, evidence-handling guidance and an archived SIM version. Replaced the earlier general-retail source file, expanded the loader and viewer, documented metadata, and authored 15 initial evaluation cases with unmeasured result fields. The active demo date is 2026-10-15; eleven documents are approved and effective and one archive is excluded.

**Concepts and architecture:** A corpus is a document collection; metadata describes each source; a schema states its required fields. A policy ID identifies a policy across revisions, while a document ID identifies one version. Named sections prepare us for later chunking and citations. This phase implements loading and eligibility selection, not vector retrieval or answer generation.

**Understanding check:** Asked which evidence to use when an archive matches a SIM question closely but a current approved policy differs. The user answered, "use the current and approved policy". That selection is correct. We explained that eligibility takes precedence over wording similarity; the reply did not independently explain the reason, so deeper understanding remains a later checkpoint.

**Concrete example:** SIM-1024-v1 required an appointment; current SIM-1024-v2 makes appointments optional. The archive remains visible only as an excluded source. Identity guidance and account authority are separate documents, making multi-source questions possible. Missing authority evidence remains uncertainty, not an invented permission or prohibition.

**Governance decisions:** Require fictional declarations, source metadata, meaningful sections and consistent identifiers. Preserve actual filenames from the filesystem. Use inclusive effective dates; reject overlapping eligible versions. Treat a review date as a reminder rather than expiry. The future namespace `telecom-demo-v1` describes a corpus boundary; no cloud resource has been created.

**Errors translated:** The first validation caught evaluation references using policy IDs where version-specific document IDs were required. Corrected those references; did not weaken the test. The viewer's first label assertion failed because PowerShell changed a non-ASCII separator in piped test code. Inspecting the actual label confirmed the app was correct; an explicit Unicode escape fixed the test. The usual Streamlit bare-mode warning appeared without an application exception.

**Verified results:** All 27 automated tests passed after the reference correction: 16 document tests, 3 evaluation-specification tests and 8 readiness tests. The validator loaded 12 documents and selected 11. Three Streamlit scenarios passed: default counts and source/section labels; no eligible evidence on 2026-09-01; and 11 overdue-review reminders on 2027-01-02 while those sources remain effective. These checks establish local behaviour, not search or model quality.

**Content review and limits:** All twelve sources were deliberately authored as fictional guidance with invented team names, allowances and training identification. No real customer records or confidential source documents were imported. Schema checks confirm declarations, not the absence of personal information in arbitrary future input. No code detects semantic contradictions across different policy IDs yet. Evaluation cases describe expected behaviour; all live result fields remain null. The partial-authority example uses deliberately restricted context and must be evaluated separately from normal retrieval.

**Cost:** No new dependency, API request, index, embedding or generated answer. No external API charges. Future embedding costs cannot be inferred from document count and remain unmeasured.

**Next:** Compare fixed-size and section-aware chunks locally, inspect rule/exception boundaries and document the choice before embedding. No API key is needed for that experiment.

## 2026-10-15 — local setup without API credentials

**User context:** No OpenAI API key is available; Pinecone credits are expected soon. Neither account access nor credit conditions have been verified. No learning spend limit has been agreed.

**What we built:** A local `retail-check` command, blank `.env.example` and ignored `.env`, planned OpenAI provider settings with models unset, and a separate Week2 Git repository. The new dependency, python-dotenv 1.2.4, is locked in `uv.lock`. The existing policy viewer remains runnable. No commit or remote publication was made.

**Concepts:** An environment variable supplies configuration to a running program. A `.env` file keeps local settings outside source code. The checker reports only whether values exist, not whether they are valid. A repository is a boundary for Git's version history; Week2's new boundary avoids operating on the surrounding home-directory repository.

**Inputs and outputs:** Week2's `.env` and process environment variables become three presence flags. Environment variables take priority, even if explicitly empty. Parent `.env` files are not searched, and the process environment is not changed. The tool does not return credential values.

**Understanding check:** The user answered the missing account-authority example with "if no account authority exists, dont allow for sim replacement". This recognised the evidence gap but inferred a prohibition. We distinguished missing retrieved evidence from a policy saying that someone lacks authority: the copilot should state that permission cannot be confirmed, not approve or deny the transaction. Revisit with a different example; do not assume this explanation proves understanding.

**Evaluation implication:** Add a partial-evidence case during telecom corpus/evaluation design: SIM guidance is retrieved, account-authority evidence is absent. Expected behaviour is explicit uncertainty about authority, with neither an invented permission nor an invented prohibition.

**Verification:** On 2026-10-15, all 16 automated tests passed: eight document tests and eight configuration tests. These cover missing/blank values, quoted values and Windows UTF-8 files, environment precedence, project isolation, unchanged environment, redacted output and a safe read-error message. The live local report showed all three values missing. The policy validator loaded four documents and selected three approved sources. Streamlit checks passed for the default 3-approved/1-excluded view and the empty-evidence date. The expected bare-mode Streamlit warning appeared without an application exception.

**Cost and limitations:** No OpenAI or Pinecone requests, cloud resources or external API charges. Package installation downloaded a public dependency. Presence does not validate keys, index access, credits or billing; this report is not a spending-control mechanism. Tests used fictional credential values. Missing keys are expected and do not block document preparation.

**Next:** Design telecom source metadata and fictional documents, followed by local chunking experiments. Service calls remain pending account access, model/index choices and cost review.

## 2026-10-15 — orientation to the updated telecom brief

**What we established:** The target is a fictional telecommunications knowledge assistant using direct Python components, Pinecone and OpenAI. The existing general-retail viewer is a runnable foundation; it does not yet implement that complete target.

**Concept:** Retrieval finds candidate evidence; generation writes an answer from selected evidence. A close text match does not prove that every part of the customer's question is answered.

**Example:** A SIM-replacement policy may not establish whether a secondary account contact is authorised. Missing authority evidence must remain a gap rather than become an invented permission.

**Observed checks:** Python 3.12.15, uv 0.12.23 and Git 2.56.0 are installed. Week2 has a separate environment and lock file, no local `.env`, and no local Git repository. These checks do not determine whether the user has provider accounts or credentials elsewhere. No key values were read.

**Documentation changes:** Added the orientation/checklist, aligned README and planned architecture, recorded scope changes and model candidates, and refreshed dated pricing and cost explanations.

**Validation boundary:** Reviewed documentation references and candidate rates against official sources. Application code did not change; the previous eight-test result remains dated 2026-10-14 rather than being reported as a new run. Cloud retrieval and generated answers remain untested.

**Cost impact:** No paid API calls or account changes. Account readiness, model access and a spending limit must be established before service-backed work.

**Understanding check:** If retrieved SIM guidance omits account authority, what should the assistant avoid concluding? The user's subsequent response and coaching clarification are recorded in the local setup entry above.

**Next:** Explain and complete local Phase 0 setup, then design telecom documents and their metadata before ingestion.

## 2026-10-14 — Milestone 1: the evidence library

**Concept:** A RAG answer is only as reliable as the evidence supplied to the model. We start with approved source documents before adding search or generation.

**Retail example:** The archived returns rule says 14 days; the approved current version says 30 days. Excluding the archive prevents a later retriever from treating both as current guidance.

**Inputs and outputs:** Four fictional policy records become three approved documents for the fixed demo date, 2026-10-14. Source titles, IDs and versions are retained for later citations.

**Changes:** Added project configuration, a policy loader and date/approval checks, a local Streamlit library viewer, document tests, an eight-category evaluation set and project documentation.

**Costs:** This milestone uses local files and local Python execution. No Pinecone resource is created and no model inference is requested.

**Verification:** All 8 document tests passed on 2026-10-14. The command-line validator loaded 4 documents, selected 3 approved sources for the demo date and excluded 1 archive. Streamlit's application test runner confirmed both the default 3-approved/1-excluded display and the insufficient-evidence message for 2026-09-01. All 8 evaluation examples refer to valid corpus IDs. The Python environment was installed independently with Streamlit 1.65.0 and locked in `uv.lock`.

**Error translated:** The restricted execution session could not access Python-created temporary test directories. Moving temporary files into the project did not resolve that session restriction. Running the same validation with normal local permissions succeeded; no application change was needed. The Streamlit test runner emitted its expected bare-mode context warning, with no application exception.

**Not tested yet:** Pinecone access, embeddings, retrieval quality, generated answers, citation grounding, latency and live service costs. No model or Pinecone calls were made. These remain later milestones.

**Understanding check:** Why should the archived 14-day policy be excluded even if its text closely matches a customer's question?

**Next lesson:** Passage boundaries and embeddings, then Pinecone account setup and retrieval.

## 2026-10-19 - Final demo verification

The final real chat rehearsal revealed an important language distinction: "Can I book?" asks about the user's options; "Can you book?" asks the assistant to perform an action. The application now handles the narrow clear self-service case without falsely asserting a complete answer. A fresh follow-up returned optional-booking guidance, and thanks/history/rerun/New chat checks passed. The original failed attempt remains saved. All 398 offline tests passed in 15.914 seconds. Fourteen selected normal scenarios and the controlled missing-evidence case met Codex-reviewed demo minimums; this is not independent human review or production accuracy. Exact passages preserve conditions but can include unnecessary background and do not certify relevance. Browser rendering remains unverified.
