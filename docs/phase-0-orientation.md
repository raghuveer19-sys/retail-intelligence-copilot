# Phase 0: orientation

Date: 2026-10-15. This plan follows the updated Week2 `AGENTS.md`.

## Purpose and two outcomes

Build a fictional telecommunications knowledge assistant for retail colleagues. It should find approved guidance about SIM replacement, eSIM activation, identity requirements, roaming, billing, device returns, click and collect, plans, account authority and troubleshooting.

The **build outcome** is a working application with evidence-based answers, verifiable citations and measurable quality and costs. The **learning outcome** is that the user can explain and evaluate each stage. Neither outcome is established by a page merely opening in the browser.

The assistant supplies guidance. It cannot verify a real identity, modify accounts, activate services, process payments, waive fees or execute transactions. All content will be synthetic and explicitly unrelated to real telecommunications providers.

## The pipeline

```text
Prepare knowledge:
Fictional documents -> load -> clean -> split into passages
                    -> local Ollama embeddings -> Pinecone

Answer a question:
Question -> local Ollama embedding -> Pinecone search
         -> relevant passages and source metadata
         -> construct context -> OpenAI language model
         -> validate references -> answer with source citations

Evaluate: retrieval quality, answer support, citations, latency and cost
```

A passage is a small section of a document, also called a chunk. An embedding is a list of numbers representing text for similarity search. Metadata describes the source, such as its title, policy ID, section and version. Context is the evidence and instructions supplied to the language model. Grounding means supporting the answer's claims with that evidence.

Pinecone retrieves candidate evidence; the language model drafts an answer from selected evidence. Finding a similar passage does not prove that it answers the question. Confidence will be an explained evidence indicator, not an unvalidated probability.

## Current state: checked, recorded and pending

**Latest update, 2026-10-17:** Terminal retrieval is implemented. All 144 tests passed; three real searches found 1/1, 2/3 and 1/2 expected source sections at top_k 4, with 3 reported read units. The baseline exposes missing identity/appointment evidence for review. Generation remains pending and the policy date stays 2026-10-15. See [retrieval lesson](retrieval.md). Entries below record earlier milestones.

**Latest update, 2026-10-15:** All 33 real Ollama embeddings are prepared and stored in Pinecone index `retail-copilot-week2`, namespace `telecom-demo-v1`. Each vector has 768 dimensions. All 127 tests passed; actual namespace count, text/source fields and vectors were checked by fetching every record. The key and host are privately configured. Starter is user-reported with Builder credits pending; billing details and remaining allowance are not independently verified. Retrieval and generation remain pending. The entries below record earlier milestones. See [the current indexing lesson](pinecone-indexing.md).

- Checked today: Python 3.12.15, uv 0.12.23 and Git 2.56.0 are installed; Week2 has its own virtual environment and dependency lock file.
- Initial inspection found no Week2-local Git repository or `.env`. Setup then revealed a surrounding home-directory Git repository; a separate Week2 repository and an ignored blank `.env` have now been created. No commits or remotes were added.
- Phase 1 delivered twelve fictional telecom documents, source/section metadata validation, approval/date selection, a Streamlit library viewer and a local credential-presence check. Phase 2 now uses `text-embedding-3-small` for the embedding baseline and has a one-chunk request integration tested with simulated responses. Live service use is disabled and the generation model remains unset. See [the Phase 1 lesson](knowledge-base.md) and [embedding example](embedding-example.md).
- Tested after Phase 1 on 2026-10-15: all 27 document, evaluation-specification and configuration tests passed, along with three viewer scenarios. The policy validator selected eleven approved sources from twelve documents. The earlier local setup check found all three credential/index values missing; no new service access has been established.
- Phase 2 progress: the reusable comparison reproduces the teaching example, and local preparation saves 33 section chunks with repeatable IDs and source metadata. Loaded policies and chunks now use LangChain's `Document` container at the user's request. All 52 automated tests passed after this migration, and the export content matches the previous snapshot. See [the experiment and preparation lesson](chunking-experiment.md); these checks are not retrieval-quality scores.
- Local embedding preparation now counts 1,404 tokens across 33 chunks, all within the configured per-input limit, and estimates USD 0.00002808 for one corpus embedding pass. All 68 tests passed after this step. See [the token lesson](embedding-preparation.md).
- One-chunk embedding integration now previews the 50-token authority passage and its expected 1,536-number vector. All 85 tests passed, including simulated HTTP responses through the installed SDK. The user confirmed no API key and requested local testing; no real vectors were created.
- Currently pending: question embedding/search, grounded generation, retrieved citations, provider billing reconciliation and live evaluation. Corpus embeddings and Pinecone ingestion are complete. Fifteen evaluation cases are authored, with no live retrieval/answer results yet.

## Tools and accounts

| Item | Plain-language purpose | Status |
| --- | --- | --- |
| Python | Runs our application instructions | Installed |
| Terminal | Lets us run commands and see their output | Available in the IDE |
| uv and `.venv` | Install dependencies in a separate environment for this project | Present |
| Dependencies | Reusable libraries our code relies on | Streamlit, python-dotenv, langchain-core, tiktoken, PyYAML, OpenAI SDK and Pinecone SDK 10.0.0 installed and locked |
| Git repository | Records local versions of the project | Separate Week2 repository initialised; first commit pending |
| OpenAI API account | Supplies embedding and answer-generation services | User reports no API key; account access and billing not verified |
| Ollama | Generates embeddings on this computer | embeddinggemma:300m produced all 33 real 768-dimensional vectors |
| Pinecone account | Stores and searches vectors with source metadata | Authentication and 33 stored records verified; Starter user-reported, Builder credits pending; remaining quota unknown |
| Environment variables and `.env` | Keep local credentials outside application code | Ignored local file contains Pinecone key and host; presence check prints no values |

