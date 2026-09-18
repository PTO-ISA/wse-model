# Calendar and NoC

This is the deep dive into the part of the model that exists in full: the Calendar
encoding, its structural validation, and the NoC that consumes it. Every claim
below names the symbol that implements it, and every rule names the design section
it comes from. The requirements that make each rule testable are collected in
[Calendar closure requirements](../requirements/calendar-closure.md).

Design sources: Calendar [§1.4](../design/wse-calendar-scheme.md),
[§1.5](../design/wse-calendar-scheme.md), [§1.8](../design/wse-calendar-scheme.md),
[§2](../design/wse-calendar-scheme.md), [§3.9](../design/wse-calendar-scheme.md),
[§4.4–§4.5](../design/wse-calendar-scheme.md); whitepaper
[§5](../design/wse-system-architecture-whitepaper.md),
[§11](../design/wse-system-architecture-whitepaper.md),
[§16](../design/wse-system-architecture-whitepaper.md).

## 1. `routeBits`: bit order and the golden vector

Every NoC node owns a two-bit `{P, L}` pair, so the bitmap is `2 × node_count`
bits — 80 bit = 10 B at the 40-node Calendar baseline, 96 bit = 12 B at 48 nodes
(open item `Q1`). The bit order is fixed by Calendar §2.2 and implemented in
[`wse_model.calendar.route_bits`](../../src/wse_model/calendar/route_bits.py):

```text
routeBits[2i + 1] = P_i          # pass: the node forwards the flit
routeBits[2i]     = L_i          # land: the node commits the payload
bit b lives in byte b // 8 at bit position b % 8   # LSB first
```

`RouteBits.node_count` and `RouteBits.width_bits` / `width_bytes` expose the
widths, and `RouteBits.from_bytes` requires exactly `(2 * node_count + 7) // 8`
bytes. Decoding is deliberately unchecked: `from_bytes` preserves an illegal `01`
pair so that `RouteBits.illegal_nodes()` and
`validate_route_bits` can reject it rather than have the codec silently repair bad
input. The checked constructor is `RouteBits.from_sets`, which raises
`IllegalBitPairError` for any node in `land_nodes` that is not in `pass_nodes`.

### `BitPair`

`BitPair` is an `IntEnum` whose integer value is exactly the on-wire pair,
`L | (P << 1)`, so a byte's low bit is `L_i` and its high bit is `P_i`:

| Member | Value | `passes` | `lands` | Meaning |
| --- | --- | --- | --- | --- |
| `BitPair.ABSENT` | `0b00` | no | no | unrelated to this flit |
| `BitPair.PASS` | `0b10` | yes | no | forward, do not land |
| `BitPair.LAND` | `0b11` | yes | yes | land and forward (multicast fork or reduction point) |
| `BitPair.ILLEGAL` | `0b01` | no | yes | `L=1` with `P=0`; the compiler must reject it and the hardware must fault |

### The §2.2.1 golden vector

`wse_model.fixtures` transcribes the consistency anchor every tool must agree on
byte for byte:

```text
source = N00
pass   = {N00, N01, N02, N03, N04, N10, N18, N19}
land   = {N04, N19}
routeBits[2i+1] = P_i , routeBits[2i] = L_i
  -> 10 B = AA 03 20 00 E0 00 00 00 00 00
```

`GOLDEN_PASS_NODES`, `GOLDEN_LAND_NODES`, `GOLDEN_ROUTE_BITS`, and
`golden_route_bits()` hold these values. The byte layout is a direct consequence
of the bit order: byte 0 is `0xAA` (nodes 0–3 all pass-only, `10` each), byte 1 is
`0x03` (node 4 is `11`, nodes 5–7 absent), byte 2 is `0x20` (node 10 passes), and
byte 4 is `0xE0` (node 18 passes, node 19 lands and passes).

### The FFN rows

`fixtures.ffn_example` reconstructs the two documented FFN identities and asserts
the two published rows:

