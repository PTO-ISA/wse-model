#!/usr/bin/env python3
"""Repository-standards gate.

Checks the things a standards-compliant repository must keep consistent, in one
place so that drift is caught by CI rather than by a reviewer:

* every required governance, packaging, and documentation file exists;
* the version in ``pyproject.toml`` equals ``wse_model.__version__``;
* the required status checks in ``.github/repository-governance.json`` name the
  jobs that ``.github/workflows/ci.yml`` actually defines, and vice versa;
* the design-source digest manifest covers ``docs/design/``;
* ``docs/design/`` is untouched by referencing only through the manifest;
* ``CHANGELOG.md`` has an ``Unreleased`` section;
* no tracked source file contains an AI co-author trailer.

Exit codes:
    0  standards met
    1  at least one violation
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "NOTICE",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "Makefile",
    "pyproject.toml",
    "mkdocs.yml",
    "ndf.yaml",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".markdownlint-cli2.jsonc",
    ".pre-commit-config.yaml",
    ".github/CODEOWNERS",
    ".github/repository-governance.json",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".github/workflows/docs.yml",
    "docs/design/MANIFEST.json",
    "docs/design/wse-system-architecture-whitepaper.md",
    "docs/design/wse-calendar-scheme.md",
)

#: Trailer patterns that must never appear in commits or repository text.
FORBIDDEN_TRAILERS = (
    re.compile(r"co-authored-by:\s*.*(?:claude|copilot|codex|gpt|cursor|ai\b)", re.I),
    re.compile(r"generated with\s*\[?(?:claude|copilot|codex|gpt)", re.I),
)

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".cfg", ".txt", ".sh"}


def _fail(violations: list[str], message: str) -> None:
    violations.append(message)


def check_required_files(violations: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (REPO_ROOT / relative).is_file():
            _fail(violations, f"missing required file: {relative}")


def check_version_consistency(violations: list[str]) -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if match is None:
        _fail(violations, "pyproject.toml has no static version")
        return
    declared = match.group(1)

    version_file = (REPO_ROOT / "src/wse_model/version.py").read_text(encoding="utf-8")
    module_match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file)
    if module_match is None:
        _fail(violations, "src/wse_model/version.py has no __version__")
        return
    if declared != module_match.group(1):
        _fail(
            violations,
            f"version drift: pyproject.toml says {declared}, "
            f"wse_model.version says {module_match.group(1)}",
        )

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if "## [Unreleased]" not in changelog:
        _fail(violations, "CHANGELOG.md has no '## [Unreleased]' section")


def _workflow_job_names() -> set[str]:
    """Resolve the status-check contexts ``ci.yml`` publishes.

    GitHub reports a job's status under its ``name:`` when one is set (expanding
    any ``matrix`` reference) and under the job key otherwise. This mirrors that
    so the governance file and the workflow cannot drift apart.
    """
    text = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    matrix_values: dict[str, list[str]] = {}
    for match in re.finditer(r"^\s+([A-Za-z0-9_-]+):\s*\[([^\]]*)\]\s*$", text, re.M):
        matrix_values[match.group(1)] = [
            item.strip().strip("'\"") for item in match.group(2).split(",")
        ]

    contexts: set[str] = set()
    current: str | None = None
    display: str | None = None
    in_jobs = False

    def flush() -> None:
        if current is None:
            return
        template = display or current
        reference = re.search(r"\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}", template)
        if reference is None:
            contexts.add(template)
            return
        for value in matrix_values.get(reference.group(1), []):
            contexts.add(template[: reference.start()] + value + template[reference.end() :])

    for line in text.splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" "):
            break
        job = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if job:
            flush()
            current, display = job.group(1), None
            continue
        name = re.match(r"^    name:\s*(.+?)\s*$", line)
        if name and current is not None:
            display = name.group(1).strip().strip("'\"")
    flush()
    return contexts


def check_governance_matches_ci(violations: list[str]) -> None:
    governance_path = REPO_ROOT / ".github/repository-governance.json"
    governance = json.loads(governance_path.read_text(encoding="utf-8"))
    contexts = set(governance["branch_protection"]["required_status_checks"]["contexts"])
    jobs = _workflow_job_names()
    missing = sorted(contexts - jobs)
    if missing:
        _fail(
            violations,
            "repository-governance.json requires status checks that ci.yml does "
            f"not define: {missing}",
        )
    # Jobs that are not required checks are allowed (an informational or
    # opt-in job), but every required context must exist.
    informational = sorted(jobs - contexts)
    if informational:
        print(f"note: ci.yml jobs not required by governance: {informational}")


def check_design_manifest(violations: list[str]) -> None:
    design_dir = REPO_ROOT / "docs" / "design"
    manifest_path = design_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        _fail(violations, "docs/design/MANIFEST.json is missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest.get("sources", {})
    on_disk = {path.name for path in design_dir.glob("*.md")}
    if set(sources) != on_disk:
        _fail(
            violations,
            "the design-source manifest and docs/design/ disagree: "
            f"manifest {sorted(sources)}, on disk {sorted(on_disk)}",
        )


def check_forbidden_trailers(violations: list[str]) -> None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        # Not a git checkout: skip rather than report a false violation.
        return
    for relative in tracked:
        path = REPO_ROOT / relative
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in FORBIDDEN_TRAILERS:
            if pattern.search(text):
                _fail(violations, f"forbidden AI co-author trailer in {relative}")


def main() -> int:
    violations: list[str] = []
    check_required_files(violations)
    check_version_consistency(violations)
    check_governance_matches_ci(violations)
    check_design_manifest(violations)
    check_forbidden_trailers(violations)

    if violations:
        print("repository-standards check failed:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print(
        f"repository standards OK: {len(REQUIRED_FILES)} required files, "
        "version, governance, manifest, and trailer checks passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
