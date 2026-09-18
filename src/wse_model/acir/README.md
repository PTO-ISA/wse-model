# `wse_model.acir` — the `agentic_circuit` (ACPy 0.5 / ACIR) layer

This package expresses the WSE Calendar semantics as an `agentic_circuit` queue
graph so the same rules can be lowered to ACIR. The **pure-Python semantic core**
in `wse_model.calendar`, `wse_model.noc`, and `wse_model.topology` is the
authority; this layer mirrors it and must never disagree with it (`AGENTS.md`
rule 2).

Pinned frontend: `agentic_circuit` from `/Users/zhoubot/dev/pycircuit` at
revision `0c1008364bf91d9e874f4206334870dd0c238f9c` (contract epoch `0.5`,
distribution version `0.1.0`).

## Layer contract

| Path | Role |
| --- | --- |
| `contract/widths.py` | `ac.param` roots and every fixed width, transcribed from the design sources |
| `contract/payloads.py` | the one `@ac.encoding` enum (`Opcode`) plus the base `@ac.struct` (`Flags`) and the two `ac.BitfieldSpec` register-pair views; every type is declared exactly once |
| `blocks/route_entry.py` | the two-LD `CalendarRouteEntry` load and the `rbLo`/`rbHi` field decode |
| `blocks/forward.py` | the stateless per-hop `{P, L}` decision and the egress set |
| `blocks/calreg.py` | `CalReg[opcode]` residency and the release gate |
| `blocks/recv_wait.py` | the `MTE4_NOC_RECV_WAIT` `expVal` byte accounting |
| `blocks/epoch.py` | `CalendarNextEpoch(opcode)` |
| `model/node.py` | one NoC node's Calendar engine (the node's closed predicates) |
| `model/top.py` | the single `@ac.system` entry plus its `ac.jit(...)` specialization |

The rules are **defined once**, in the entry file `model/top.py`, because this
frontend build only captures a single source file (see the gaps below). The
`blocks/*.py` modules own the pure-Python semantic helpers for each block — the
formulas, the Python oracle of the `{P, L}` rule, the capacity and wraparound
predicates, the `expVal` predicates — and the test asserts the lowered ACIR
against them. `model/top.py`'s rules mirror those helpers 1:1; nothing is
duplicated that the frontend would let them share.

## Rules expressed

1. **`{P, L}` pair encoding.** `pair = L | (P << 1)`; `00` absent, `10` pass,
   `11` land+pass, `01` illegal. The pair is read out of the register pair with
   `pair(n) = ((rbLo >> 2n) & 3) | ((rbHi >> max(0, 2n - 64)) & 3)`. That is the
   literal register-pair boundary: for `n <= 31` the second shift is at least 64
   and its exact-width value is zero, so only `rbLo` contributes; for `n >= 32`
   only `rbHi[15:0]` contributes. `2 * node_index` is a closed constant because
   `node_index` is an `ac.const[int]` — the fixed hardware node — while the
   *source's* runtime `blockId` is what the two scalar `LD` operations index
   (Calendar §4.3).
2. **Illegal `01` faults.** The decode writes `fault` and the CalReg gate clears
   `gate`, so `01` is a reachable error lane, never a silent "absent" default.
3. **Register-pair field boundaries.** `rbHi[15:0]` node 32..39 route bits,
   `rbHi[23:16]` `landCount`, `rbHi[31:24]` `flags` (bit0 `isMember`, bit1
   `isRoot`, bit2 `selfLand`), `rbHi[63:32]` `expectedRxBytes`.
4. **`CalReg[opcode]` residency gate.** A send is admitted only when
   `CalReg[opcode]` is installed. `opcode` 0, `opcode` 7, and any uninstalled
   code fault; the residency image resets to zero, so code `0` is uninstalled by
   construction (Calendar §2.3, §3.9, §4.4.4 rule 4).
5. **Per-`opcode` epoch.** `CalendarNextEpoch(opcode)` starts at 1, is per
   `opcode`, and wraps only when the previous epoch has drained; a wrap attempt
   with traffic in flight sets `epochWrap` and faults (Calendar §1.5, §4.5.2
   contract 7, open item `C-5`).
6. **The seven `expVal` contracts.** Payload bytes only; `[dst, dst + capacity)`
   only; matching `{opcode, epoch}` only; `expVal == 0` completes immediately;
   `expVal > capacity` faults; duplicate segment identities do not double count;
   the source's own bytes do not count.
7. **Completion** is exactly `counted >= expVal` — no notification, no
   semaphore, no `WAIT_SPR` (Calendar §1.2 "完成机制").

## Build commands