| `keyId` | Identity | Source N00 row | `landCount` | `expectedRxBytes` |
| --- | --- | --- | --- | --- |
| 0 | `AllGather`, `ROW(my_row)` | `FE FF 00 00 00 00 00 00 00 00` | 7 | `8 × 192 × 7 = 10752` |
| 1 | `AllGather`, `COL(my_col)` | `02 00 03 00 03 00 03 00 00 00` | 3 | `8 × 1536 × 3 = 36864` |

The FFN uses the first four rows of the 5×8 mesh (32 cells); nodes 32–39 carry an
all-zero row for both identities. These two rows are a **fixture, not a routing
algorithm**: Calendar §2.7 is explicit that software must not rewrite the NoC's
routing algorithm, so production bitmaps arrive from the NoC provider or from a
table and are validated here, never generated.

## 2. The 16 B `CalendarRouteEntry`

Calendar §2.6 fixes the `.rodata` entry at exactly 16 B so that two ordinary
64 bit scalar loads fill one GPR pair. The layout is defined in
[`wse_model.calendar.entry`](../../src/wse_model/calendar/entry.py):

```text
struct alignas(16) CalendarRouteEntry {   // 16 B
    uint8_t  routeBits[10];   // 40 x {P,L}: bit(2i+1)=P_i, bit(2i)=L_i
    uint8_t  landCount;       // popcount(L), for cross-checking
    uint8_t  flags;           // bit0 isMember, bit1 isRoot, bit2 selfLand
    uint32_t expectedRxBytes; // this core's expVal as a destination
};
```

`ENTRY_SIZE_BYTES` is 16 and `ENTRY_LAYOUT_OVERHEAD_BYTES` is 6
(`landCount` + `flags` + `expectedRxBytes`). `ROUTE_BITS_NODE_CAPACITY` is
`(16 - 6) * 4 = 40`: the largest node count whose bitmap plus the fixed tail still
fits 16 B. `entry_layout_size_bytes(node_count)` computes the requirement.

### `rbLo` / `rbHi` field boundaries

The register-pair view is `CalendarRouteRegs`, and it mirrors Calendar §1.7 field for
field rather than re-deriving the layout:

```text
rbLo = entry bytes 0..7   -> nodes 00..31          (32 pairs)
rbHi = entry bytes 8..15  -> [15:0]  nodes 32..39  (8 pairs)
                              [23:16] landCount
                              [31:24] flags
                              [63:32] expectedRxBytes

routeBits80 = rbLo[63:0] ++ rbHi[15:0]
```

`CalendarRouteRegs.route_bits_value` reassembles exactly that value;
`CalendarRouteRegs.land_count`, `.flags`, and `.expected_rx_bytes` read the three tail
fields. Calendar §4.4.4 requires the send instruction to take only `rbHi[15:0]` as
routing bits and to ignore the high 48 bit without checking them (`HW-4`), which
is what lets `landCount`, `flags`, and `expectedRxBytes` ride along at zero extra
load cost. `CalendarRouteEntry.from_regs` decodes the tail deliberately, because
those bits *are* the tail; it is the hardware that must ignore them when sending.

`RouteEntryFlags` defines the three flag bits: `IS_MEMBER` (`1 << 0`), `IS_ROOT`
(`1 << 1`), and `SELF_LAND` (`1 << 2`). `CalendarRouteEntry.declared_land_count`
exists only so that a mismatching `popcount(L)` raises `LandSetError`;
`expected_rx_bytes` is range-checked against `uint32`.

### Why 48 nodes cannot be emitted

At 48 nodes, `routeBits` alone is 12 B, so `entry_layout_size_bytes(48) == 18`.
`CalendarRouteEntry.to_bytes` and `CalendarRouteTable.to_bytes` raise
`WseModelError` (naming open item `Q1`) rather than widen the entry or round it,
and `validate_entry_layout` reports `V-ENTRY-SIZE`. This is a structural
consequence of `Q1`, not a missing feature.

## 3. The induced-subgraph-is-a-tree rule

Calendar §2.2 gives the NoC exactly two rules:

