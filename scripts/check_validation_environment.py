"""Dependency-free environment probe for blocked validation workflows.

This script is intentionally stdlib-only so it can run in stripped-down Python
environments. It captures the minimum evidence needed to explain why runtime
validation is or is not executable from the current workspace snapshot.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / ".git"
REQUIRED_MODULES = ["pytest", "numpy", "pandas", "scipy"]
WHEELHOUSE_CANDIDATES = ["wheelhouse", "wheels", ".wheels", "vendor", ".vendor"]
PATH_EXECUTABLE_NAMES = ["python.exe", "py.exe", "pytest.exe"]


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def executable_candidates() -> dict:
    """Locate likely Python/test launchers without executing untrusted binaries."""
    by_name = {
        name: shutil.which(name) or shutil.which(name.removesuffix(".exe"))
        for name in PATH_EXECUTABLE_NAMES
    }

    path_hits = []
    seen = set()
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        directory = Path(part)
        for name in PATH_EXECUTABLE_NAMES:
            candidate = directory / name
            key = str(candidate).casefold()
            if key not in seen and safe_exists(candidate):
                seen.add(key)
                path_hits.append(str(candidate))

    common_roots = [
        Path(os.environ[name])
        for name in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)")
        if os.environ.get(name)
    ]
    common_python_candidates = []
    for root in common_roots:
        patterns = [
            root / "Programs" / "Python" / "Python*" / "python.exe",
            root / "Python*" / "python.exe",
        ]
        for pattern in patterns:
            try:
                common_python_candidates.extend(str(path) for path in pattern.parent.glob(pattern.name))
            except OSError:
                continue

    return {
        "which": by_name,
        "path_hits": path_hits,
        "common_python_candidates": sorted(set(common_python_candidates)),
    }


def wheelhouse_probe() -> dict:
    locations = []
    total_wheels = 0
    for name in WHEELHOUSE_CANDIDATES:
        path = ROOT / name
        exists = safe_exists(path)
        wheel_count = 0
        if exists and path.is_dir():
            try:
                wheel_count = sum(1 for _ in path.glob("*.whl"))
            except OSError:
                wheel_count = 0
        total_wheels += wheel_count
        locations.append(
            {
                "path": str(path),
                "exists": exists,
                "top_level_wheel_count": wheel_count,
            }
        )
    return {
        "candidate_locations": locations,
        "total_top_level_wheels": total_wheels,
        "offline_install_source_available": total_wheels > 0,
    }


def git_probe() -> dict:
    required_paths = {
        "HEAD": GIT_DIR / "HEAD",
        "config": GIT_DIR / "config",
        "refs": GIT_DIR / "refs",
        "objects": GIT_DIR / "objects",
        "index": GIT_DIR / "index",
    }
    presence = {
        name: path.is_dir() if path.suffix == "" and name in {"refs", "objects"} else path.exists()
        for name, path in required_paths.items()
    }
    head_text = read_text(required_paths["HEAD"])
    status = "usable" if all(presence.values()) else "incomplete"
    summary = (
        "Git metadata appears complete enough for local repository operations."
        if status == "usable"
        else "Git metadata is incomplete; local git status/log/commit operations are expected to fail."
    )
    return {
        "git_dir": str(GIT_DIR),
        "status": status,
        "summary": summary,
        "head": head_text,
        "required_paths": presence,
    }


def main() -> int:
    dependency_status = {name: module_available(name) for name in REQUIRED_MODULES}
    missing = [name for name, present in dependency_status.items() if not present]
    git_status = git_probe()
    pip_available = module_available("pip")
    wheelhouse_status = wheelhouse_probe()
    launcher_status = executable_candidates()
    runtime_ready = not missing and git_status["status"] == "usable"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(ROOT),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "environment": {
            "cwd": os.getcwd(),
            "path_has_python_launcher": bool(launcher_status["path_hits"]),
            "launcher_candidates": launcher_status,
        },
        "dependencies": {
            "required_modules": dependency_status,
            "missing_modules": missing,
            "runtime_ready": not missing,
        },
        "installer": {
            "pip_available": pip_available,
            "offline_wheelhouse": wheelhouse_status,
            "summary": (
                "pip is available, but no workspace wheelhouse was found."
                if pip_available and not wheelhouse_status["offline_install_source_available"]
                else "pip and a workspace wheelhouse are available."
                if pip_available
                else "pip is not available in this interpreter."
            ),
        },
        "git": git_status,
        "overall_status": "READY" if runtime_ready else "BLOCKED",
        "next_step": (
            "Run targeted and full pytest suites from this interpreter."
            if runtime_ready
            else "Provision a Python environment from requirements-dev.txt and restore a complete .git checkout."
        ),
    }

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
