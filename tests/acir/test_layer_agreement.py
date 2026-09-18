"""The ACIR layer must not disagree with the semantic core.

``AGENTS.md`` rule 2: the pure-Python core is the authority, and the
``agentic_circuit`` layer expresses the *same* rules. This module is the test that
enforces it, by comparing the lowered ACIR's actual constants against the core's
own encoding, rather than against a restatement of them.

The comparison that matters most is the register-pair boundary. ``routeBits`` is
``2 x node_count`` bits spread over two 64 bit registers, so the pair for node
``n`` is::

    pair(n) = ((rbLo >> 2n) & 3) | ((rbHi >> max(0, 2n - 64)) & 3)

with the second term **vanishing** for ``n < 32``. It vanishes by shifting at
least the register width (this frontend defines such a shift as zero), not by
shifting zero — shifting zero would leak ``rbHi[1:0]``, which is *node 32's* pair,
into every node below 32. That is precisely the aliasing the two-register layout
exists to prevent, and it is invisible in the FFN fixture because nodes 32..39
carry all-zero rows there.
"""

from __future__ import annotations

import re

import pytest

from wse_model.acir.model.top import acir_top
from wse_model.calendar.route_bits import BitPair, RouteBits
from wse_model.fixtures import ffn_example, golden_route_bits
from wse_model.topology import CALENDAR_BASELINE, WHITEPAPER_HARDWARE

pytestmark = pytest.mark.acir

REG_BITS = 64
REG_MASK = (1 << REG_BITS) - 1

#: Nodes worth probing: the low register's ends, the boundary, and the high
#: register's start and end.
PROBE_NODES = (0, 1, 5, 31, 32, 33, 39, 47)


def _frontend_available() -> bool:
    """``lower_acir()`` needs the frontend, not the native toolchain."""
    try:
        import agentic_circuit  # noqa: F401
    except ImportError:
        return False
    return True


requires_frontend = pytest.mark.skipif(
    not _frontend_available(),
    reason="the agentic_circuit frontend is not installed (not published on PyPI)",
)


@pytest.fixture(scope="module")
def lowered():
    """Lower each probe node once and return ``(node, node_count) -> text``."""
    if not _frontend_available():
        pytest.skip("the agentic_circuit frontend is not installed")

    import agentic_circuit as ac

    cache: dict[tuple[int, int], str] = {}

    def lower(node: int, node_count: int) -> str:
        key = (node, node_count)
        if key not in cache:
            specialization = ac.jit(
                acir_top, node_index=node, node_count=node_count, epoch_tag_bits=8
            )
            cache[key] = specialization.lower_acir()
        return cache[key]

    return lower


def _pair_shifts(acir_text: str) -> tuple[int, int]:
    """Extract the ``(shift_lo, shift_hi)`` constants of ``load_route_entry``.

    They are the first two ``i64`` constants in that rule: ``2 * node_index`` and
    the rebased ``rbHi`` position.
    """
    body = acir_text.split('name "load_route_entry"', 1)
    assert len(body) == 2, "the lowered ACIR has no load_route_entry rule"
    rule = body[1].split("ac.rule", 1)[0]
    constants = [
        int(match.group(1)) for match in re.finditer(r"ac\.var\.constant (\d+) : i64", rule)
    ]
    assert len(constants) >= 2, f"expected two i64 shift constants, got {constants}"
    return constants[0], constants[1]


def _pair_from_registers(bitmap: RouteBits, node: int, lo_shift: int, hi_shift: int) -> int:
    """Reproduce the lowered expression: ``((rbLo>>lo)|(rbHi>>hi)) & 3``."""
    raw = bitmap.to_int()
    rb_lo = raw & REG_MASK
    rb_hi = raw >> REG_BITS
    return ((rb_lo >> lo_shift) & 0b11) | ((rb_hi >> hi_shift) & 0b11)


def _bitmaps_for(node_count: int) -> tuple[tuple[str, RouteBits], ...]:
    """Fixtures whose row values vary, so a leak would be visible."""
    if node_count == CALENDAR_BASELINE.topology.node_count:
        table = ffn_example().table
        return (
            ("golden", golden_route_bits()),
            ("ffn-key0-row0", table.entry(0, 0).route_bits),
            ("ffn-key1-row0", table.entry(1, 0).route_bits),
            ("ffn-key0-row4", table.entry(0, 4).route_bits),
        )
    # A 48-node map with both registers populated, including node 32 landing.
    return (
        (
            "48-node",
            RouteBits.from_sets(
                node_count,
                pass_nodes={0, 31, 32, 33, 47},
                land_nodes={31, 32, 47},
            ),
        ),
    )