```text
(1) if L_self == 1:  land the payload locally (and continue)
(2) out = { neighbour j : P_j == 1 } - ingress
    replicate one flit per egress port
```

Rule (2) copies to **all** physical neighbours with `P=1`. The set of edges that
actually carries traffic is therefore not the path the algorithm intended: it is
the subgraph **induced** by `{P_i = 1}`, in which any two adjacent members share a
live link. `MeshTopology.induced_edges` implements exactly that — it returns every
physical link whose *both* endpoints are in the node set.

The consequence is the rule's sharp edge. A 2×2 block of nodes all set to `P=1`
necessarily contains a cycle, because all four links between them are induced; a
flit entering it replicates forever and lands repeatedly.
`wse_model.calendar.validate.check_induced_tree` analyses the subgraph and
`TreeAnalysis.is_tree` requires all three of:

- `is_connected` — one component, so every land node is reachable;
- `is_acyclic` — `|E| == |V| - |components|`, i.e. a tree (or forest);
- `contains_source` — the source is on its own path.

`validate_route_bits` raises `V-TREE-CONNECTED` or `V-TREE-ACYCLIC` accordingly.
A node with `P_self = 0` is reported separately as `V-PSELF`, and
`simulate_multicast` refuses to start from such a source.

## 4. Stateless forwarding

[`wse_model.noc.forward`](../../src/wse_model/noc/forward.py) simulates the two
rules over the induced subgraph. There is no routing table, no lookup path, and no
per-hop state: the whole path is the bitmap the flit carries.

- `Hop` records one node's decision: `node`, `ingress`, `egress`, `lands`.
- `Landing` records one commit into a node's receive range, with `order` and a
  `duplicate` flag.
- `MulticastTrace` is the result of one flit's traversal, exposing `land_nodes`
  (deduplicated, in delivery order), `duplicate_nodes`, `is_clean_tree_walk`,
  `hop_count`, `max_depth`, and `link_load`.

Because a cyclic induced subgraph would replicate a flit without bound, the
simulator **refuses to diverge**: it expands each node at most once, records any
repeat arrival as a duplicate landing, and lists the nodes it declined to
re-expand in `unexpanded_revisits`. The validator reports those as faults, and
`Noc.send` rejects any trace whose `is_clean_tree_walk` is false. The ingress port
is always excluded from `egress`, so a flit never bounces straight back.

## 5. `CalReg` residency

Calendar §3.9 puts the timeslot **value** in a resident register on each NoC node,
written once at load time. The core never sees that value; it supplies a 3 bit
`opcode`, and the node performs one register index `CalReg[opcode]` to decide when
to release the packet. [`wse_model.noc.calreg`](../../src/wse_model/noc/calreg.py)
models the four properties the design requires:

- **Resident and read-only during execution.** `CalRegSlot` is immutable content
  plus `arm_lead_cycles` and the identities that share the slot. `CalRegBank`
  installs one slot per `opcode` and **refuses a rewrite** of an installed slot.
- **Independent queue per `opcode`.** The bank is keyed by `opcode`, so one domain
  cannot head-of-line block another.
- **Illegal or uninstalled codes fault.** `CalRegSlot` and `CalRegBank.lookup`
  reject `opcode in OPCODE_RESERVED` (`{0, 7}`) and any code with no installed
  content; there is no default entry.
- **Shared constraint.** Every collective using one `opcode` shares one
  `CalReg[opcode]` entry, so the no-conflict and no-concurrency guarantees are the
  NoC algorithm's responsibility (Calendar §2.7.1). The model records the
  algorithm's `conflictProof` and never re-derives the timing guarantee.

`CalRegImage` is the die-wide mirror handed to the loader: all nodes receive a
byte-identical image, and `CalRegImage.install_into` installs it into every node
only if every node is drained. `Noc.install_calreg` first calls
`StopTheWorldWindow.require_drained` on every node, then installs. `Noc.send`
calls `CalRegBank.lookup` through `Noc._check_release` before injecting anything,
so a flit can never be released on an uninstalled or reserved `opcode`.

