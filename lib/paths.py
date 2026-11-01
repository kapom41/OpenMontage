"""Canonical repository paths — single source of truth.

The projects root is the most load-bearing path in the system: checkpoints
are written under it, tool events are attributed against it, and the Backlot
board watches it. Define it once.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Overridable for staging/screenshots/tests. Everything — checkpoint writes,
# event attribution, the Backlot board — follows the same root.
PROJECTS_DIR = Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR") or (REPO_ROOT / "projects"))


def _windows_long_path_prefix(path: Path) -> Path:
    """Return a path with Windows extended-length prefix (\\\\?\\) if needed.
    
    Windows MAX_PATH is 260 chars by default. The \\\\?\\ prefix allows up to 32,767 chars.
    Only applies on Windows when path length exceeds 240 chars (safety margin).
    """
    if sys.platform != "win32":
        return path
    path_str = str(path.resolve())
    if len(path_str) > 240:
        # Extended-length path prefix
        if not path_str.startswith(r"\\?\\"):
            path_str = r"\\?\\" + path_str
    return Path(path_str)


def safe_project_path(project_id: str) -> Path:
    """Get the project directory with Windows long path support."""
    path = PROJECTS_DIR / project_id
    return _windows_long_path_prefix(path)


def safe_artifact_path(project_id: str, artifact_name: str) -> Path:
    """Get an artifact path with Windows long path support."""
    path = PROJECTS_DIR / project_id / "artifacts" / f"{artifact_name}.json"
    return _windows_long_path_prefix(path)


def safe_checkpoint_path(project_id: str, stage: str) -> Path:
    """Get a checkpoint path with Windows long path support."""
    path = PROJECTS_DIR / project_id / f"checkpoint_{stage}.json"
    return _windows_long_path_prefix(path)
