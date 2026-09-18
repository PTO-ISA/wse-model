#!/usr/bin/env python3
"""Verify that the design sources under docs/design/ are present and unmodified.

The two design documents are verbatim input material. This check records their
digests so that an accidental edit is caught in CI instead of silently changing
the model's source of truth.

Exit codes:
    0  every design source matches its recorded digest
    1  a design source is missing, renamed, or modified

Run with ``--update`` to rewrite the digest manifest after an intentional,
reviewed update of a design document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_DIR = REPO_ROOT / "docs" / "design"
MANIFEST = DESIGN_DIR / "MANIFEST.json"

EXPECTED = {
    "wse-system-architecture-whitepaper.md": {
        "title": "WSE 系统架构设计白皮书",
        "version": "v0.1",
        "date": "2026-09-17",
    },
    "wse-calendar-scheme.md": {
        "title": "WSE Calendar 方案",
        "version": "0917",
        "date": "2026-09-17",
    },
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, object]:
    entries = {}
    for name, meta in sorted(EXPECTED.items()):
        path = DESIGN_DIR / name
        entries[name] = {
            **meta,
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
    return {
        "$comment": (
            "Digest manifest for the read-only design sources. Regenerate with "
            "`python tools/check_design_sources.py --update` after a reviewed "
            "design-document update."
        ),
        "sources": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the digest manifest from the current files",
    )
    args = parser.parse_args(argv)

    if args.update:
        MANIFEST.write_text(
            json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"updated {MANIFEST.relative_to(REPO_ROOT)}")
        return 0

    if not MANIFEST.is_file():
        print(f"error: missing manifest {MANIFEST.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    failures: list[str] = []

    for name in sorted(EXPECTED):
        path = DESIGN_DIR / name
        label = path.relative_to(REPO_ROOT)
        if not path.is_file():
            failures.append(f"missing design source: {label}")
            continue
        if name not in recorded:
            failures.append(f"design source not in manifest: {label}")
            continue
        actual = digest(path)
        if actual != recorded[name]["sha256"]:
            failures.append(
                f"design source modified: {label}\n"
                f"    recorded {recorded[name]['sha256']}\n"
                f"    actual   {actual}"
            )

    for name in sorted(set(recorded) - set(EXPECTED)):
        failures.append(f"manifest lists an unexpected source: {name}")

    if failures:
        print("design source check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\ndocs/design/ is read-only source material. Record a divergence in "
            "docs/decisions/ instead of editing it.",
            file=sys.stderr,
        )
        return 1

    total = sum(recorded[name]["bytes"] for name in EXPECTED)
    print(f"design sources OK: {len(EXPECTED)} files, {total} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
