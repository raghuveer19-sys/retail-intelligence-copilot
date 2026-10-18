"""Check demo prerequisites without downloads, inference or Pinecone requests."""

import argparse
import errno
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import socket
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ("streamlit", "python-dotenv", "langchain-core", "tiktoken", "pyyaml", "openai", "pinecone")


def missing_dependencies() -> list[str]:
    missing = []
    for name in DEPENDENCIES:
        try:
            version(name)
        except PackageNotFoundError:
            missing.append(name)
    return missing


def _credential_presence(root: Path) -> dict[str, bool]:
    from retail_copilot.readiness import credential_presence
    return credential_presence(root)


def _validate_inputs(root: Path, settings: dict) -> dict:
    from retail_copilot.answering import answer_limits
    from retail_copilot.conversation import conversation_limits
    from retail_copilot.generate import generation_options
    from retail_copilot.pinecone_ingest import prepare_upload

    generation_options(settings)
    conversation_limits(settings)
    answer_limits(settings)
    required = ("app.py", "assets/chat.css", "prompts/conversation.md", settings["answering"]["system_prompt_file"])
    for relative in required:
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("A required application file is unavailable.")
    return prepare_upload(root, settings)


def _installed_digest(options: dict) -> str:
    from retail_copilot.ollama_embeddings import installed_model_digest
    # Metadata only, loopback-only HTTP, with no proxies, redirects or retries.
    return installed_model_digest({**options, "timeout_seconds": 5})


def check_demo(root: Path = PROJECT_ROOT, *, check_ollama: bool = False) -> list[tuple[str, bool, str]]:
    checks = []
    if sys.version_info < (3, 12):
        return [("Python", False, "Use this project's Python 3.12 or newer.")]
    checks.append(("Python", True, "Supported version."))
    missing = missing_dependencies()
    if missing:
        return checks + [("Dependencies", False, "Missing installed packages: " + ", ".join(missing) + ". See docs/demo-guide.md.")]
    checks.append(("Dependencies", True, "Required packages are installed; nothing was downloaded."))
    try:
        import tomllib
        with (root / "config/settings.toml").open("rb") as handle:
            settings = tomllib.load(handle)
        prepared = _validate_inputs(root, settings)
    except Exception:
        # Do not echo parser text, provider errors or arbitrary configuration values.
        return checks + [("Local inputs", False, "Check config/settings.toml, application files and the prepared corpus. See docs/demo-guide.md.")]
    checks.append(("Local inputs", True, f"{prepared['record_count']} saved chunks match the current approved sources and embedding settings."))
    try:
        presence = _credential_presence(root)
        configured = bool(presence.get("PINECONE_API_KEY", False))
        checks.append(("Pinecone configuration", configured,
                       "API key is present (not verified); the pipeline resolves the host from the configured index name." if configured
                       else "Set PINECONE_API_KEY privately in this project's .env."))
    except Exception:
        checks.append(("Pinecone configuration", False, "The private configuration could not be read; check .env permissions and encoding."))
    if check_ollama:
        try:
            embedding_digest = _installed_digest(settings["embedding"])
            _installed_digest(settings["generation"])
            if embedding_digest != prepared["model_digest"]:
                raise ValueError("Different model version.")
        except Exception:
            checks.append(("Local Ollama models", False,
                           "Check that Ollama is running, both configured models are installed locally, and the embedding model still matches the saved corpus."))
        else:
            checks.append(("Local Ollama models", True, "Both models are available; embedding version matches. No inference or download requested."))
    return checks


def _require_free_port(port: int) -> None:
    """Probe a loopback bind without listening or contacting any service."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))


def launch_demo(port: int) -> int:
    """Start our foreground server only when the local port is not listening."""
    if type(port) is not int or not 1024 <= port <= 65535:
        print("Choose a whole-number port from 1024 to 65535.")
        return 1
    try:
        _require_free_port(port)
    except OSError as error:
        if error.errno in (errno.EADDRINUSE, 10048) or getattr(error, "winerror", None) == 10048:
            print(f"Port {port} is already in use; no existing process was changed.")
            print("Use the address from your existing Week2 terminal, or choose a free --port.")
        else:
            print("Could not check the local port safely. No server was started or stopped.")
        return 1
    command = [sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "app.py"),
               "--server.address", "127.0.0.1", "--server.port", str(port), "--server.headless", "true"]
    print(f"Open http://127.0.0.1:{port} in your browser. Keep this terminal open; Ctrl+C stops this server.", flush=True)
    try:
        return subprocess.run(command, cwd=PROJECT_ROOT, shell=False, check=False).returncode
    except KeyboardInterrupt:
        return 130
    except OSError:
        print("The local server could not start. Check the project environment and docs/demo-guide.md.")
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-ollama", action="store_true", help="Also read the local Ollama model list; never generate, embed or download.")
    parser.add_argument("--launch", action="store_true", help="Check local models, then start Streamlit in this terminal without a PowerShell script.")
    parser.add_argument("--port", type=int, default=8501, help="Local server port, from 1024 to 65535 (default 8501).")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535.")
    print("Demo preflight: local files, installed packages and configuration presence.")
    checks = check_demo(check_ollama=args.check_ollama or args.launch)
    for label, passed, detail in checks:
        print(f"[{'OK' if passed else 'CHECK'}] {label}: {detail}")
    passed = all(check[1] for check in checks)
    if not (args.check_ollama or args.launch):
        print("Ollama was not contacted. Add --check-ollama for local model availability.")
    print("Preflight requested no cloud calls, model inference, downloads or project-data changes.")
    print("This does not verify Pinecone access/quota, answer quality or browser appearance. No OpenAI key is required.")
    if not passed:
        return 1
    return launch_demo(args.port) if args.launch else 0


if __name__ == "__main__":
    raise SystemExit(main())
