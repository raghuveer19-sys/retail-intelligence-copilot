# Chat interface design

Updated on 2026-10-18. The user approved the central chat layout, requested graphical polish, removed source expansion, and authorized implementation. **The natural chat is implemented in `app.py`, and the user has now accepted the current UI: "UI part is fine."** The next focus is evaluating grounded answers to knowledge scenarios. User acceptance does not establish browser accessibility or model correctness; the verification boundaries below still apply.

## Current experience

The welcome screen offers SIM replacement, account authority and roaming starters. The conversation uses native Streamlit chat messages, a question input and New chat, with teal styling, readable spacing and Material icons. The input supports follow-ups. The header caption is "Your policy companion", and "Policy guidance" is a noninteractive gray badge. At the user's explicit request, the customer-details privacy reminder is removed from the interface. This is a display change; data handling and backend behavior are unchanged. The user's earlier instruction also removes fictional/demo labels from the chat's surrounding interface; the corpus remains synthetic and does not become real commercial policy. The badge uses native `st.badge`; see [the official reference](https://docs.streamlit.io/develop/api-reference/text/st.badge), checked on 2026-10-18.

There are no inline S1/source buttons, source expansions, answer diagnostics, confidence percentages or policy-library toggle in the chat. This follows the latest user instruction: "I dont want source expansion functionallity on the chat interface, but just a natural chat." It supersedes the earlier request for expandable supporting policies. Plain-language uncertainty, clarification and action limitations remain part of the answer when applicable.

The original library viewer is preserved separately as `library_app.py`. Retrieved passages, source metadata, citations and measured usage still exist behind the scenes in the current turn's session record. Existing development commands and saved evaluation reports remain available for learning and inspection outside chat. Hiding evidence controls does not remove source-reference validation or make an answer more reliable.

User and model messages use native `st.text` inside `st.chat_message`, so text that resembles HTML or Markdown is displayed as text rather than creating links or images. Only the project's own stylesheet is loaded through `st.html`; generated answers are not passed to it. The implementation uses the installed Streamlit 1.65.0 and adds no dependency. Official references checked on 2026-10-18: [chat elements](https://docs.streamlit.io/develop/api-reference/chat), [st.html](https://docs.streamlit.io/develop/api-reference/text/st.html) and [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

### Focused presentation correction

Installed Streamlit 1.65.0 gives the child `span` inside `st.text` its own text colour. The CSS now targets that child directly so user messages use white text on the dark teal bubble. It also sets dark typed text on a white input background, with an explicit visible placeholder and caret. For that earlier contrast/alias correction, all 58 focused offline checks passed (12 interface, 22 pipeline, 6 plan-name and 18 conversation checks), and a network-blocked consistency check validated all 33 saved records. The restarted local server returned HTTP 200 from its health endpoint. These are historical results; the refinement below has its own focused checks. The browser inventory is empty, so rendering remains unverified.

Plan names have a configurable display mapping in `[plan_aliases]`: **Practice Basic → Connect Essential** (10 GB domestic data per monthly cycle) and **Practice Plus → Connect Plus** (30 GB). Questions and recent user context are mapped back to the original policy names before resolution and retrieval. Final chat text receives the display names only after the structured draft is validated. Canonical policy text, drafts, citation metadata and synthetic-data flags remain unchanged. These aliases do not create real offers or add prices; the existing source defines no monthly prices. This presentation change requires no source edits, re-embedding, Pinecone writes or model change.

### Responsive layout and clear failures

At widths of 640 pixels or less, the starter row stacks its complete columns at full width. Each question caption stays beneath its own button. Long messages use explicit `wrap=True` in native text rendering, with `pre-wrap` and `overflow-wrap: anywhere` on the text's child span so paragraphs and long words can wrap without switching to HTML or Markdown.

Public service/setup failures ask the colleague to try again or contact copilot support; they do not expose API names, credentials, file paths or raw exceptions. Insufficient or unverifiable evidence is distinguished from a service failure and refers the user to the policy owner or support channel. Clarification and unsupported-action responses remain conversational, with no source panels or policy-reference controls added.

All **41 focused offline checks passed: 15 interface and 26 pipeline checks**. AppTest verified the complete long reply, including its ending and an unbroken identifier, plus the enabled wrap flag. Coverage also includes clarification, unsupported-action display, setup/service failure and reset behavior. These tests simulate services and cannot establish viewport rendering, screen-reader behavior or real model correctness. No live services were called for this refinement.

