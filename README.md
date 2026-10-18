# Retail Intelligence Copilot

A hands-on RAG learning project for a fictional telecommunications retail colleague, following the updated Week2 `AGENTS.md`. RAG (retrieval-augmented generation) means finding relevant approved document passages and giving them to a language model to support its answer.

**New to this repository?** Follow [the fresh-install guide](docs/getting-started.md). It covers an offline policy viewer and tests, then the complete chat setup with local Ollama and your own Pinecone account. No OpenAI key is needed for the active application.

This repository includes the application, 12 synthetic policy documents, 15 authored evaluation scenarios, prompts, tests and learning documentation. Credentials, downloaded models, generated embeddings and raw evaluation transcripts are excluded. Dated results below describe the original development machine; cloning the code does not provision its services or reproduce those measurements automatically.

Start with [Phase 0: orientation and learning checklist](docs/phase-0-orientation.md). The target covers SIM/eSIM, identity requirements, roaming, billing, devices, click and collect, plans, account authority and troubleshooting. It provides knowledge guidance only and does not perform transactions or represent any real provider.

## Current demo

Start with [the operating guide](docs/demo-guide.md) and [current readiness report](docs/demo-readiness.md). The accepted interface now uses the compact `prompts/answering-grounded-v2.md` prompt and `source_passages` presentation: the model selects evidence, and the application displays whole supplied policy passages instead of its policy paraphrases. Deterministic routing/clarification and an application action guard support the chat. Exact source text preserves wording; relevance, complete coverage and status decisions still need review.

The final offline suite passed **398 tests in 15.914 seconds**. A real Python-launcher test on port 8502 returned HTTP 200 and was stopped; the owned server on 8501 also returned HTTP 200. All 14 selected normal scenarios met the reviewed demo minimums, and the controlled missing-evidence case passed. This comparison combines preserved initial requests, separate reruns and service-free presentation replays; it is not a single fresh run of the final implementation. The six-turn real AppTest rehearsal found one follow-up routing error; a targeted live retest verified the correction, acknowledgement/history retention, reruns and New chat. Reviews are by Codex, not independent human validation. Browser appearance/accessibility remains unverified. Keep the computer plugged in during the demo; local Ollama requests temporarily prevent Windows idle sleep without changing power settings or preventing deliberate sleep.

For a narrow named-policy overview, an empty insufficient draft can fall back to exact matching passages already retrieved. Available source guidance uses neutral introductory wording, while missing referenced policies are named explicitly. These display rules do not establish that the model's uncertainty classification is correct; original drafts and statuses remain in the private evaluation trace.

## Build milestones and preserved baselines

Phase 1 contains 12 fictional telecom documents in `data/knowledge/`: 11 approved sources and one archived SIM policy. The validator checks source metadata, sections and eligibility. The original Streamlit policy viewer is preserved as `library_app.py`. [Read the knowledge-base lesson](docs/knowledge-base.md) for the metadata design and versioning example.

Phase 2 includes real Pinecone indexing. All 33 eligible chunks have real Ollama embeddings and are stored in `retail-copilot-week2`, namespace `telecom-demo-v1`. Reading every record back verified its ID, text, source fields and vector. See [chunking](docs/chunking-experiment.md), [the complete corpus](docs/corpus-embeddings.md) and [actual indexing](docs/pinecone-indexing.md).

Phase 3 has a working terminal retrieval command. Three real searches on 2026-10-17 found 1/1, 2/3 and 1/2 expected source sections at `top_k = 4`, revealing completeness gaps. An optional policy-ID/reference lookup recovered the missing sections: 1/1, 3/3 and 2/2, with 8, 8 and 5 total passages. That enhanced run reported 6 read units including fetches. Default search remains semantic top_k 4. See [the baseline](docs/retrieval.md) and [policy lookup lesson](docs/policy-lookup.md). Real local answers are now available for review, and a runner covers all 15 authored cases. The authored expectations remain separate from measured reports.

Phase 4 has local context, answering instructions and an Ollama generation command. Saved retrieval becomes a labelled evidence pack, preserving whole sections and source metadata. E04 contains eight sections and 5,266 formatted context characters. The new command checks draft format and source IDs, then renders metadata citations. Claim support still requires a separate review. See [context construction](docs/context-construction.md), [answering instructions](docs/answering-instructions.md) and [local generation](docs/local-generation.md).

