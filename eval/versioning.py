"""Golden-set versions and run provenance.

Golden sets live in eval/golden/vN.json and are immutable once a run has used them:
any change to questions, expectations or evidence becomes a new version. Each run
records the version and a content hash, so a notebook re-reading an old run always
scores it against the golden set it was actually evaluated with.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

EVAL_DIR = Path(__file__).parent
GOLDEN_DIR = EVAL_DIR / "golden"
PROJECT_ROOT = EVAL_DIR.parent
# Only these paths affect answers or scores; results and notebooks do not.
CODE_PATHS = ["rag", "eval/evidence.py", "eval/run_eval.py", "requirements.txt"]


def golden_versions() -> list[str]:
    versions = [p.stem for p in GOLDEN_DIR.glob("v*.json") if re.fullmatch(r"v\d+", p.stem)]
    return sorted(versions, key=lambda v: int(v[1:]))


def latest_golden_version() -> str:
    versions = golden_versions()
    if not versions:
        raise FileNotFoundError(f"No golden sets in {GOLDEN_DIR}")
    return versions[-1]


def golden_path(version: str) -> Path:
    path = GOLDEN_DIR / f"{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden set {version} not found; available: {golden_versions()}")
    return path


def load_golden(version: str) -> list[dict]:
    return json.loads(golden_path(version).read_text(encoding="utf-8"))


def sha256_short(data: str | bytes) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()[:12]


def golden_hash(version: str) -> str:
    return sha256_short(golden_path(version).read_bytes())


def git_state() -> dict:
    """Commit and whether answer-affecting code had uncommitted changes."""

    def git(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit = git("rev-parse", "--short", "HEAD")
    status = git("status", "--porcelain", "--", *CODE_PATHS)
    return {"git_commit": commit, "code_dirty": bool(status) if status is not None else None}
