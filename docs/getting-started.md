# Set up a fresh copy

This guide prepares a new checkout. Historical lesson pages describe the original development environment; its credentials, installed models, Pinecone index contents and generated reports do not come with the repository.

The commands below use Windows PowerShell, the tested development environment. Keep the terminal in the repository root. Python 3.12 is selected by `.python-version`.

## 1. Get the code and Python environment

Install Git, Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/) first. `uv` manages the project's isolated Python environment and locked package versions. These commands download the repository and its dependencies:

```powershell
git clone https://github.com/raghuveer19-sys/retail-intelligence-copilot.git
cd retail-intelligence-copilot
uv sync --locked --no-active
```

Use this project's Python directly in later commands. You do not need to activate another environment or change PowerShell execution policy. Dependency downloads use network traffic; installation does not call a model API or Pinecone.

## 2. Check the code without cloud services

Validate the synthetic policy library, then run the automated suite. Tests use local fixtures and simulated service responses; they do not require real API keys, Ollama models or a Pinecone index. The first test run may download tokenizer vocabulary into the ignored `.cache/` folder, so a new environment can require internet access without making a billed model API call.

```powershell
uv run --no-active retail-validate
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expect 12 policy documents: 11 eligible and one archived for the fixed policy date of 15 October 2026. The development suite last passed 398 tests; a successful test run is not proof of live answer accuracy.

To explore the policies without model or Pinecone calls, start the separate library viewer:

```powershell
.\.venv\Scripts\python.exe -m streamlit run library_app.py
```

Open the local address printed in the terminal. Press Ctrl+C to stop this viewer before starting the chat on the same port. The viewer is an offline way to explore the dataset, not a substitute for the retrieval pipeline.

## 3. Install the local models

Install and start [Ollama](https://ollama.com/download), then download the two configured models:

```powershell
ollama pull embeddinggemma:300m
ollama pull qwen3:4b-instruct
```

The first creates vectors for search; the second selects evidence and resolves some follow-up questions. Model downloads use bandwidth and disk space. Inference runs on your computer, with no external model API fee; hardware and electricity costs still apply. The application expects Ollama at `http://127.0.0.1:11434`.

Model tags can be updated by their publisher. The application records the installed embedding model's digest, which identifies its version. It rejects mismatched local/indexed data rather than assuming the same tag always means identical vectors.

## 4. Configure your own Pinecone account

Create a Pinecone account/project and obtain a key through its console. Copy the example file only if your checkout does not already have `.env`:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Open `.env` in your editor and fill in `PINECONE_API_KEY` privately. Leave `OPENAI_API_KEY` blank. Leave `PINECONE_INDEX_HOST` blank for initial setup; successful ingestion saves the host automatically. Never put a real key in `.env.example`, source code, screenshots or a Git commit.

Review the `[retrieval]` settings in `config/settings.toml`: the default index is `retail-copilot-week2`, namespace `telecom-demo-v1`, with 768-dimensional cosine vectors in AWS `us-east-1`. Use an isolated index for this demonstration, especially if your account already has an index with that name. Index names are scoped to your account/project; cloning this repository does not grant access to the author's index.

The original user reported Starter. Your account plan and remaining allowances may differ. Writes, reads, storage and data transfer consume Pinecone usage; check your console and the dated [cost model](cost-model.md) before uploading. This application does not upgrade your subscription or enforce a provider spending cap.

## 5. Build the local corpus

Prepare whole-section chunks, then generate real embeddings using local Ollama:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.prepare_chunks
.\.venv\Scripts\python.exe -m retail_copilot.prepare_embeddings
```

Expected outputs are `data/processed/chunks.json` and `data/processed/embedding-corpus.json`, with 33 eligible chunks/vectors. The archived SIM version is excluded. These commands make no Pinecone or OpenAI calls. Unchanged valid embeddings can be reused on later runs; changed inputs or model versions require new embeddings.

## 6. Preview, then populate Pinecone

First validate the prepared data and preview the configured destination. This command makes no cloud request:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.pinecone_ingest
```

After checking the destination and account allowance, the following command contacts Pinecone, creates/connects the configured index, uploads the synthetic records and reads them back for verification. It consumes account write/read/storage allowances and may incur charges under your plan:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.pinecone_ingest --upload
```

Success reports 33 verified records and saves the host in your ignored `.env`. If existing records or the model do not match, stop and inspect the destination. Do not delete another index or assume a timeout means nothing was written. See [indexing and recovery](pinecone-indexing.md).

## 7. Launch the chat

The launcher checks installed dependencies, prepared local data, credential presence and the local model list, then starts Streamlit:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --launch
```

Open `http://127.0.0.1:8501`. Try: “Do I need an appointment for a physical SIM replacement?” and then “Can I book one anyway?” A new chat with “Can I replace it?” should ask for clarification. “Waive my outstanding bill now” should explain the action boundary.

Keep Ollama, the terminal and internet access to Pinecone available. Preflight does not verify Pinecone access/quota or answer quality. Local policy requests took roughly 41–99 seconds on the original computer; your timings can differ. The app is local and is not deployed by pushing this repository to GitHub.

## Evaluation and included artifacts

`evaluation/cases.json` contains 15 authored scenarios with expected behavior. `retail_copilot.evaluate_chat` previews current chat evaluation without calling services; `--run` performs fresh requests and writes a new result directory. Follow [the evaluation method](chat-evaluation.md) before executing live cases. Expected answers are not supplied to the answering model.

Historical raw results, vectors and chat transcripts under `data/processed/` are excluded from Git. Dated findings and their limitations remain in the documentation; those raw files referenced in lessons will not exist in a fresh checkout. New preparation/evaluation commands recreate new artifacts, not the original observations. Ordinary chat history remains session-only.

The app provides guidance from synthetic policies and cannot perform real account actions. Exact source text and valid citations do not prove complete or relevant answers. Browser/mobile/accessibility checks, independent business review and production operations remain outside the verified local demonstration.