```console
# pure Python: parse the real source files, no toolchain
/Users/zhoubot/dev/.venvs/wse-model/bin/python -m pytest tests/acir -q -m unit

# native: lower the real system to ACIR text
export ACIR_OPT=/Users/zhoubot/dev/pycircuit/.pycircuit_out/toolchain/build/bin/acir-opt
export ACIR_QUEUE_CXXGEN=/Users/zhoubot/dev/pycircuit/.pycircuit_out/toolchain/build/bin/acir-queue-cxxgen
/Users/zhoubot/dev/.venvs/wse-model/bin/python -m pytest tests/acir -q -m acir

# the repository's opt-in target (pre-existing; it already refuses without ACIR_OPT)
make acir PYTHON=/Users/zhoubot/dev/.venvs/wse-model/bin/python
```

Lowering the artifact directly:

```console
$ ACIR_OPT=... /Users/zhoubot/dev/.venvs/wse-model/bin/python -c \
    "from wse_model.acir.model.top import node_lowering_spec as s; print(len(s.lower_acir()))"
35648
```

`tests/acir/test_acir_syntax.py` is `pytest.mark.unit` and needs no toolchain.
`tests/acir/test_acir_lower.py` is `pytest.mark.acir` and skips cleanly when
`ACIR_OPT` is unset, so `make check` stays green without the toolchain.

## Gaps against the semantic core

Every gap below is a frontend constraint, not a semantic choice. Each was hit by
running the real files; the diagnostic text is quoted verbatim.

### 1. The source closure accepts only a single file, so the entry is self-contained

`ac.jit(system, workspace=<root>)` builds a *source closure* by walking static
imports. Every realistic layout for this package fails. Observed diagnostics:

* workspace above the package root —
  `ACPY-JIT-006: external import 'collections.abc' is not allowed in wse_model/topology.py`
  (the walk pulls `wse_model/__init__.py`, whose imports reach the semantic core).
* `from wse_model.acir.blocks.calreg import ...` with the workspace at `src/wse_model` —
  `ACPY-JIT-006: external import 'wse_model.acir.contract.payloads' is not allowed in
  acir/blocks/route_entry.py`.
* the same absolute import with the workspace at `src/wse_model/acir`,
  the only root under which `_module_candidates` resolves `blocks/calreg.py` —
  still ends in `ACPY-JIT-006: external import 'wse_model.acir.contract.payloads' is not
  allowed in acir/blocks/route_entry.py`, because `_import_targets` resolves an
  absolute import against `source.parent + module_parts` rather than the package
  root.
* a local import in the package initializer —
  `ACPY-JIT-006: external import 'wse_model.acir.model.top' is not allowed in acir/__init__.py`.

**Consequence.** `model/top.py` declares the one payload struct, the widths it
uses, and the five rules. The blocks keep the pure helpers. `wse_model.acir`
therefore re-exports nothing (`__all__` is empty) to keep the closure importable,
and the entry is imported as `from wse_model.acir.model.top import
node_lowering_spec`.

### 2. `@ac.module` cannot resolve a payload type

The natural composition is a module:

```python
@ac.module
def node_engine(value: CalEvent, node_index: ac.const[int]) -> CalEvent:
    row = load_route_entry(value, node_index)
    return apply_forward(row)
```

Both forms fail:

* pure module with an annotated struct parameter/return, single file and
  multi-file alike —
  `agentic_circuit._queue_frontend.QueueFrontendError: ACPY-QUEUE-002: source payload must be a
  compile-time supported type`;
* rule-backed module —
  `ACPY-MODULE-005: rule module return names must match its arity`, and with the
  documented "return a local from the last rule call" shape,
  `ACPY-QUEUE-002: source payload must be a compile-time supported type`.

`_lower_simple_module_source` resolves the module's return annotation against a
payload map built only from the file being parsed, so any imported or dependent
type is unresolvable there even though `ac.source(CalEvent, ...)` in the system
body resolves fine.

**Consequence.** `model/top.py` chains the rules explicitly. The graph is
identical — five `ac.rule` transitions, one atomic transaction each — and
`model/node.py` keeps the node's closed predicates (`node_pair`, `hop_egress`,
`landing_ok`).

### 3. A `Table` entry type must be declared in the entry file

`ac.table[8, CalEvent]` with `CalEvent` imported from another module fails with
`ACPY-QUEUE-002: source payload must be a compile-time supported type`, because
`table_declaration` resolves the entry type against the same entry-file payload
map as gap 2.