@pytest.mark.parametrize("node", PROBE_NODES)
@requires_frontend
def test_low_register_nodes_do_not_leak_the_high_register(lowered, node: int) -> None:
    """The bug this test exists for: node 32's pair must not reach nodes 0..31."""
    if node >= 40:
        pytest.skip("node 47 belongs to the 48-node reading")
    lo_shift, hi_shift = _pair_shifts(lowered(node, 40))
    assert lo_shift == 2 * node
    if node < 32:
        assert hi_shift >= REG_BITS, (
            f"node {node}: the rebased rbHi shift is {hi_shift}, so rbHi[1:0] "
            "(node 32's pair) leaks into this node's pair; it must be at least "
            f"{REG_BITS} so the term vanishes"
        )
    else:
        assert hi_shift == 2 * node - REG_BITS


@pytest.mark.parametrize("node", PROBE_NODES)
@requires_frontend
def test_pair_derivation_matches_the_core_for_every_fixture(lowered, node: int) -> None:
    """The lowered constants must reproduce the core's own pair for real rows."""
    node_count = 48 if node >= 40 else 40
    lo_shift, hi_shift = _pair_shifts(lowered(node, node_count))
    for label, bitmap in _bitmaps_for(node_count):
        expected = bitmap.pair(node)
        derived = _pair_from_registers(bitmap, node, lo_shift, hi_shift)
        assert derived == int(expected), (
            f"{label} node {node}: the lowered register arithmetic yields pair "
            f"{derived:02b} but the core says {int(expected):02b}"
        )


@pytest.mark.parametrize("node", [0, 31, 32, 39])
@requires_frontend
def test_pass_and_land_agree_with_the_bit_pair_semantics(lowered, node: int) -> None:
    """``P`` is bit 1 and ``L`` is bit 0, in both layers."""
    lo_shift, hi_shift = _pair_shifts(lowered(node, 40))
    for label, bitmap in _bitmaps_for(40):
        pair = BitPair(_pair_from_registers(bitmap, node, lo_shift, hi_shift))
        assert pair.passes is bool(int(pair) & 0b10), label
        assert pair.lands is bool(int(pair) & 0b01), label
        assert pair.passes == (pair in (BitPair.PASS, BitPair.LAND))
        assert pair.lands == (pair in (BitPair.ILLEGAL, BitPair.LAND))


@requires_frontend
def test_the_illegal_pair_is_reachable_in_the_lowered_rule(lowered) -> None:
    """``01`` must fault rather than be repaired, in both layers."""
    text = lowered(0, 40)
    body = text.split('name "load_route_entry"', 1)[1].split("ac.rule", 1)[0]
    assert "PAIR_ILLEGAL" in body or "constant 1 : i2" in body
    assert BitPair(0b01) is BitPair.ILLEGAL
    assert BitPair.ILLEGAL.lands and not BitPair.ILLEGAL.passes


@requires_frontend
def test_the_five_rules_are_the_core_steps(lowered) -> None:
    """One rule per documented Calendar step, named the same in both layers."""
    from wse_model.core import calendar_step_pipes

    text = lowered(0, 40)
    for rule in (
        "load_route_entry",
        "apply_forward",
        "admit_send",
        "epoch_policy",
        "recv_wait",
    ):
        assert f'name "{rule}"' in text, rule
    # The core's own step list is the reference for what those rules cover.
    steps = {step.step for step in calendar_step_pipes()}
    assert {"Step3 MTE4 RECV", "Step4 MTE3 SEND", "Step5 Join"} <= steps


@requires_frontend
def test_the_48_node_reading_is_a_different_model(lowered) -> None:
    """Open item Q1: the two readings differ in their bound, not their boundary.

    The register-pair boundary is a property of the 16 B entry, so node 32's
    shifts are 64 and 0 under either reading. What differs is which node indices
    are legal at all: node 47 lowers only under the 48-node reading, and the
    40-node reading must refuse it.
    """
    lo32_40, hi32_40 = _pair_shifts(lowered(32, 40))
    lo32_48, hi32_48 = _pair_shifts(lowered(32, 48))
    assert (lo32_40, hi32_40) == (64, 0)
    assert (lo32_48, hi32_48) == (64, 0)

    lo47, hi47 = _pair_shifts(lowered(47, 48))
    assert (lo47, hi47) == (94, 30)

    import agentic_circuit as ac
    from agentic_circuit._diagnostics import AgenticCircuitError

    with pytest.raises(AgenticCircuitError):
        ac.jit(acir_top, node_index=47, node_count=40, epoch_tag_bits=8).lower_acir()
    assert WHITEPAPER_HARDWARE.topology.node_count == 48
    assert CALENDAR_BASELINE.topology.node_count == 40


@requires_frontend
def test_an_out_of_range_node_fails_closed() -> None:
    """Both readings bound node_index, so a bad binding cannot produce a model."""
    import agentic_circuit as ac

    with pytest.raises(Exception) as excinfo:
        ac.jit(acir_top, node_index=40, node_count=40, epoch_tag_bits=8).lower_acir()
    assert "node_index" in str(excinfo.value)