The first evaluation baseline is complete: **15 real local answers**, all accepted by the format/source-ID checks, and **6 of 15 cases passing separate Codex review**. That review checks meaning, conditions, completeness and response behavior; it is not an independent human review or a production-accuracy estimate. Nine cases failed that historical review. The baseline and its reviews are preserved in `data/processed/evaluation-baseline/`. The completed completeness-prompt comparison passed 7 of 15 cases but introduced material regressions, including an unsupported prohibition when authority evidence was missing, so it was rejected. A narrower clarification prompt and a separate question-position experiment also failed the ambiguous-question check and were rejected. That historical run restored `prompts/answering.md`; it is now preserved as an earlier prompt. The active chat uses `prompts/answering-grounded-v2.md` plus source-passage assembly, because prompt-only trials still lost required conditions. All experiment results remain separate and preserved; see [evaluation results](docs/evaluation.md), [local generation](docs/local-generation.md) and [the review rubric](docs/evaluation-review-rubric.md).

The **first current-chat baseline on 2026-10-18** ran five fresh, isolated scenarios through the same `run_chat_turn` function as Streamlit. All completed; **three met the established scenario minimums under separate Codex review**. E05 retrieved all required sections but lost identity conditions and used overbroad wording; E09 incorrectly asked for clarification before search. E08 passed the safe fallback minimum but could give a more specific next step. This is not a production-accuracy estimate or a direct comparison with the old 15-case run. The new runner's 12 focused checks and the full 322-test suite passed. Results, evidence and separate reviews are preserved in `data/processed/chat-evaluation-2026-10-18/`; see [the current-chat evaluation lesson](docs/chat-evaluation.md).

Week2 uses **LangChain's `Document` container** from `langchain-core` for loaded policies and chunks. A container holds information in a standard structure: `page_content` holds text, `metadata` holds source details, and `id` identifies the policy or section chunk. Our own Python functions still validate policies, select eligible evidence and split sections. See [the container walkthrough](docs/knowledge-base.md#the-langchain-document-container).

The active embedding model is **Ollama's `embeddinggemma:300m`**, with 768 dimensions. The full corpus reported 1,808 input tokens. Pinecone SDK 10.0.0 stores the vectors in a named `embedding` field, alongside text and source metadata. The current local answering candidate is **`qwen3:4b-instruct`**. Earlier thinking-only `qwen3:4b` calls failed, and smaller `qwen2.5:1.5b` answers revealed completeness problems. See [the model comparisons](docs/answer-review.md); a completed request is not proof of accuracy. The [OpenAI preview](docs/embedding-example.md) and [token report](docs/embedding-preparation.md) remain comparison lessons with separate settings and disabled paid access; their counts/prices do not apply to Ollama.

Phase 5 now has a **natural Streamlit chat in `app.py`**, using the approved central layout, teal styling, starter questions and New chat. As requested, it has no source expanders, source buttons, diagnostics panel or policy-library toggle. The pipeline still retains retrieved evidence and metadata citations privately in the Streamlit session. It uses fresh approved Pinecone retrieval, bounded policy lookup, whole-section context and local generation for an answerable question. Source-ID validation still does not establish that a claim is supported.

Conversation memory uses at most three recent user turns and 4,000 history characters, with a 1,000-character question limit. At most 30 exchanges remain visible; New chat clears the session's conversation and private evidence. Ordinary chats are not written to disk. A contextless question such as "Can I replace it?" now asks for specifics before making service requests. Some follow-ups use the local model to propose a standalone search question; conservative checks can ask for clarification instead. This is an English demonstration with limited routing rules, not a guarantee of correct follow-up interpretation. The original 6/15 answer-quality baseline remains unchanged. See [chat behavior, limits and test boundaries](docs/chat-design.md).

Phase 0 includes a configuration report and separate Week2 Git repository. Pinecone authentication and indexing are verified; the key and index host are configured privately in `.env`. The user reports Starter (free), with Builder credits pending. Billing-plan details and remaining quota have not been independently inspected, and no subscription upgrade was made. No OpenAI key is required for local Ollama embeddings.

## Run locally

In PowerShell, change into the project folder:

```powershell
cd "path\to\retail-intelligence-copilot"
```

