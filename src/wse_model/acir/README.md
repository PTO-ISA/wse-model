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

## Frontend constraints and modelling choices

Every entry below was re-verified against the frontend at the pinned revision,
either by parsing the real files in this package or by a minimal reproducer. Each
one is labelled for what it actually is:

* **constraint** — reproduced: the frontend rejects the construct.
* **choice** — the frontend would allow it; this layer does something else, and
  the reason is stated rather than implied.
* **refuted** — asserted earlier in this document and found **not** to reproduce;
  the corrected statement is given instead. Three entries are in this class, and
  they are kept visible rather than deleted so nobody re-derives them.

Two constraints are filed upstream:
[PTO-ISA/pyCircuit#158](https://github.com/PTO-ISA/pyCircuit/issues/158) (the
source closure) and
[PTO-ISA/pyCircuit#159](https://github.com/PTO-ISA/pyCircuit/issues/159) (two
misleading diagnostics and a stale marker inventory).

### 1. constraint — the source closure accepts only three external modules, and needs the package's parent as workspace

`ac.jit(system, workspace=<root>)` walks static imports and rejects anything
outside `_ALLOWED_EXTERNAL_MODULES = {"__future__", "agentic_circuit", "enum"}`
(`_source_closure.py:42`). A captured module importing `collections.abc`,
`typing`, `math`, `dataclasses`, or `pathlib` therefore fails:

```text
SourceClosureError: ACPY-JIT-006: external import 'collections.abc' is not allowed in pkg/types.py
```

**Reproduced minimally**: a two-module package whose `types.py` contains only
`from collections.abc import Iterable` plus one `@ac.struct`. Removing that one
import makes the same capture succeed (1258 B of ACIR), so the import is the sole
trigger. The other stdlib modules named above fail the same way.

The second half of the same behaviour: `workspace` must be the directory
**containing** the root package. Pointing it at the package root instead makes an
absolute self-import fail, with a message that sends the reader in the wrong
direction:

```text
SourceClosureError: ACPY-JIT-006: external import 'pkg.types' is not allowed in top.py
```

**Consequence.** `model/top.py` declares the one payload struct, the widths it
uses, and the five rules; the blocks keep the pure helpers. `wse_model.acir`
re-exports nothing (`__all__` is empty) so the closure never walks its package
initializer, and the entry is imported as
`from wse_model.acir.model.top import node_lowering_spec`.

### 2. constraint — `@ac.module` cannot resolve an imported payload type

```python
@ac.module
def node_engine(value: CalEvent, node_index: ac.const[int]) -> CalEvent:
    row = load_route_entry(value, node_index)
    return apply_forward(row)
```

Parsed with `entry_kind="module"` and `CalEvent` imported from another file:

```text
QueueFrontendError: ACPY-QUEUE-002: source payload must be a compile-time supported type
```

`_lower_simple_module_source` resolves the module's parameter and return
annotations against a payload map built only from the file being parsed, so any
imported or dependent type is unresolvable there even though
`ac.source(CalEvent, ...)` in an `@ac.system` body resolves the same name fine.

**Consequence.** `model/top.py` chains the rules explicitly. The graph is
identical — five `ac.rule` transitions, one atomic transaction each — and
`model/node.py` keeps the node's closed predicates (`node_pair`, `hop_egress`,
`landing_ok`).

### 3. constraint — a `Table` entry type must be declared in the same file

`ac.table[4, S]` where `S` is imported fails the same way, for the same reason
(`table_declaration` uses the entry-file payload map):

```text
QueueFrontendError: ACPY-QUEUE-002: source payload must be a compile-time supported type
```

**Consequence.** The layer keeps exactly one payload type and carries the resident
state as compact vectors inside it: `calreg` is an 8 bit residency bitmap where
`bit i` *is* `CalReg[i].installed`, and `ctr` is a 64 bit vector of eight 8 bit
epoch lanes indexed by `opcode * 8`. Semantically that is the same per-`opcode`
state the core keeps in `CalRegBank`/`EpochTracker`; only the carrier differs.

### 4. refuted — "dynamic bit selection is not expressible"; the egress `- ingress` term is a modelling choice

Calendar §2.2 rule 2 is `out = { neighbour j : P_j = 1 } - ingress`. The ingress
port is runtime data, so applying it means selecting a bit at a dynamic position.

**This was previously recorded here as a frontend limitation, and that was
wrong.** A dynamic shift is accepted:

```python
@ac.rule
def pick(v):
    return v.with_fields(idx=ac.truncate(v.lane >> v.idx, ac.u8))
```

parses cleanly, so `ac.truncate(lane >> dynamic_ingress, ac.u1)` — the term the
rule actually needs — is expressible.

So the current treatment is a **modelling choice, not a constraint**: the
flit's `lane` carries the pass bitmap, `apply_forward` republishes it as the
egress bitmap, and `blocks/forward.py:egress_set` is the exact Python oracle the
test asserts against — but the ingress subtraction is left to the NoC. Implementing
it in ACIR would make the node model self-contained and is the natural next
increment; it is not blocked by the frontend.

### 5. constraint — scalars are limited to 64 bits, so `routeBits` stays a register pair