## How a question travels

```text
Submitted question + bounded recent user questions
    -> complete acknowledgement? Return a brief local reply
    -> clear enough? If not, ask for clarification
    -> when needed, propose and check a standalone question locally
    -> create a question embedding and retrieve fresh approved evidence
    -> follow explicit policy references within the existing bounds
    -> build whole-section context and generate a structured local answer
    -> check source IDs and retain metadata citations privately
    -> display natural answer text in the chat
```

`conversation.py` handles reference resolution: identifying what a word such as "it" or "one" refers to. It does not answer policy questions. With no usable recent context, "Can I replace it?" asks what the user wants to replace and what happened, before any service call. Clear independent questions avoid the extra model request. Some follow-ups use the local answering model to propose a standalone question, which must pass format, vocabulary and topic checks. Invalid output or a resolver failure leads to clarification, not a guessed retrieval request.

Complete social acknowledgements such as "OK thanks" receive a short local reply, such as "You're welcome!", with status `acknowledgement`. They bypass resolution, corpus/credential loading, models and Pinecone. A message that also asks a substantive question follows the normal route; standalone yes/no also remains on that route because it may answer a pending clarification. Acknowledgements remain visible in the conversation but do not become policy-reference context.

These are conservative English rules for a fictional demonstration. They can ask an unnecessary clarification, miss an ambiguous phrasing, or fail to resolve a natural follow-up. The checks do not prove that a rewrite preserves the user's meaning. Real follow-up quality still needs evaluation; this implementation does not erase the original answer-quality failures. See [answer evaluation](answer-evaluation.md).

## Bounded memory and reset

Memory is reference context, not approved policy evidence. Configuration in `[conversation]` sets:

| Setting | Current limit | Meaning |
| --- | --- | --- |
| `max_history_turns` | 3 | Latest raw exchanges considered before acknowledgements are skipped and failure boundaries are applied |
| `max_question_characters` | 1,000 | Maximum new-question length |
| `max_history_characters` | 4,000 | Combined previous-question and resolved-question text; retain complete turns only |
| `max_display_turns` | 30 | Maximum exchanges retained in this session and displayed in chat |

The app and pipeline select the latest three raw turns, then skip acknowledgements. Skipping does not extend the window to retrieve an older question. A failed turn is a boundary: only later successful or clarification turns are considered, so an older topic is not revived across an error. The resolver receives only user questions and their previous resolved questions; assistant answers, policy passages and diagnostics are not supplied as conversation evidence. An explicit independent topic can therefore start fresh retrieval without copying an earlier answer. A reference with competing topics asks for clarification.

All chat turns and their private evidence records remain in Streamlit session memory. They are not written to chat logs or shared through a global conversation cache. There is no cross-session memory. New chat clears both the visible conversation and its private records. Older visible exchanges do not imply that every one of them is sent to the model.

The server uses polling for file changes and `runOnSave = true` so routine edits can rerun the app without a process restart. Automatic source reload is a local development convenience and can interrupt a reply that is still running. `disconnectedSessionTTL = 900` allows a disconnected session to remain eligible for reconnection for 15 minutes within the same server process. These settings were verified at runtime, and the restarted server's health endpoint returned HTTP 200. This is not durable chat storage: a browser refresh/new session or server restart can still lose conversation state. See [Streamlit Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state), checked on 2026-10-18.

The user's report that "OK thanks" returned the whole chat to the welcome screen was not reproduced in the baseline AppTest: both exchanges and all four messages remained visible. The confirmed defect was an unnecessary model-resolution request and clarification for that acknowledgement. The fix has **70 passing offline checks: 17 interface, 32 pipeline and 21 conversation checks**. The interface test now exercises the actual acknowledgement pipeline with networking blocked, retains the earlier answer and "You're welcome!", and verifies that a subsequent follow-up uses the prior question. These tests do not establish the cause of the reported whole-history loss or prove that it is fixed. Browser rendering remains unverified; no browser surface is available.

## Implementation files

