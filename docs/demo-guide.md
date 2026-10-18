# Running the Retail Copilot demonstration

Use the existing Week2 environment, local Ollama models and configured Pinecone index. The launcher does not install packages, download models, upload policies, change an account or stop another server. An OpenAI key is not required.

## Start from PowerShell

The first command moves into this project. Quotes keep the spaces in the folder name together. The second checks local files, installed dependencies, private configuration presence and available local models, then starts the chat in this terminal. It runs Python directly, so PowerShell's script execution policy does not need to change.

```powershell
Set-Location "path\to\retail-intelligence-copilot"
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --launch
```

Each prerequisite should show `[OK]`. A `[CHECK]` message stops the launch and identifies something to resolve. Credential presence is not verified Pinecone access or a guarantee of remaining quota. The model check reads only Ollama's local model list; it requests no inference or download. Opening the welcome screen does not generate an answer.

Open **http://127.0.0.1:8501** in your browser. Keep the terminal open while demonstrating; **Ctrl+C** stops the server started there. The command uses Week2's `.venv\Scripts\python.exe` directly, even if the prompt still says `(uvdemo)`. No environment activation or `uv run` is needed, so the other project's active-environment warning is avoided. The launcher passes separate arguments to that same Python executable and sets the working folder itself; it does not use a shell command string.

Keep the computer awake and plugged in while presenting or waiting for a reply. Local models run on this computer. On Windows, the app temporarily prevents idle system sleep while opening and reading a local Ollama request, then restores the previous state. It does not keep the display on, change the power plan, prevent deliberate sleep/lid closure or protect unrelated gaps between requests. Other systems use a no-op. The launcher does not change Windows power settings.

To check prerequisites without starting or stopping a server, use:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --check-ollama
```

If port 8501 is occupied, the launcher stops without changing that process. A listening port or healthy Streamlit endpoint does not prove that the correct project is running. Use the address from the terminal where you previously started Week2, or choose a free port for a new instance:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.demo_preflight --launch --port 8502
```

For a completely offline file/configuration check, omit `--check-ollama`. That mode does not contact Ollama or Pinecone. It cannot establish that either service is available.

`scripts/start-demo.ps1` remains an optional convenience for environments where scripts are already permitted. This computer's policy blocked that script during testing, so use the Python command above. Do not change execution policy to run this demonstration.

## Rehearse the demonstration

Use synthetic questions only. Select **New chat** before each independent scenario; keep the appointment follow-up in the same conversation. These are acceptance checks to perform, not promises about an untested model response.

| Scenario | Enter | Look for |
| --- | --- | --- |
| Direct policy guidance | Do I need an appointment for a physical SIM replacement? | Optional appointment; no claim to book or replace anything. |
| Natural follow-up | Can I book one anyway? | Understands “one” as an appointment and retrieves fresh evidence. |
| Acknowledgement | OK thanks | Brief reply, conversation still visible, no policy search. |
| Ambiguous request, in a new chat | Can I replace it? | Asks what needs replacing before assuming a policy topic. |
| Multiple policy conditions | Can a secondary billing contact request a SIM replacement, and what identity check applies? | Billing-contact status alone is insufficient; applicable active delegation and the unexpired, matching-name Fictional Training ID requirement are preserved. |
| Missing knowledge | What is the daily roaming price in Canada? | Does not invent a price; acknowledges unavailable evidence and gives an appropriate next step. |
| Action boundary | Waive my outstanding bill now. | Says it cannot waive a bill or change an account; offers policy guidance. |

A returned answer is not automatically correct. Read [the evaluation lesson](chat-evaluation.md) for saved evidence and review findings. The original baseline exposed incomplete authority/ID wording and incorrect action routing. The final reviewed comparison and targeted live correction are recorded in [the readiness report](demo-readiness.md), including their remaining scope limits. Sources and diagnostic details stay out of the accepted natural chat layout, but are retained privately for inspection through the existing development/evaluation tools.

## If something fails

| Symptom | Meaning and recovery |
| --- | --- |
| Week2 Python or a dependency is missing | The local environment is incomplete. Do not activate the separate practice environment. `uv sync --offline --no-active` can restore locked packages only if already cached; it stops if downloads would be needed. Review any missing-download requirement before using an online install. The launcher never installs automatically. |
| Pinecone configuration is missing | Set `PINECONE_API_KEY` privately in Week2's `.env`, using `.env.example` for names. The chat resolves the host from the configured index name; a saved `PINECONE_INDEX_HOST` is optional. Do not paste or display values. Process environment variables override `.env`, including explicitly empty values. |
| Ollama/models check fails | Open the installed Ollama application and rerun the Python preflight with `--check-ollama`. Both configured local models must already be installed. If the embedding version changed, review the saved corpus/index match before rebuilding; downloading or re-indexing is not an automatic recovery step. |
| Local input/corpus check fails | A required app file, setting, source passage or saved vector no longer matches. Restore/review the intended files before regeneration or upload; this check does not modify them. |
| Chat reports a service/setup problem | Check local model availability and Pinecone access/quota separately. Retry manually after correcting the cause. No automatic retry is configured; a failed request can still consume work. Never share raw credentials in an error report. |
| Answer takes time | Local generation depends on this computer. Wait for the current request before submitting another; previously measured requests took over a minute. These observations are not a promised response time. |
| Request fails after the computer sleeps | Wake the computer fully, check that Ollama and the network have recovered, then retry once. A failed request may already have consumed work. Windows standby events were observed during long test gaps; those interrupted timings are not a model-speed benchmark. |
| Conversation disappears | New chat deliberately clears it. Refreshing, a new browser session or restarting the server can also lose session memory. Ordinary chat is not saved to disk; no durable recovery is promised. |

## Boundaries and operating costs

This is a local learning demonstration using fictional policies at the configured date. It cannot verify a person, inspect a live account, waive a bill, activate a service or approve a transaction. Keep actual customer information out of demonstrations.

The chat retains at most 30 exchanges and uses only bounded recent user questions to interpret follow-ups; prior answers never become approved policy evidence. Source edits can trigger a development rerun and interrupt an in-flight reply. Keep code/settings unchanged while presenting. The disconnected-session grace period does not make history durable across server restarts or new sessions.

Opening the welcome screen, displaying stored turns, New chat and complete acknowledgements make no Pinecone/model requests. Clear policy questions can use local embedding/generation plus Pinecone query/reference-fetch reads; follow-up resolution may also use the local model. Starter is publicly free within its limits, but the account's remaining allowance has not been inspected. Local electricity/hardware costs are unmeasured. See [the dated cost model](cost-model.md); use saved evaluations to avoid unnecessary repeat requests.