`ac.bits[N]` rejects `N > 64` (`ACPY-TYPE-003`) and `ac.uNN` stops at `ac.u64`.
`2 x node_count` is 80 bit at the Calendar baseline, so it cannot be one scalar.
The layer keeps `rbLo`/`rbHi` exactly as the hardware does; the derived `lane`
field is `node_count` bits and holds the decoded pair, not the full 80 bit map.

A second consequence: `ctr` is one 64 bit scalar holding eight 8 bit epoch lanes,
which covers the Calendar baseline `epoch_tag_bits = 8`. A wider `C-5` reading
(9-16 bit) would need a wider vector than a 64 bit scalar provides and is **not**
modelled; `top.py` still static-asserts the 8-16 bit range, and the epoch value
itself is an 8 bit field.

### 6. constraint — a struct body must be annotations only

A class docstring inside an `@ac.struct` body raises

```text
QueueFrontendError: ACPY-QUEUE-002: struct body requires annotated fields
```

although the annotated fields are present. In `model/top.py` the payload
documentation is therefore a comment block above the class. Filed upstream as
part of [#159](https://github.com/PTO-ISA/pyCircuit/issues/159), because the
diagnostic names the wrong problem.

### 7. refuted — helper-function calls in rule bodies

Previously recorded here as `ACPY-QUEUE-003: unsupported lambda or rule
expression`. **Not reproduced.** A rule body calling a user-defined helper is
accepted, and so is calling an `ac.BitfieldSpec` instance:

```python
FIELDS = ac.BitfieldSpec(width=16, fields={"lo": (7, 0), "hi": (15, 8)})


@ac.rule
def keep(v):
    return v.with_fields(word=FIELDS(v.word).lo)
```

parses cleanly. `model/top.py` still spells the `rbHi` extraction with
`truncate`/`>>` — that is now simply a style choice, kept because the explicit
form mirrors the register boundaries one for one. `RBHI_FIELDS` is declared and
emitted as `ac.bitfield @RBHI_FIELDS` with the documented boundaries.

### 8. refuted — `**` and computed widths

Previously recorded here as `2 ** 5` being unsupported and decorator widths
needing literals. **Neither reproduces**: `ac.truncate(2 ** 5, ac.u8)` inside a
rule and `@ac.encoding(width=2 * 2)` both parse.

The rejection that *does* exist is the width bound, and it is correct:
`ac.bits[2 * 40]` fails with

```text
ACPY-TYPE-003: bits width must be in [1, 64]; field S.lane has annotation 'ac.bits[2 * 40]'
```

because the product is 80. `ac.bits[2 * SMALL]` (16) and `ac.bits[K + K]` are
accepted, so arithmetic inside `bits[...]` works. `EPOCH_CAPACITY_8` is a named
constant for readability, not because the expression is rejected.

### 9. choice — the de-duplication set is bounded

The layer's `seen` is a 64 bit one-hot bitmap over `seq` and faults rather than
aliasing past 64 distinct segment identities. The core's `SegmentId` set is
unbounded; this cap is a modelling gap, recorded rather than hidden. Calendar
§4.5.2 contract 5 (and `S-6`) require identity de-duplication, which the bitmap
does provide for the admitted window.

### 10. choice — pre-command arrivals are not modelled

Contract 4 ("legal arrivals that predate the command must not be missed") belongs
to the core's `CoreIngress` ledger. The ACIR layer keys adoption on
`{opcode, epoch}` and has no pre-command buffer, so it is a **partial** mirror of
that contract. The core's `CoreIngress` remains the authority.

### Reproducing these verdicts

The constraints were re-checked with the frontend's own parser, which needs no
native toolchain:

```bash
python - <<'PY'
from agentic_circuit._queue_frontend import parse_queue_program

def case(name, body):
    try:
        parse_queue_program("import agentic_circuit as ac\n\n" + body, "top")
        print("ACCEPTED  ", name)
    except Exception as exc:
        print(f"{type(exc).__name__}: {str(exc).strip().splitlines()[0]}   <-- {name}")
PY
```

and the closure behaviour with `ac.jit(system, workspace=...)` over a two-module
package. `tests/acir/test_layer_agreement.py` keeps the cross-layer arithmetic
honest; the verdicts above are documentation, not tests, because the frontend's
behaviour is outside this repository's control.

## Not a disagreement with the design documents

Two readings in the design sources are open and the layer keeps them open rather
than choosing:

* `Q1` node count: the entry is parameterised by `node_count` and both 40- and
  48-node specializations lower to different ACIR (the folded shift constants
  differ, exactly as the register-pair boundary predicts).
* `C-5` epoch width: static-asserted to the documented 8-16 bit range, with only
  the 8 bit lane modelled (constraint 5).

No value the sources leave open is defaulted silently: `node_count`,
`node_index`, and `epoch_tag_bits` are all `ac.const[int]` parameters with
`ac.static_assert` bounds, and an out-of-range binding fails loudly:

```console
ACPY-STATIC-003: src/wse_model/acir/model/top.py:373:5: node_index must be a node of the
target topology; expression='node_index < node_count'; bindings={"node_count":40,"node_index":40}
```