- `app.py`: welcome screen, chat messages/input, starters, session state, safe failures and New chat.
- `assets/chat.css` and `.streamlit/config.toml`: presentation styling and local server/theme configuration.
- `src/retail_copilot/conversation.py` and `prompts/conversation.md`: bounded user-question context, clarification and conservative local rewriting.
- `src/retail_copilot/pipeline.py`: one fresh retrieval/context/generation turn, retaining evidence and citation associations privately.
- `src/retail_copilot/plan_names.py`: configured presentation names mapped to canonical policy names for questions, and back for displayed answer text.
- `config/settings.toml`: conversation limits outside application logic.
- `library_app.py`: preserved local document viewer, run separately from chat.
- `tests/test_chat_app.py`, `tests/test_pipeline.py` and `tests/test_conversation.py`: interface state, pipeline boundaries and conversation behavior using simulated services.

Only submission enters the service pipeline. An ordinary Streamlit rerun reuses the stored turn result, and New chat clears it. Neither triggers retrieval or generation. Failed requests receive a safe current error message; earlier answers are not relabelled as the failed request's result. No automatic retry is configured. Ordinary chat questions are not automatically turned into evaluation files.

## Run the interfaces

From the Week2 project folder, this command starts the natural chat's local server:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Opening the welcome screen makes no model or Pinecone request. For a real answer, Ollama must be running with the configured models and the project's Pinecone connection must be available. A submitted clear question can consume Pinecone read units and local inference time; a follow-up may also use local resolution. Local hardware/electricity cost is unknown, not zero. See [cost model](cost-model.md).

Stop the server with Ctrl+C. To inspect the original local library instead, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run library_app.py
```

This separate viewer reads local policy files and makes no model or Pinecone calls.

## Verification and remaining review

The final full automated suite passed **281 tests** after all code changes, including **12 Streamlit AppTest UI checks, 17 pipeline checks and 18 conversation checks**, including assertions for the strengthened failed-turn boundary. The chat checks cover one request per submission, no repeat calls on rerun, starters, bounded sanitized history, clarification, safe failures, New chat, plain-text rendering and the display limit. These checks use simulated service responses and do not establish actual model answer quality.

The real `run_chat_turn("Can I replace it?", [], settings)` path was also exercised with network connections blocked. It returned `needs_clarification`, no retrieval question, and "What would you like to replace, and what has happened to it?" This confirms that particular contextless question is clarified before service calls. It is not a broad ambiguity benchmark or evidence that all follow-ups resolve correctly.

The local Streamlit server at `127.0.0.1:8501` returned HTTP 200 for its page and health endpoint. That establishes server availability, not successful browser rendering. Two real pipeline requests also completed:

| Input | Observed behavior | End-to-end time |
| --- | --- | --- |
| Appointment question for a physical SIM replacement | Returned that no appointment is required for this fictional consumer service; one metadata citation retained privately | 94.1 seconds |
| "Can I book one anyway?" with the prior user question | Resolved to "Can I book an appointment for a physical SIM replacement anyway?" and returned that a booking is optional to help plan a visit; one metadata citation retained privately | 137.5 seconds |

Both answers were checked against the actual `SIM-1024-v2` appointments section and matched its guidance. These two pipeline examples do not establish broad answer/follow-up quality, browser interaction or a general latency benchmark. The live check did not print complete token/read-unit totals, so none are inferred here; the application retains reported per-turn metrics privately when available.

AppTest inspects the Streamlit element/state model without rendering a real browser. Browser appearance, narrow-screen layout, keyboard behavior and screen-reader behavior remain separate checks; no browser surface was available. Earlier static checks and HTTP responses for the scripted design preview must not be counted as browser verification of this app.

The user has accepted the current interface. The next focus is knowledge-scenario evaluation: review each actual answer against its retrieved evidence for claim support, complete conditions and appropriate response behavior. The original saved baseline remains **6 passes and 9 failures across 15 cases, reviewed by Codex rather than an independent human**. Its `evaluate.py` route bypasses `run_chat_turn`, so it does not measure the current chat's clarification/acknowledgement gates, display aliases or bounded conversation memory. New checks should exercise that actual route and keep retrieval quality separate from answer quality. No new evaluation results are claimed by this change. A valid source ID alone does not establish support or completeness, and the small synthetic set is not a production-accuracy estimate.

## Design history

The user first selected Focused chat with expandable supporting policies over a side-by-side evidence workspace. They approved the central layout and requested richer graphics, then explicitly removed evidence controls in favor of a natural chat. The separate scripted preview was updated along that sequence, and the implementation remained reviewable under their approval request. They subsequently accepted the current UI and moved the focus to knowledge-answer evaluation.
