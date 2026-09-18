"""The stateless per-hop ``{P, L}`` decision and the egress set.

Calendar §2.2 gives the NoC exactly two passive rules::

    1. if L_self == 1:  commit the payload locally (and continue forwarding)
    2. out = { neighbour j : P_j == 1 } - ingress
       replicate one flit per egress port

There is no routing table, no lookup path, and no state. Because rule 2 copies
to *all* physical neighbours with ``P = 1``, what must be a tree is the subgraph
**induced** by ``{P_i = 1}``; the design therefore treats the ``{P, L}`` pair as
the whole hop decision.

Two facts are worth stating about what this layer can and cannot express.

* The pair, ``P``/``L``, and the egress bitmap are derived facts of the *fixed*
  node's own two bits, so the frontend folds them to closed constants.
* The ``- ingress`` term of rule 2 needs the ingress port's ``P`` bit, and the
  ingress port is runtime data. Dynamic bit selection is not expressible in this
  frontend (see ``README.md``), so ``egress`` is the pass bitmap the NoC
  replicates over and the ingress subtraction happens in the NoC's reduction.

``egress_set`` below is the exact Python mirror of the hardware rule, exposed so
the test can assert the ACIR-derived bitmap against it without re-deriving
anything.
"""

from __future__ import annotations

from collections.abc import Iterable

import agentic_circuit as ac

from wse_model.acir.contract.payloads import PAIR_ABSENT, PAIR_ILLEGAL

__all__ = [
    "apply_forward",
    "egress_set",
    "is_illegal",
    "is_land",
    "is_pass",
]


def is_pass(pair: int) -> bool:
    """``P``: the node forwards the flit (bit 1 of ``L | (P << 1)``)."""
    return bool(pair & 0b10)


def is_land(pair: int) -> bool:
    """``L``: the node commits the payload to its receive range."""
    return bool(pair & 0b01)


def is_illegal(pair: int) -> bool:
    """The illegal pair ``01``: ``L = 1`` with ``P = 0`` (Calendar §2.2)."""
    return pair == PAIR_ILLEGAL


def egress_set(
    *,
    neighbours: Iterable[int],
    node_pairs: dict[int, int],
    ingress: int | None,
) -> tuple[int, ...]:
    """``out = { neighbour j : P_j == 1 } - ingress`` (Calendar §2.2 rule 2).

    ``node_pairs`` is the decoded ``{P, L}`` value of every node the topology
    reaches, so this is the induced-subgraph walk the design documents describe,
    not a planned path.
    """
    return tuple(
        peer
        for peer in sorted(neighbours)
        if peer != ingress and is_pass(node_pairs.get(peer, PAIR_ABSENT))
    )


@ac.rule
def apply_forward(v):
    """Publish the stateless hop decision.

    ``passes``/``lands`` are the two Calendar rules for this node's own bits;
    ``egress`` is the node bitmap of the continuing flit, which the NoC
    materialises per physical neighbour. The illegal ``01`` pair stays flagged
    rather than silently defaulting to "absent".
    """
    return v.with_fields(
        egress=v.lane,
        fault=v.fault or v.pair == ac.literal(PAIR_ILLEGAL, ac.u2),
    )