The same drain property is what makes cross-launch epoch isolation valid
(`SW-1`), so `StopTheWorldWindow` and `Noc.drained` are shared with the runtime
picture in [Runtime and loading](runtime.md).

## 6. Epochs

Calendar §1.5: the report instruction is a pure side effect with no return value,
so the round's `collectionEpoch` cannot come back through alignment. Each core
keeps a counter per `opcode` domain instead:

```text
epoch = CalendarNextEpoch(opcode)   // pure scalar increment, starts at 1
```

[`wse_model.calendar.epoch`](../../src/wse_model/calendar/epoch.py) implements:

- `EpochCounter` — per core, per `opcode`, with `width_bits` in the proposed 8–16
  bit range. `next(drained=...)` starts at 1, increments, and at capacity either
  wraps to 1 when `drained=True` or raises when older traffic is still in flight
  (contract 7, open item `C-5`).
- `EpochTracker` — all counters of one core, plus `next_epoch(opcode)` and
  `assert_spmd_consistent(opcode, peers)`, which models the consequence of
  invariant `E1`: a divergent counter makes receivers drop packets under the wrong
  epoch.
- `RecvContext` — the `{opcode, epoch}` context a receive command establishes,
  keyed with the AICORE / kernel / stream identity that `HW-5` requires to be
  isolated.

Two points the model makes explicit. First, the counter lives on a kernel-local
object, so it resets every launch and isolation across launches depends entirely
on `SW-1` (all Calendar traffic drained before the launch boundary), not on the
epoch value being monotonic. Second, the alignment domain is partitioned **by
`opcode`, not by group**: every core in a launch that uses the same `opcode`
rendezvouses on the same semaphore. `AlignmentDomain` models the arrival count and
`required_width_for` computes `ceil(log2(members + 1))`; `HW-7` requires at least
6 bit for the 32-core FFN phase B and the 40-core full-die collective against the
existing 4 bit field. The FFN's two phases both use `opcode 1`, so running them
back to back yields epochs 1 and 2 on the same counter.

## 7. The seven `expVal` contracts

Calendar §4.5 defines the one genuinely new instruction,
`MTE4_NOC_RECV_WAIT(dst, capacity, expVal, opcode, epoch)`. It **moves no bytes**:
the payload is written into the core's arena directly by the NoC, and MTE4 only
*accounts*. A receive command retires once the valid payload bytes that match
`{opcode, epoch, dstRange}` and are already committed reach
`expVal`. [`wse_model.calendar.receive`](../../src/wse_model/calendar/receive.py)
implements the seven P0 contracts of §4.5.2 as explicit, fail-closed checks.