An API is a service's defined interface for requests from our code. An API key authorises those requests and must remain private. Only the account holder should create credentials and enter them locally. A local Git repository does not publish anything; a remote repository is a separate later decision.

## Phase plan

| Phase | Deliverable | Learning checkpoint |
| --- | --- | --- |
| 0: orientation and setup | Aligned scope, local version control, configuration plan and cost explanation | Explain the role of each component |
| 1: synthetic knowledge base | About 12 telecom documents with sections and governance metadata | Explain why approval, version and source information matter |
| 2: ingestion | Cleaning, two chunking strategies, embeddings and verified Pinecone records | Explain what gets stored and why chunk boundaries matter |
| 3: retrieval | Questions retrieve evidence with titles, sections and relevance scores | Separate similarity from evidence sufficiency |
| 4: grounded generation | Answers, source citations, clarification and insufficient-evidence handling | Explain how to check a claim against its source |
| 5: interface and observability | Questions, answers, expandable evidence, latency, token counts and estimated costs | Inspect how an answer was produced without exposing hidden reasoning |
| 6: evaluation | A baseline scorecard and evidence-led improvements | Distinguish retrieval, grounding, citation accuracy, latency and cost |

The brief mentions approximately 30 evaluation questions and also a 15-question set in Phase 6. Plan for 30 overall, with 15 as an initial baseline subset. Begin writing cases with the knowledge documents rather than postponing evaluation until Phase 6.

## Decisions and assumptions

- The updated telecom and OpenAI requirements supersede the earlier general-retail and provisional Ollama design. Phase 1 replaced the generic corpus through an explained, tested migration; the viewer remains runnable.
- Use LangChain's `Document` container in Week2, as explicitly requested on 2026-10-15; keep validation, eligibility and chunking logic in visible Python functions. This refers to the library and does not change the separate practice folder.
- Selected embedding baseline: `text-embedding-3-small`, with 1,536 dimensions, `cl100k_base` encoding and a documented 8,192-token input maximum recorded in settings. Local token checks are implemented; service calls remain pending. Candidate generation model: `gpt-6-luna`, still unset in settings. Neither selection nor local size checks establish account access or retrieval quality. See [the embedding decision](architecture.md#embedding-baseline-selected-not-yet-run).
- Confirm account access, provider plan, credit conditions and an explicit learning spend limit before paid calls. Expected Pinecone credits do not establish readiness for OpenAI requests. Public prices do not verify account eligibility or provide spending enforcement.
- Continue fictional document design and local chunking without credentials. Preserve the chosen architecture while the user arranges access.
- Use local Streamlit initially. Deployment and real customer data are outside this demonstration.
- Phase 1 records the planned namespace `telecom-demo-v1` to identify a corpus revision. Metadata filters describe eligible records within that corpus; these concepts are not interchangeable. No namespace or index has been created.

## Phase 0 file plan

| File or local resource | Purpose |
| --- | --- |
| `README.md` | Describe the telecom target and accurately label the current starter |
| `docs/phase-0-orientation.md` | Keep this orientation and checklist |
| `docs/architecture.md` | Distinguish implemented stages from the planned pipeline |
| `docs/learning-journal.md` | Record concepts, questions and observed verification results |
| `docs/decision-log.md` | Record scope, choices, assumptions and revisit conditions |
| `docs/cost-model.md` | Explain triggers, formulas, monitoring and cost controls |
| `config/pricing.yaml` | Store dated candidate rates with official sources |
| `.env.example` and ignored `.env` — completed | Provide blank OpenAI/Pinecone configuration fields |
| `src/retail_copilot/readiness.py` — completed | Report presence without printing values; also read a private credential for an enabled live caller |
| `tests/test_readiness.py` — completed | Check missing values, precedence, project isolation and safe output |
| `config/settings.toml` — providers and corpus aligned | Models and index remain unset; Phase 1 points to telecom sources and names the planned corpus namespace |
| `pyproject.toml` and `uv.lock` — updated | Install and lock python-dotenv; defer service SDKs until their stage |
| `.gitignore` and local `.git` — checked/initialised | Ignore private files and establish a Week2 boundary; no commit yet |

## Initial learning checklist

- [ ] Explain the difference between finding evidence and writing an answer.
- [ ] Explain why a similar passage may still be insufficient evidence.
- [ ] Identify which components run locally and which send data to a provider.
- [ ] Explain why credentials belong outside source code.
- [ ] Describe a document, a chunk, an embedding and source metadata.
- [ ] Compare fixed-size and section-aware chunking using actual examples.
- [ ] Trace a question through retrieval, context construction, generation and citation rendering.
- [ ] Distinguish a knowledge request from an action the copilot cannot perform.
- [ ] Explain an evaluation failure and how to measure an improvement.
- [ ] Estimate and monitor the cost of indexing documents and answering a question.

Understanding check: if a SIM policy is retrieved but account-authority rules are missing, what can the assistant safely conclude, and what must remain unanswered?

User response: "if no account authority exists, dont allow for sim replacement". Coaching clarification: not retrieving authority information is different from proving that authority does not exist. The assistant should say it cannot confirm permission from the available evidence; it cannot approve or block a replacement. The distinction was explained, but understanding should be revisited with a new example.

## Orientation result

Orientation initially changed documentation only. Local setup then added the configuration check, blank credential template, planned-provider settings and isolated Git repository. Phase 1 subsequently added the fictional telecom library and metadata validation. No real credentials, account settings or cloud resources were changed, and no embedding or generation calls were made. Local chunking experiments can proceed; service-backed ingestion still requires account setup and cost review.
