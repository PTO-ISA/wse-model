"""One NoC node's Calendar engine.

A NoC node is *fixed hardware*: the node index is a compile-time constant of the
specialization, never a runtime operand. This module therefore exposes the node's
closed, testable facts — the decoded ``{P, L}`` pair of the fixed node, the
egress bitmap, and the hop predicate — and lets
:mod:`wse_model.acir.model.top` place the rule-backed engine.

**Frontend gap (recorded, not worked around).** The natural expression of this
composition is an ``@ac.module``::

    @ac.module
    def node_engine(value: CalEvent, node_index: ac.const[int]) -> CalEvent:
        row = load_route_entry(value, node_index)
        return apply_forward(row)

This build cannot lower it. Even a single-file, single-struct pure module fails
with::

    agentic_circuit._queue_frontend.QueueFrontendError:
        ACPY-QUEUE-002: source payload must be a compile-time supported type

and the rule-backed module path fails with ``ACPY-MODULE-005: rule module return
names must match its arity``. ``top.py`` therefore chains the rules explicitly,
which is the same graph with the same atomic-transition boundaries. See the
"Gaps against the semantic core" section of ``README.md``.

``node_pair`` and ``landing_ok`` are the closest faithful thing: pure predicates
that name this node's decode-then-decide transition, so a test can assert the
lowered ACIR against them directly.
"""

from __future__ import annotations

import agentic_circuit as ac

from wse_model.acir.blocks.forward import is_land, is_pass
from wse_model.acir.blocks.route_entry import pair_of
from wse_model.acir.model.top import CalEvent

__all__ = [
    "hop_egress",
    "landing_ok",
    "node_pair",
    "pair_is_illegal",
]


def node_pair(event: CalEvent, node_index: int) -> ac.u2:
    """The pair of the fixed node, expressed exactly as the route-entry block is."""
    return pair_of(event, node_index)


def hop_egress(event: CalEvent) -> ac.bits[40]:
    """``out = { neighbour j : P_j == 1 } - ingress`` (Calendar §2.2 rule 2).

    The pass bitmap is what the NoC replicates over; the ingress-port subtraction
    is a NoC-side reduction over that bitmap, because the ingress port is runtime
    data and this frontend cannot express dynamic bit selection.
    """
    return event.lane


def landing_ok(pair: int) -> bool:
    """Whether this hop both forwards and commits: the ``11`` multicast fork.

    Exposed so callers and tests can name the Calendar §2.2 rule without
    duplicating the bit arithmetic.
    """
    return is_pass(pair) and is_land(pair)


def pair_is_illegal(pair: int) -> bool:
    """The illegal pair ``01``, which must fault rather than default to absent."""
    return is_land(pair) and not is_pass(pair)
