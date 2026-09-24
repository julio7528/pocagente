"""Create an ignored runtime env file with a random Docker service token."""

from __future__ import annotations

import os
from pathlib import Path
import secrets


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    secret_directory = repository_root / ".docker-secrets"
    env_path = secret_directory / "agent-api.env"
    legacy_token_path = secret_directory / "agent-api-service-token"
    secret_directory.mkdir(exist_ok=True)
    if env_path.exists():
        print("Docker service token env file already exists; existing token retained.")
        return
    token = (
        legacy_token_path.read_text(encoding="utf-8").strip()
        if legacy_token_path.is_file()
        else secrets.token_urlsafe(48)
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(env_path, flags, 0o600)
    except FileExistsError:
        print("Docker service token env file already exists; existing token retained.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"AGENT_API_SERVICE_TOKEN={token}\n")
    if legacy_token_path.is_file():
        legacy_token_path.unlink()
    print("Created the ignored local Docker service token env file.")


if __name__ == "__main__":
    main()