| # | Contract (Calendar §4.5.2) | Implementation | Proving test |
| --- | --- | --- | --- |
| 1 | The unit is valid payload **bytes**; no header, CRC, padding, retransmit copy, or self-sourced byte counts | `Noc.send` skips the source's own landing when `self_delivery` is false; `ReceiveAccount.deliver` returns `DeliveryOutcome.SELF_SOURCED` for any `Segment.self_sourced`; headers and padding never reach the account | `tests/unit/test_receive_contracts.py::test_contract_1_the_unit_is_payload_bytes`, `tests/unit/test_noc.py::test_self_sourced_bytes_never_count` |
| 2 | Only writes inside `[dst, dst + capacity)` matching the current `{opcode, epoch}` count; anything else is discarded **and faults** | `ReceiveAccount._in_range` plus the `segment.key != self.key` check, both raising `ReceiveContractError(2)` | `test_contract_2_wrong_epoch_faults`, `test_contract_2_wrong_opcode_faults`, `test_contract_2_out_of_range_write_faults` |
| 3 | Accounting happens after the payload is committed and readable; MTE4 completion is an acquire | Modelled structurally: a `Segment` is delivered into the ledger only after the payload has been placed in the arena | — (no isolated unit test; contract 3 is a hardware ordering property) |
| 4 | Legal arrivals that predate the command but belong to the same established epoch must not be missed | `CoreIngress` buffers arrivals per `{opcode, epoch}` (`DeliveryOutcome.DEFERRED`) and `post` adopts them into the new account | `test_contract_4_early_arrivals_are_not_missed` |
| 5 | Duplicate packets must not be double counted, including multicast copies per land point | `ReceiveAccount.seen` holds `SegmentId(source, seq)`; `MulticastTrace` also reports `duplicate_nodes` | `test_contract_5_duplicate_segments_are_not_double_counted`, `test_contract_5_multicast_copies_dedupe_per_land_point` |
| 6 | `expVal == 0` completes immediately; `expVal > capacity`, a mismatch with the compiled value, or counter overflow faults | `ReceiveAccount.__post_init__` checks `expVal <= capacity` and `compiled_exp_val`; `deliver` raises `ReceiveContractError(6)` on overflow; `complete` is `counted_bytes >= exp_val` | `test_contract_6_exp_val_zero_completes_immediately`, `test_contract_6_exp_val_above_capacity_faults`, `test_contract_6_a_compiled_exp_val_mismatch_faults`, `test_contract_6_counter_overflow_faults_rather_than_satisfying_exp_val` |
| 7 | `opcode` is a weak discriminator (every AllGather shares `opcode = 1`), so `collectionEpoch` carries the entire discrimination duty | `EpochCounter` is unique per `opcode` domain and monotonic until a drained wrap; `CoreIngress.post` rejects two active receives for one key | `test_contract_7_two_active_receives_for_one_epoch_fault` |

Two supporting checks follow from the same fail-closed policy: a receive for a
reserved `opcode` raises (`test_reserved_opcode_receive_faults`), and a receive
cannot be retired before it is complete (`test_retire_requires_completion`).

The completion condition is **local byte accounting**, not a distributed
protocol — no notify, no semaphore, no threshold shadow. The price is that the
accounting must be exact, which is why every one of the seven is a fault rather
than a warning.

## 8. Symmetric addressing and `A3`

Calendar §2.8: the Calendar topology is opaque to software, so a send never names a
peer's physical address. It uses a **SPMD symmetric address plus this core's
segment offset**, and the hardware resolves the per-peer landing point:

```text
dst(s, r) = recvSymBase + r * recvRowStride + selfOff(s)
selfOff(s) = rankInGroup(s) * rowBytes        // packed AllGather
```

`SymmetricArena.dst_address(rank, row)` implements exactly that expression, and
`SymmetricArena.packed` builds the packed AllGather arena whose
`selfOff(rank) = index * rowBytes`. Three invariants ride on it:

| Invariant | Content | Implementation |
| --- | --- | --- |
| **A1 symmetric same-address** | every member's `recvTile` sits at the same local offset; under SPMD one constant `TASSIGN` satisfies it | `SymmetricArena.recv_sym_base` is shared; only `selfOff` varies |
| **A2 forwarding does not move the landing point** | `routeBits` says which nodes are passed and landed, never where in the arena | `Noc.send` computes the address from `arena_base`, `row_stride`, and `source_self_off`; `simulate_multicast` never touches it |
| **A3 fill** | the members' `selfOff` segments tile every arena row without overlap | `SymmetricArena.validate_fill` walks segments in offset order and raises on a gap, an overlap, or an incomplete row |

`PayloadGeometry` derives the two gaps the send instruction encodes
(`src_gap = sendRowStride - rowBytes`, `dst_gap = recvRowStride - rowBytes`) and
the receive bound `capacity = recvRowCount * recvRowStride`, and rejects a
`recv_row_count` that differs from `row_count`. `ARENA_SEGMENT_ALIGNMENT_BYTES`
is 32: `R-1` makes a 32 B row-start alignment a **correctness** requirement
(`check_source_alignment`), while `R-2` is efficiency only, so
`rowBytes` need not be a link multiple.

### The `expVal` triple identity

