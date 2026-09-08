"""CONSOLE AI Skill - Python tool for analyzing projects with CONSOLE."""

import io
import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import fnmatch

import api_client

DEFAULT_SERVER = "https://dashboard.consoleproject.eu/api/v1"
CONFIG_FILE = ".console-skill.json"
DEFAULT_IGNORE = {
    CONFIG_FILE,
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    ".claude",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "*.pyc",
    ".env",
    ".env.*",
}


@dataclass
class Config:
    server_url: str
    api_key: str

    def to_dict(self) -> dict:
        return {"server_url": self.server_url, "api_key": self.api_key}

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            server_url=data.get("server_url", DEFAULT_SERVER),
            api_key=data["api_key"],
        )


def find_git_root(start: Path) -> Optional[Path]:
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return None


def load_config(project_dir: Path) -> Config:
    config_path = project_dir / CONFIG_FILE
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return Config.from_dict(data)

    # Try env fallback
    server_url = os.environ.get("CONSOLE_SERVER_URL", DEFAULT_SERVER)
    api_key = os.environ.get("CONSOLE_API_KEY")
    if api_key:
        return Config(server_url=server_url, api_key=api_key)

    raise ConfigMissingError(
        f"CONSOLE skill is not configured for {project_dir}. "
        f"Create {CONFIG_FILE} with {{'server_url': '...', 'api_key': '...'}} or set CONSOLE_API_KEY."
    )


class ConfigMissingError(Exception):
    pass


def write_config(project_dir: Path, server_url: str, api_key: str) -> Config:
    config_path = project_dir / CONFIG_FILE
    config = Config(server_url=server_url, api_key=api_key)
    config_path.write_text(
        json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return config


def _should_ignore(rel_path: str, gitignore_patterns: set[str]) -> bool:
    parts = Path(rel_path).parts
    for part in parts:
        for pattern in DEFAULT_IGNORE:
            if fnmatch.fnmatch(part, pattern):
                return True
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
    return False


def _read_gitignore(project_dir: Path) -> set[str]:
    gitignore = project_dir / ".gitignore"
    patterns = set()
    if not gitignore.exists():
        return patterns
    for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line.rstrip("/"))
    return patterns


def zip_project(project_dir: Path, extra_ignore: Optional[set[str]] = None) -> bytes:
    gitignore_patterns = _read_gitignore(project_dir)
    extra_ignore = extra_ignore or set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            rel_root = Path(root).relative_to(project_dir)
            dirs[:] = [
                d
                for d in dirs
                if not _should_ignore(str(rel_root / d), gitignore_patterns | extra_ignore)
            ]
            for f in files:
                full_path = Path(root) / f
                rel_path = full_path.relative_to(project_dir)
                if _should_ignore(str(rel_path), gitignore_patterns | extra_ignore):
                    continue
                zf.write(full_path, rel_path)
    return buffer.getvalue()


def create_job(
    config: Config,
    project_dir: Path,
    project_version: Optional[str] = None,
    details: Optional[str] = None,
) -> int:
    zip_bytes = zip_project(project_dir)
    job_id = api_client.create_job(
        server=config.server_url,
        token=config.api_key,
        zip_name=f"{project_dir.name}.zip",
        zip_bytes=zip_bytes,
        project_version=project_version,
        details=details,
    )
    if job_id is None:
        raise RuntimeError("Failed to create CONSOLE job")
    return job_id


def poll_job(
    config: Config, job_id: int, timeout_seconds: int = 600, interval_seconds: int = 10
) -> dict | str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = api_client.get_job_status(config.server_url, config.api_key, job_id)
        if isinstance(status, dict):
            state = status.get("status")
            if state in ("completed", "failed", "error"):
                return status
        elif isinstance(status, str) and status.lower() in ("completed", "failed", "error"):
            return {"status": status.lower()}
        time.sleep(interval_seconds)
    raise TimeoutError(f"CONSOLE job {job_id} did not complete within {timeout_seconds}s")


def get_clues(config: Config, job_id: int) -> list[dict]:
    return api_client.get_clues(config.server_url, config.api_key, job_id=job_id)