**Consequence.** The layer keeps exactly one payload type and carries the
resident state as compact vectors inside it: `calreg` is an 8 bit residency
bitmap where `bit i` *is* `CalReg[i].installed`, and `ctr` is a 64 bit vector of
eight 8 bit epoch lanes indexed by `opcode * 8`. Semantically that is the same
per-`opcode` state the core keeps in `CalRegBank`/`EpochTracker`; only its
carrier differs.

### 4. Dynamic bit selection is not expressible

The frontend has no dynamic bit-slice or index expression, so two core facts are
modelled by the closest faithful thing:

* **Egress `- ingress` (Calendar §2.2 rule 2).** The egress bitmap is the pass
  bitmap the NoC replicates over; the ingress-port subtraction is a NoC-side
  reduction over that bitmap, because the ingress port is runtime data and its
  `P` bit cannot be selected dynamically. `blocks/forward.py:egress_set` is the
  exact Python mirror, asserted by the test.
* **Epoch lanes.** `ctr` is one 64 bit scalar, so it holds eight 8 bit lanes: the
  Calendar baseline `epoch_tag_bits = 8`. A wider `C-5` reading (9-16 bit) needs
  a wider vector than a 64 bit scalar can hold and is **not** modelled here;
  `top.py` still static-asserts the 8-16 bit range, and the epoch value itself is
  an 8 bit field.

### 5. Scalars are limited to 64 bits, so `routeBits` stays a register pair

`2 x node_count` is 80 bit at the Calendar baseline and cannot be one scalar.
The layer keeps `rbLo`/`rbHi` exactly as the hardware does; the derived `lane`
field is `node_count` bits and holds the decoded pair, not the full 80 bit map.

### 6. A struct body must be annotations only

A class docstring inside an `@ac.struct` body raises
`ACPY-QUEUE-002: struct body requires annotated fields`. In `model/top.py` the
payload documentation is therefore a comment block above the class.

### 7. Helper-function calls are not rules expressions

`ACPY-QUEUE-003: unsupported lambda or rule expression 'RBHI_FIELDS(v.rbHi)'`
(and the same for plain helper calls). A rule body can call only the closed
intrinsic set (`ac.literal`, `ac.zext`, `ac.sext`, `ac.truncate`, `ac.concat`,
`ac.insert`, `ac.matches`, the count/encode primitives, `ac.checked`, `ac.wrap`,
`ac.saturate`, `ac.refine`, the enum helpers) plus operators, so the entry file
spells the `rbHi` field extraction with `truncate`/`>>` rather than calling the
`BitfieldSpec`. The spec itself is still declared and is emitted into the ACIR as
`ac.bitfield @RBHI_FIELDS` with the documented boundaries.

### 8. `**` is not an operator; a literal width is required in decorators

`ACPY-QUEUE-003: unsupported lambda or rule expression '2 ** 5'`, and
`ACPY-TYPE-003: bits width must be in [1, 64]; field Sample.lane has annotation
'ac.bits[2 * 40]'`. The epoch capacity `2 ** epoch_tag_bits - 1` is therefore
materialised as a constant (`EPOCH_CAPACITY_8`) rather than computed in ACIR, and
`@ac.encoding(width=...)` takes a literal.

### 9. The de-duplication set is bounded

The frontend has no unbounded set, so `seen` is a 64 bit one-hot bitmap over
`seq` and the model faults (rather than aliasing) past 64 distinct segment
identities. The core's `SegmentId` set is unbounded; this cap is the modelling
gap, and it is recorded rather than hidden. Calendar §4.5.2 contract 5 (and
`S-6`) require identity de-duplication, which the bitmap does provide for the
admitted window.

### 10. Unbounded-before-the-command arrivals are not modelled

Contract 4 ("legal arrivals that predate the command must not be missed")
belongs to the core's `CoreIngress` ledger. The ACIR layer keys adoption on
`{opcode, epoch}` and has no pre-command buffer, so it is a **partial** mirror of
that contract. The core's `CoreIngress` remains the authority.

## Not a disagreement with the design documents

Two readings in the design sources are open and the layer keeps them open rather
than choosing:

* `Q1` node count: the entry is parameterised by `node_count` and both 40- and
  48-node specializations lower to different ACIR (the folded shift constants
  differ, exactly as the register-pair boundary predicts).
* `C-5` epoch width: static-asserted to the documented 8-16 bit range, with only
  the 8 bit lane modelled (gap 4).

No value the sources leave open is defaulted silently: `node_count`,
`node_index`, and `epoch_tag_bits` are all `ac.const[int]` parameters with
`ac.static_assert` bounds, and an out-of-range binding fails loudly:

```console
ACPY-STATIC-003: src/wse_model/acir/model/top.py:373:5: node_index must be a node of the
target topology; expression='node_index < node_count'; bindings={"node_count":40,"node_index":40}
```