For the existing prepared environment, use the [Python launch command](docs/demo-guide.md) without activation or reinstallation. Only if restoring the environment, `uv sync` creates this project's separate `.venv` and installs locked dependencies; it can download packages. `--no-active` ignores another project's activated environment. The operating guide includes an offline-cache recovery option.

```powershell
uv sync --no-active
```

Check the sample policies, then run the automated document, chunking, evaluation-specification and configuration tests:

```powershell
uv run --no-active retail-validate
uv run --no-active python -m unittest discover -s tests -v
```

At the configured policy date, 2026-10-15, expect 12 documents loaded, 11 approved and one excluded. The earlier chat-implementation suite passed **281 tests on 2026-10-18**, including **12 UI, 17 pipeline and 18 conversation checks with simulated service responses**. This includes the strengthened history boundary across a failed request. A separate real pipeline check with network connections blocked confirmed that "Can I replace it?" asks for clarification without retrieval. The Streamlit page and health endpoint returned HTTP 200. Real appointment and follow-up requests completed in 94.1 and 137.5 seconds, each with a supported claim checked against the appointments section and one private citation. These are two successful pipeline examples, not a broad quality or latency benchmark. Browser appearance remains unverified. See [the exact follow-up and verification boundaries](docs/chat-design.md).

Print the chunking comparison for the configured authority section. This shows passage text and source details and makes no service calls:

```powershell
uv run --no-active python -m retail_copilot.chunking
```

The defaults reproduce the lesson: 3 passages containing 43 combined words without overlap, 3 containing 53 words with overlap, and one complete 43-word section. The `[chunking_experiment]` settings control this teaching example. Word counts are not model token counts or cost estimates.

Prepare the eligible library as local chunk records. This command uses Week2's Python directly, saves `data/processed/chunks.json` and makes no service calls:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.prepare_chunks
```

Expect 12 documents loaded, 11 eligible, `SIM-1024-v1` excluded, and 33 saved chunks containing 1,169 body-text words. `[chunk_preparation]` selects `section-v1` and the output path. Reruns replace the generated snapshot; they do not append duplicates. Generated files are ignored by Git and can be recreated. Preparation itself does not check model limits; use the separate report below. If preparation fails, do not treat an earlier output file as a successful current result.

For the retained OpenAI comparison, measure body-text tokens and estimate one embedding pass. These figures do not apply to Ollama. This command creates no vectors and makes no model or Pinecone requests. First use downloads the tokenizer vocabulary; later runs use its local cache:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.token_report
```

Expect 33 chunks, 1,404 tokens, sizes of 26–57 tokens and an estimated USD 0.00002808 for one corpus embedding pass at the recorded rate. This is not a bill or the total application cost. The report counts freshly prepared chunks, leaves the export unchanged and flags oversized inputs without truncation. See [the token-counting lesson](docs/embedding-preparation.md).

Preview the retained OpenAI comparison request. It shows 50 input tokens, an expected 1,536-number vector and estimated USD 0.000001 cost. It creates no vector or result file and reads no credential:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.embed_example
```

The user confirmed they still have no OpenAI API key and requested local work. `paid_service_use_enabled` remains false. A future live example requires account/cost review, explicit live mode, an estimated per-run allowance and a privately configured key. See [the walkthrough and test boundaries](docs/embedding-example.md).

Generate one real local embedding using the active Ollama model (already downloaded). A successful result has already been saved; rerunning stops before overwriting it:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.ollama_example
```

Inspect `data/processed/ollama-embedding-example.json` for the actual 768-number vector, unchanged passage, metadata and reported 63-token usage. See [the walkthrough](docs/ollama-embedding-example.md). This calls local Ollama only, with no OpenAI or Pinecone request.

Prepare or refresh the complete embedding corpus locally. This reuses matching vectors and generates missing/changed ones, then saves only a complete validated result:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.prepare_embeddings
```

All 33 vectors are saved in `data/processed/embedding-corpus.json`. The initial run generated 32 and reused one; a verified rerun reused all 33 with zero new embedding requests. The corpus input total is 1,808 Ollama-reported tokens. See [the corpus lesson](docs/corpus-embeddings.md).

Preview the Pinecone ingestion checks locally. This makes no cloud request. The actual 33-record upload is already complete; see [the indexing guide](docs/pinecone-indexing.md) before using `--upload`:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.pinecone_ingest
```