Calendar §2.8 requires three derivations of `expVal` to agree: the value the user
passes, the value derived from geometry, and the table entry's `expectedRxBytes`.
`PayloadGeometry.exp_val(land_count)` computes `rowCount × rowBytes × landCount`
where `landCount` counts **remote** land sources, so the source's own segment never
counts (contract 1). The model checks the identity in two places: `run_allgather`
passes the entry's `expected_rx_bytes` as `ReceiveAccount.compiled_exp_val`, which
raises on disagreement, and `CalendarRouteTable._check_conservation` recomputes the
land-set sum per destination and reports `V-CONSERVE` when it differs from the
declared value. `SymmetricArena.check_conservation` provides the same check for a
standalone arena.

## 9. The §2.7.2 validation set

Calendar §2.7.2 lists the checks PyPTO runs on the NoC algorithm's output. They are
independent of the algorithm and cost a linear pass per node.
`CalendarRouteTable.validate` runs them and records each in
`ValidationReport.checks_run`.

| Check (`checks_run` name) | What it rejects | Diagnostic code |
| --- | --- | --- |
| `entry-fits-gpr-pair` | an entry that no longer fits the 16 B one-GPR-pair layout (the 48-node case) | `V-ENTRY-SIZE` |
| `per-source-structural-checks` → `bit-pairs-legal` | any `01` pair (`L=1` with `P=0`) | `V-PAIR` |
| `per-source-structural-checks` → `source-on-path` | the source is not on its own path (`P_self = 0`) | `V-PSELF` |
| `per-source-structural-checks` → `induced-subgraph-is-tree` | a disconnected or cyclic `{P=1}` induced subgraph | `V-TREE-CONNECTED`, `V-TREE-ACYCLIC` |
| `per-source-structural-checks` → `land-set-complete` | `{L=1}` differs from the semantics' destination set, or `landCount` disagrees with `popcount(L)` | `V-LAND`, `V-LANDCOUNT` |
| `per-source-structural-checks` → `self-land-consistent` | the source's own `L` bit disagrees with `FabricSelfDelivery` | `V-SELFLAND` |
| `send-receive-conservation` | the land-set sum per destination differs from `expectedRxBytes` — the device-side `expVal` | `V-CONSERVE` |
| `arm-reachability` | a negative `armLeadCycles`; an unset window is a warning | `V-ARM-NEGATIVE`, `V-ARM-UNSET` (warning) |
| `noc-timing-proof-present` | a missing `conflictProof` is a warning, because the timing guarantee is the algorithm's to make | `V-CONFLICT-PROOF-MISSING` (warning) |
| `table-budget` | `keyCount` over 16, or a per-core D-cache residency over budget | `V-KEYCOUNT`, `V-DCACHE`; alignment and DDR-footprint checks are warnings (`V-ALIGN`, `V-ALIGN-PAD`, `V-DDR-FOOTPRINT`) |

A node count or geometry mismatch produces `V-NODECOUNT` or `V-GEOMETRY-MISSING`.
`validate_route_bits` returns after reporting illegal pairs, because every later
structural check assumes a legal bitmap.

The two timing guarantees of Calendar §2.7.1 — "no conflict within one `opcode`"
and "no two collectives share an `opcode` concurrently" — are **not re-derived**.
They require the NoC timing model (ports, virtual channels, quotas, pipeline
latency), so they are the algorithm's responsibility and are returned as
`conflictProof`. The model records the proof's presence and refuses to claim the
property itself.

`ValidationReport.raise_if_failed` turns a failed report into a `CalendarError`,
and `ValidationReport.format` renders the human-readable form the CLI prints.

## 10. The C-9 layout comparison

Calendar §2.6 emits the table as `kCalendarRoute[keyId][node]`. Because a core is
selected by the runtime `blockId`, every core's two loads name
`base + keyId*640 + blockId*16` and `+8`; different keys are 640 B apart, so each
core residents one 64 B D-cache line per key. Calendar §3.8.3 observes that a 64 B
line holds four 16 B entries (cells `4k..4k+3`), of which a core uses one, so 48 B
of every line it touches belongs to a neighbour. Transposing the table to
`kCalendarRoute[node][keyId]` makes a core's entries contiguous.

