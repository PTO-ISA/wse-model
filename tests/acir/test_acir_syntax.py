"""Pure-Python syntax and parse checks for the ACIR layer.

These tests need no toolchain. They parse the **real** source files with the
frontend's own ``parse_queue_program``, so an arity, keyword, scope, or expression
mistake in the model fails here before anyone needs a native build.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# The gate is the frontend, not the toolchain: parsing needs no native build.
# importorskip at module scope keeps collection clean in CI, where the frontend is
# absent because it is not published on PyPI.
pytest.importorskip(
    "agentic_circuit",
    reason="the agentic_circuit frontend is not installed (not published on PyPI)",
)
from agentic_circuit._queue_frontend import parse_queue_program  # noqa: E402

from wse_model.acir.model import top as top_module  # noqa: E402

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ACIR = ROOT / "src" / "wse_model" / "acir"
ENTRY = ACIR / "model" / "top.py"
BLOCKS = ACIR / "blocks"
CONTRACT = ACIR / "contract"

#: The entry file is the single captured source; its fields must therefore be
#: declared in it (see the README gap on the source closure).
ENTRY_TEXT = ENTRY.read_text(encoding="utf-8")


def _parse(text: str, system: str, **static):
    program = parse_queue_program(text, system, static or None)
    assert program.diagnostics == ()
    return program


# -- the real entry file parses --------------------------------------------


def test_entry_file_parses_as_a_queue_program() -> None:
    program = _parse(ENTRY_TEXT, "acir_top", node_index=0, node_count=40, epoch_tag_bits=8)
    assert program.system == "acir_top"


def test_entry_file_parses_at_the_other_q1_reading() -> None:
    _parse(ENTRY_TEXT, "acir_top", node_index=47, node_count=48, epoch_tag_bits=16)


def test_entry_file_parses_at_every_node_of_the_baseline() -> None:
    for node in range(40):
        _parse(ENTRY_TEXT, "acir_top", node_index=node, node_count=40, epoch_tag_bits=8)


def test_entry_file_declares_exactly_one_system() -> None:
    tree = ast.parse(ENTRY_TEXT)
    systems = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(decorator, ast.Attribute) and decorator.attr == "system"
            for decorator in node.decorator_list
        )
    ]
    assert systems == ["acir_top"]


def test_entry_file_declares_the_one_payload_type() -> None:
    tree = ast.parse(ENTRY_TEXT)
    structs = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(decorator, ast.Attribute) and decorator.attr == "struct"
            for decorator in node.decorator_list
        )
    ]
    assert structs == ["CalEvent"]


def test_entry_declares_the_five_rule_backed_transitions() -> None:
    tree = ast.parse(ENTRY_TEXT)
    rules = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(decorator, ast.Attribute) and decorator.attr == "rule"
            for decorator in node.decorator_list
        )
    ]
    assert rules == [
        "load_route_entry",
        "apply_forward",
        "admit_send",
        "epoch_policy",
        "recv_wait",
    ]


def test_registry_pair_bitfield_boundaries_are_the_documented_ones() -> None:
    """Calendar §1.7: rbHi[15:0] routes, [23:16] landCount, [31:24] flags, [63:32] rx."""
    match = re.search(r"RBHI_FIELDS = ac\.BitfieldSpec\((.*?)\n\)", ENTRY_TEXT, re.DOTALL)
    assert match is not None
    pairs = re.findall(r'"(\w+)": \((\d+), (\d+)\)', match.group(1))
    assert {name: (int(msb), int(lsb)) for name, msb, lsb in pairs} == {
        "nodes32_39": (15, 0),
        "landCount": (23, 16),
        "flags": (31, 24),
        "expectedRxBytes": (63, 32),
    }


# -- the block files parse too ---------------------------------------------


def test_every_block_module_imports_cleanly() -> None:
    names = sorted(path.name for path in BLOCKS.glob("*.py") if path.name != "__init__.py")
    assert names == [
        "calreg.py",
        "epoch.py",
        "forward.py",
        "recv_wait.py",
        "route_entry.py",
    ]


def test_blocks_define_their_rule_once() -> None:
    expected = {
        "route_entry.py": {"load_route_entry"},
        "forward.py": {"apply_forward"},
        "calreg.py": {"admit_send"},
        "epoch.py": {"epoch_policy"},
        "recv_wait.py": {"recv_wait"},
    }
    for filename, rules in expected.items():
        tree = ast.parse((BLOCKS / filename).read_text(encoding="utf-8"))
        found = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(decorator, ast.Attribute) and decorator.attr == "rule"
                for decorator in node.decorator_list
            )
        }
        assert found == rules


def test_contract_declares_the_opcode_encoding_once() -> None:
    tree = ast.parse((CONTRACT / "payloads.py").read_text(encoding="utf-8"))
    enums = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "encoding"
            for decorator in node.decorator_list
        )
    ]
    assert enums == ["Opcode"]


# -- the specialization object is importable and consistent ----------------


def test_specialization_binds_only_const_parameters() -> None:
    arguments = dict(top_module.node_lowering_spec.canonical_arguments)
    assert arguments == {"node_index": 0, "node_count": 40, "epoch_tag_bits": 8}
    assert top_module.node_lowering_spec.definition.__name__ == "acir_top"


def test_epoch_capacity_matches_the_c5_baseline() -> None:
    assert top_module.EPOCH_CAPACITY_8 == (1 << 8) - 1
    assert top_module.EPOCH_CAPACITY_8 == 255


def test_node_module_exposes_the_closed_node_facts() -> None:
    from wse_model.acir.model.node import hop_egress, landing_ok, node_pair, pair_is_illegal

    assert callable(node_pair)
    assert callable(hop_egress)
    # Calendar §2.2: 00 absent, 10 pass, 11 land+pass, 01 illegal.
    assert not landing_ok(0b00)
    assert not landing_ok(0b10)
    assert landing_ok(0b11)
    for pair in (0b00, 0b10, 0b11):
        assert not pair_is_illegal(pair)
    assert pair_is_illegal(0b01)
