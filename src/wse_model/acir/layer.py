"""Machine-readable description of the ACIR layer.

Kept in its own module so the CLI can describe the layer **without importing
``agentic_circuit``**: the pure-Python semantic core, and everything that only
reports on it, must keep working on a machine with no toolchain.

The gap list is read from ``README.md`` rather than restated here, so it cannot
drift from the prose that documents it.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["describe_layer", "gaps"]

_README = Path(__file__).with_name("README.md")

#: The five transitions the entry system wires, in the order the design fixes.
RULES: tuple[tuple[str, str, str], ...] = (
    ("load_route_entry", "Step 取数", "the two scalar LDs plus the rbLo/rbHi decode"),
    ("apply_forward", "Step4 path", "the stateless passive {P, L} hop decision"),
    ("admit_send", "Step4 gate", "the CalReg[opcode] release gate"),
    ("epoch_policy", "Step2/Step3", "CalendarNextEpoch(opcode) per opcode domain"),
    ("recv_wait", "Step3 accounting", "the expVal valid-payload byte account"),
)

#: The build commands, in the order a developer needs them.
BUILD_COMMANDS: tuple[tuple[str, str], ...] = (
    (
        "make bootstrap PYCIRCUIT_ROOT=../pyCircuit",
        "install the agentic-circuit Python frontend from a pyCircuit checkout",
    ),
    (
        "make acir-tools PYCIRCUIT_ROOT=../pyCircuit",
        "build the native acir-opt and friends (needs LLVM/MLIR 22.1.8)",
    ),
    (
        "make acir",
        "run the ACIR-layer tests (skipped cleanly without the native tools)",
    ),
    (
        "wse-model acir lower --node 0 --node-count 40",
        "lower one fixed node's system to ACIR text",
    ),
)


def gaps() -> tuple[str, ...]:
    """The gap headings of ``README.md``'s "Gaps against the semantic core"."""
    if not _README.is_file():  # pragma: no cover - the file ships with the package
        return ()
    text = _README.read_text(encoding="utf-8")
    section = text.split("## Gaps against the semantic core", 1)
    if len(section) != 2:
        return ()
    body = section[1].split("\n## ", 1)[0]
    return tuple(match.group(1).strip() for match in re.finditer(r"^### \d+\.\s*(.+)$", body, re.M))


def describe_layer() -> dict[str, object]:
    """Describe the layer: its contract, rules, build path, and documented gaps."""
    return {
        "package": "wse_model.acir",
        "frontend": "agentic_circuit (ACPy 0.5 / ACIR)",
        "authority": (
            "the pure-Python semantic core (wse_model.calendar, wse_model.noc, "
            "wse_model.core, wse_model.host) is the authority; this layer expresses "
            "the same rules and must not disagree"
        ),
        "entry": "wse_model.acir.model.top::acir_top",
        "specialization": (
            "wse_model.acir.model.top::node_lowering_spec "
            "(node_index=0, node_count=40, epoch_tag_bits=8)"
        ),
        "rules": [
            {"name": name, "step": step, "meaning": meaning} for name, step, meaning in RULES
        ],
        "build_commands": [
            {"command": command, "purpose": purpose} for command, purpose in BUILD_COMMANDS
        ],
        "documented_gaps": list(gaps()),
        "gap_count": len(gaps()),
        "toolchain_required": (
            "yes for lowering (@ac.rule and @ac.module need acir-opt); no for the "
            "pure-Python syntax tests, which parse the real source files"
        ),
    }