`TableLayout` implements both, with `KEY_MAJOR` as the default and `NODE_MAJOR` as
the `C-9` variant ([decision 0005](../decisions/0005-static-table-layout.md)):

| | key-major (default) | node-major (`C-9` variant) |
| --- | --- | --- |
| `entry_index(keyId, node)` | `keyId * node_count + node` | `node * key_count + keyId` |
| Address for core `n`, key `k` | `base + k * 640 + n * 16` | `base + n * key_count * 16 + k * 16` |
| Lines per core | `keyCount` | `ceil(keyCount / 4)` |
| FFN (`keyCount = 2`) | 2 lines = 128 B | 1 line = 64 B |
| Budget cap (`keyCount = 16`) | 16 lines = 1 KB | 4 lines = 256 B |
| Instruction count, addressing shape, total bytes | — | identical |
| Cold misses per core | 1 per key | 1 for the whole table |

The "4×" is the asymptotic and full-budget figure; for the FFN's two keys it is
2 → 1 lines, because the first four keys share one line. Calendar §3.8.3
recommends deciding before `keyCount > 4`, which is where key-major's residency
starts to grow linearly while node-major's stays at one line.
`CalendarRouteTable.d_cache_lines_per_core` and
`CalendarRouteTable.d_cache_bytes_per_core` expose the residency, and
`wse_model.noc.network.table_layout_lines` provides the same computation for a
table plus an override layout.
`tests/contracts/test_table_schema.py::test_both_layouts_emit_the_same_bytes_in_a_different_order`
proves the two layouts contain the same set of 16 B entries and the same total
bytes.

## 11. The AllGather closure

[`wse_model.collective.run_allgather`](../../src/wse_model/collective.py) drives one
phase through Step0–Step6 using the compiled table. Step1 (producer ordering) is
the caller's guarantee; the model enforces the rest:

- **Step2** — each member advances its own `opcode` counter through
  `Noc.next_epoch`, then `EpochTracker.assert_spmd_consistent` verifies the peers
  agree (invariant `E1`). A caller-supplied `epoch` that disagrees with the
  counter is rejected.
- **Step3** — each member posts a `ReceiveAccount` with `dst = recv_sym_base`,
  `capacity = geometry.capacity`, `exp_val = geometry.exp_val(land_count)`, and
  `compiled_exp_val = entry.expected_rx_bytes`. Posting happens before any send
  (invariant `O3`).
- **Step4** — each member sends its own row: `Noc.send` builds the plan from
  `definition.entry(node).route_bits` and the member's `selfOff`.
- **Step4s** — when `self_delivery` is false, the source's own bytes are excluded
  (they are the local UB-to-UB copy's job) and never enter `expVal`.
- **Step5** — the sends are drained, then each member's counted bytes are read
  back. `AllGatherReport.ok` is the conjunction of completion.
- **Step6** — accounts are retired only if the report is complete, so an incomplete
  phase cannot be papered over by a later round.

The `Report` also exposes `max_tree_depth`, `peak_link_load`,
`total_wire_bytes`, `total_header_bytes`, `total_payload_bytes`, and
`useful_payload_fraction`. These are **volume** numbers: the model does not model
release timing, which comes from `CalReg` contents the NoC algorithm produces
under a timing model this repository does not own.

Two limitations are deliberate and are surfaced as errors, not approximations:

- Only `AllGather` closes. `run_allgather` and
  `allgather_geometry_check` raise for any reduction collective, because the
  reduction semantics under `{P, L}` (open item `C-10`) are not defined.
- `self_delivery` must agree with the compiled key, or `run_allgather` raises: a
  disagreement would make the source's own `L` bit inconsistent, which is the
  §2.7.2 `selfLand` check.

## See also

- [Requirements: Calendar closure](../requirements/calendar-closure.md) for the
  numbered, test-backed statements.
- [Descriptors and schemas](../reference/descriptors.md) for the route-table JSON.
- [Open items](../reference/open-items.md) for `Q1`, `C-3`, `C-5`, `C-9`, `C-10`
  and the rest.