Search with the configured appointment question. This uses local Ollama plus one Pinecone read request, prints candidate passages and saves a local report. It generates no answer:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.retrieve
```

Expect up to four passages with similarity scores, token usage and timing. The observed first passage is the SIM appointments section. Use fictional questions only. See [the lesson](docs/retrieval.md) for measured gaps and the three-case `--baseline` option. This terminal command remains available for inspecting evidence outside the natural chat interface.

The optional `--follow-references` flag adds a bounded lookup of explicitly named policies, using a separate output report. Extra passages retain source details and show no similarity score. This can add one Pinecone fetch per question. See [the worked example, results and limitations](docs/policy-lookup.md) before trying it.

Build and inspect a labelled evidence pack from the saved stolen-SIM result. This reads local files, makes no service calls and saves `data/processed/context-example.json`:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.context --show
```

Expect eight whole sections labelled S1 to S8. These are source references, not a generated answer or proof that the evidence is sufficient. See [the context lesson](docs/context-construction.md) for size limits, tests and the missing-reference example.

Prepare and inspect the answering instructions plus saved evidence. This revalidates the pack and saves `data/processed/answering-preview.json`, without requesting a model answer:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.answering --show
```

Expect an offline preview with allowed source IDs S1–S8. The draft checker rejects unknown IDs and renders source details from metadata. It does not verify that each claim is supported; see [the answering lesson](docs/answering-instructions.md).

Preview the local answering command without making requests:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.generate
```

Add `--run` to request one local draft from the saved evidence. No OpenAI key or fresh Pinecone search is needed. Existing result files are preserved. Read [the local-generation lesson](docs/local-generation.md) before running; a generated draft still requires claim review.

The historical `evaluate.py` runner preserves the 15-case generation baseline and controlled-context E11 experiment. It bypasses the current chat routing and source-passage assembly. Its default `data/processed/evaluation-baseline` belongs to older instructions/settings; do not resume it under the active configuration. Changed experiment identities are refused rather than mixed. Read the preserved [evaluation plan and results](docs/evaluation.md), and use the current-chat runner below for fresh measurements.

For the **current chat pipeline**, preview five isolated scenarios (E01/E05/E07/E08/E09) without service calls or file writes. Choose a fresh folder because the first dated run is already saved:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate_chat --output-dir data/processed/chat-evaluation-next
```

Add `--run` to make fresh local model/Pinecone requests and save separate results in the chosen folder. The first run is preserved in `data/processed/chat-evaluation-2026-10-18`. This runner calls `run_chat_turn`, including its clarification gates, and refuses nonempty output directories even in preview. It never resumes or overwrites a completed run. Keep expected answers outside the pipeline and review the actual claims against their saved evidence; see [the current-chat evaluation lesson](docs/chat-evaluation.md) for commands, artifacts and measurement limits.

Start the natural chat with the Python launcher. It checks existing local prerequisites and model metadata, then starts Streamlit without changing PowerShell execution policy. Opening the welcome screen does not call Pinecone or generate an answer:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --launch
```

Use the local address printed in the terminal. Ollama must be running with the configured embedding and answering models, and the project's Pinecone credentials/index must remain available for real answers. Submitting a clear question can create Pinecone query/fetch usage and local model work; some follow-ups also use a local resolution request. New chat and ordinary reruns make no service requests. There are no automatic retries. Local electricity and hardware costs are unmeasured; account allowance and billing remain unverified. See [the cost model](docs/cost-model.md).

For the separate learning view of the policy library, stop the chat server with Ctrl+C and start:

```powershell
.\.venv\Scripts\python.exe -m streamlit run library_app.py
```

The library viewer reads local documents and needs no API key or model. It is intentionally separate from the chat and makes no Pinecone or model calls. Stop either server with Ctrl+C. The user has accepted the current chat interface; independent browser rendering/accessibility checks remain outstanding.

## Learning path

### Demo milestone completed, 2026-10-19

The application, operating launcher, selected-scenario review, corrected live chat rehearsal and usage notes are complete. See [the readiness report](docs/demo-readiness.md) and `data/processed/demo-final-verification-2026-10-19.json` for the exact verification scope. Local policy requests took roughly 41–99 seconds in selected successful attempts; the final follow-up took 90 seconds. These are observations, not a response-time promise.

