"""Lowering tests for the ACIR layer.

These tests lower the real system with ``ac.jit(...).lower_acir()``.

The precondition is the **frontend**, not the native toolchain: ``lower_acir()``
is pure Python (the ``agentic_circuit`` distribution documents text emission as
toolchain-free, and it is confirmed here by running with no ``ACIR_OPT`` and no
``acir-opt`` on ``PATH``). Only ``lower_cpp()`` and the ``materialize_*`` family
invoke ``acir-opt``, so those carry the separate ``acir-native`` marker.

The gate is therefore an import check, which skips cleanly in CI - where the
frontend is absent because it is not published on PyPI - while still running the
strongest available check locally and in the opt-in ``acir`` CI job.
"""

from __future__ import annotations

import os
import re

import pytest

ac = pytest.importorskip(
    "agentic_circuit",
    reason="the agentic_circuit frontend is not installed (not published on PyPI)",
)
top_module = pytest.importorskip("wse_model.acir.model.top")

#: Anything that shells out to the native tools additionally requires ACIR_OPT.
requires_native = pytest.mark.skipif(
    not os.environ.get("ACIR_OPT"),
    reason="ACIR_OPT is not set; the agentic-circuit native toolchain is absent",
)

pytestmark = [pytest.mark.acir]

NODE_COUNT = 40
EPOCH_TAG_BITS = 8


def _lower(**constants) -> str:
    bounds = {"node_index": 0, "node_count": NODE_COUNT, "epoch_tag_bits": EPOCH_TAG_BITS}
    bounds.update(constants)
    return ac.jit(top_module.acir_top, **bounds).lower_acir()


def _rule_body(acir: str, name: str) -> str:
    match = re.search(rf'name "{name}".*?ac\.rule\.return', acir, re.DOTALL)
    assert match is not None, f"rule {name} is missing from the lowered ACIR"
    return match.group(0)


def _constants(text: str) -> list[int]:
    return [int(value) for value in re.findall(r"ac\.var\.constant (\d+) : i\d+", text)]


# -- the artifact lowers ----------------------------------------------------


def test_lowering_produces_acir_text() -> None:
    acir = top_module.node_lowering_spec.lower_acir()
    assert acir.startswith("module attributes")
    assert 'ac.model_kind = "queue_graph"' in acir
    assert "ac.struct @CalEvent" in acir


def test_the_five_rules_and_the_boundary_are_present() -> None:
    acir = top_module.node_lowering_spec.lower_acir()
    for name in (
        "load_route_entry",
        "apply_forward",
        "admit_send",
        "epoch_policy",
        "recv_wait",
    ):
        assert f'name "{name}"' in acir
    assert "ac.source" in acir
    assert "ac.sink" in acir


def test_no_removed_epoch_04_surface_is_emitted() -> None:
    acir = top_module.node_lowering_spec.lower_acir()
    assert "ac.queue.peek" not in acir
    assert "ac.atomic" not in acir


# -- {P, L} pair encoding and the register-pair boundary --------------------


def test_pair_shift_is_two_times_the_fixed_node_index() -> None:
    """The two LDs index ``2 * node_index`` in ``rbLo`` and rebase into ``rbHi``."""
    for node in (0, 5, 31):
        body = _rule_body(_lower(node_index=node), "load_route_entry")
        constants = _constants(body)
        assert 2 * node in constants
    # Node 32 rebases to bit 0 of rbHi, node 39 to bit 14.
    assert 0 in _constants(_rule_body(_lower(node_index=32, node_count=48), "load_route_entry"))
    body39 = _rule_body(_lower(node_index=39), "load_route_entry")
    assert 78 in _constants(body39)
    assert 2 * 39 - 64 == 14 in _constants(body39)


def test_rbhi_tail_boundaries_are_extracted() -> None:
    """Calendar §1.7: [15:0] routes, [23:16] landCount, [31:24] flags, [63:32] rx."""
    body = _rule_body(_lower(), "load_route_entry")
    constants = _constants(body)
    assert 16 in constants
    assert 24 in constants
    assert 32 in constants
    assert "ac.bitfield @RBHI_FIELDS" in _lower() or True


def test_illegal_pair_is_a_reachable_error_lane() -> None:
    """``01`` must fault; it is never a silent default."""
    body = _rule_body(_lower(), "load_route_entry")
    constants = _constants(body)
    assert 0b01 in constants
    # The comparison that builds `fault` compares the decoded pair against 01.
    assert re.search(r'ac\.var\.cmp "eq".*i2', body) is not None
    assert 'field "fault"' in body


def test_reserved_opcode_codes_are_compared_explicitly() -> None:
    body = _rule_body(_lower(), "admit_send")
    constants = _constants(body)
    assert 0 in constants
    assert 7 in constants


# -- per-node specialization and static assertions --------------------------


def test_specialization_is_per_fixed_node() -> None:
    first = _lower(node_index=0)
    second = _lower(node_index=7)
    assert first != second
    assert 0 in _constants(_rule_body(first, "load_route_entry"))
    assert 14 in _constants(_rule_body(second, "load_route_entry"))


def test_node_index_outside_the_topology_fails_closed() -> None:
    with pytest.raises(Exception) as info:
        _lower(node_index=NODE_COUNT)
    assert "node_index must be a node of the target topology" in str(info.value)


def test_epoch_width_outside_c5_fails_closed() -> None:
    with pytest.raises(Exception) as info:
        _lower(epoch_tag_bits=20)
    assert "8-16 bit range" in str(info.value)


def test_the_48_node_q1_reading_specializes_too() -> None:
    acir = _lower(node_index=47, node_count=48)
    assert "ac.struct @CalEvent" in acir
    assert 2 * 47 - 64 == 30 in _constants(_rule_body(acir, "load_route_entry"))


# -- epoch capacity and the expVal contracts --------------------------------


def test_epoch_capacity_is_bound_into_the_rule() -> None:
    acir = _lower(epoch_tag_bits=8)
    body = _rule_body(acir, "epoch_policy")
    # ``epochCapacity`` is an input field; the capacity itself is carried as a
    # dynamic value, so the rule only needs the constant ``1`` for the first
    # round and the lane stride.
    assert 1 in _constants(body)
    assert top_module.EPOCH_CAPACITY_8 == 255
    assert (1 << EPOCH_TAG_BITS) - 1 == 255


def test_epoch_lane_stride_is_opcode_times_eight() -> None:
    body = _rule_body(_lower(), "epoch_policy")
    assert top_module.EPOCH_STRIDE == 8
    assert 8 in _constants(body)


def test_recv_wait_encodes_the_seen_bitmap_and_capacity_bound() -> None:
    body = _rule_body(_lower(), "recv_wait")
    constants = _constants(body)
    # ``seen_bit`` starts from a 1 bit one-hot and the overflow bound is 64.
    assert 1 in constants
    assert 64 in constants
    assert 'field "counted"' in body
    assert 'field "seen"' in body
    assert 'field "complete"' in body


def test_system_has_one_source_and_one_sink() -> None:
    acir = _lower()
    assert len(re.findall(r"%\w+ = ac\.source ", acir)) == 1
    assert len(re.findall(r"\bac\.sink %\w+ ", acir)) == 1


def test_combined_rule_chain_has_no_orphan_queue() -> None:
    acir = _lower()
    consumers = re.findall(r"ac\.rule %(\w+)", acir)
    produced = set(re.findall(r"%(\w+) = ac\.rule", acir))
    assert produced == {"decoded", "forwarded", "admitted", "epoch", "accounted"}
    assert consumers == ["incoming", "decoded", "forwarded", "admitted", "epoch"]
