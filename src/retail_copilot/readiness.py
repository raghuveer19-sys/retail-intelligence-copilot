"""Report configuration presence locally, without printing values or using APIs."""

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

from retail_copilot.documents import PROJECT_ROOT


CONFIGURATION_NAMES = ("OPENAI_API_KEY", "PINECONE_API_KEY", "PINECONE_INDEX_HOST")


def _local_values(project_root: Path) -> dict:
    """Read only the project's private file; never log its contents."""
    try:
        with (project_root / ".env").open(encoding="utf-8-sig") as handle:
            file_values = dotenv_values(stream=handle, interpolate=False)
    except FileNotFoundError:
        file_values = {}
    except (OSError, UnicodeError):
        raise ValueError(
            "The local .env could not be read. Check its permissions and UTF-8 encoding."
        ) from None

    return file_values


def read_credential(
    name: str, project_root: Path = PROJECT_ROOT,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Read a credential for a caller, without printing it or changing the environment."""
    if name not in CONFIGURATION_NAMES:
        raise ValueError("Unsupported credential name.")
    file_values = _local_values(project_root)
    environment = os.environ if environment is None else environment
    return (environment.get(name, file_values.get(name)) or "").strip()


def credential_presence(
    project_root: Path = PROJECT_ROOT,
    environment: Mapping[str, str] | None = None,
) -> dict[str, bool]:
    """Report presence only; process values take priority, including explicitly empty ones."""
    file_values = _local_values(project_root)
    environment = os.environ if environment is None else environment
    return {
        name: bool((environment.get(name, file_values.get(name)) or "").strip())
        for name in CONFIGURATION_NAMES
    }


def main() -> int:
    print("Local configuration check (no network calls).")
    try:
        presence = credential_presence(PROJECT_ROOT)
    except ValueError as error:
        print(f"Configuration check could not finish: {error}")
        return 1

    for name, is_present in presence.items():
        print(f"{name}: {'present (not verified)' if is_present else 'missing'}")
    print("Presence does not verify keys, index access, credits or billing.")
    print("Local document work can continue without these values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