Browser appearance/accessibility, independent business review, broader evaluation and production deployment remain outside this verified local demonstration. Exact source copying does not guarantee complete or relevant answers, and raw model status decisions remain imperfect.

1. Inspect documents, approval status, effective dates and metadata (information describing a source).
2. Split policies into passages and create embeddings (number lists representing their meaning).
3. Store and search passages in Pinecone, preserving their source metadata.
4. Send retrieved evidence to the model; validate source references and retain citations from metadata, with evidence inspection outside the natural chat.
5. Evaluate retrieval separately from answer quality, including unsupported questions and action requests.
6. Measure usage and costs and review limitations before considering deployment.

## Configuration and secrets

- `config/settings.toml`: demo date, chunking settings, output locations, active provider/model settings, answering-prompt selection and bounded conversation/display limits. A `.toml` file is a readable configuration file.
- `config/pricing.yaml`: dated public pricing information and explicitly unknown paid rates. A `.yaml` file is another readable configuration format.
- `.env.example`: blank credential fields that can be shared with the project. Enter real credentials only in your ignored local `.env` or environment variables, never in this example file or chat.
- `.env`: the private local configuration file. Readiness, Pinecone ingestion/retrieval, chat requests that reach retrieval and a future enabled OpenAI request read it; offline previews and the separate document viewer do not need it. Git ignoring a file does not encrypt it.
- All supplied policy text is fictional. There is no customer-data upload or transaction execution feature.

The synthetic flag is a validation requirement, not a detector for real personal information. Only use documents deliberately authored as fictional examples.

### Check local configuration

Run this command from Week2 to report whether configuration values are present. It does not print values, connect to either provider, create an index or incur API charges:

```powershell
uv run --no-active retail-check
```

With the current local configuration, the expected result is:

```text
Local configuration check (no network calls).
OPENAI_API_KEY: missing
PINECONE_API_KEY: present (not verified)
PINECONE_INDEX_HOST: present (not verified)
Presence does not verify keys, index access, credits or billing.
Local document work can continue without these values.
```

`missing` is expected until the relevant credentials and index exist; it is not an application failure. `present (not verified)` means only that a non-blank value was found. The command succeeds when it can complete the report, even with missing values; it is not a gate authorising cloud calls. If it cannot read `.env`, it reports a safe error and exits unsuccessfully: check file permissions and save the file as UTF-8.

Only Week2's `.env` is read; parent-folder files are not searched. Existing environment variables take priority, including explicitly empty values, and the check does not change them. The implementation uses [python-dotenv's documented reader](https://bbc2.github.io/python-dotenv/#load-configuration-without-altering-the-environment).

This project has its own Git repository. `.env`, environments, caches, editor settings, generated results and local Streamlit secrets are ignored; `.env.example` contains blank placeholders and is shareable. Never commit a populated credential file. See [the fresh-install guide](docs/getting-started.md) for rebuilding excluded artifacts.

## Documentation

- [Architecture](docs/architecture.md)
- [Knowledge-base design and Phase 1 lesson](docs/knowledge-base.md)
- [Chunking comparison, local preparation and saved records](docs/chunking-experiment.md)
- [Embedding preparation: tokens, input limits and estimated cost](docs/embedding-preparation.md)
- [One-chunk embedding request: preview, local tests and future live use](docs/embedding-example.md)
- [Actual Pinecone indexing and read-back verification](docs/pinecone-indexing.md)
- [Semantic retrieval: first questions, source checks and measured gaps](docs/retrieval.md)
- [Learning journal](docs/learning-journal.md)
- [Decision log](docs/decision-log.md)
- [Cost model](docs/cost-model.md)
- [Evaluation plan](docs/evaluation.md)
- [Demo launch, rehearsal and recovery](docs/demo-guide.md)
- [Current demo readiness and limitations](docs/demo-readiness.md)
- [Natural chat, memory limits and interface checks](docs/chat-design.md)
- [Checking grounded answers through the current chat](docs/chat-evaluation.md)

## Completion

The project is complete only when the user can explain the architecture, retrieval, grounding, evaluation, costs, limitations and production considerations. Deployment, authentication, access controls and operational monitoring remain future work.
