# Open items

Whitepaper Appendix A (`Q1`–`Q12`) and Calendar §6.3 (`S-1`–`S-7`, `C-1`–`C-12`)
list values and interface choices the design documents explicitly do not fix. The
model registers every one of them in
[`wse_model/open_items.py`](../../src/wse_model/open_items.py) rather than
substituting a plausible default.

This page is **generated from the code**, so it cannot drift. The command is:

```bash
wse-model --json open-items
```

which reports `total: 31`, `returned: 31`, and
`by_resolution: { "open": 26, "assumed": 5, "resolved": 0 }`. The four columns
below are the registry's `id` and `title`, its `owner`, the `source` section it
came from, and the `note` describing the current treatment (plus the decision
record, when one is named). An em dash means the registry carries no note for that
item.

The three statuses are defined by `wse_model.open_items.Resolution`:

- **open** — no reading is chosen; code whose result would change materially under
  the other reading calls `require_resolved` and fails closed.
- **assumed** — a reading is adopted from a stated assumption and must name a
  decision record.
- **resolved** — decided by a decision record.

See [decision 0003](../decisions/0003-keep-open-items-explicit.md) for the
mechanism and [Decisions](../decisions/index.md) for the records.

## Open (26)

| id | title | owner | source | current treatment |
| --- | --- | --- | --- | --- |
| `Q1` | NoC node count: 40 (Calendar baseline, 5x8) or 48 (whitepaper hardware, 6x8) | hardware | Whitepaper Appendix A | Both readings are modelled: routeBits is 80 bit at 40 nodes and 96 bit at 48 nodes, and the flit header grows from about 12 B to about 14 B. No single value is authoritative yet. |
| `Q2` | Reticle / die count per WSE-Lite | hardware | Whitepaper Appendix A | The model assumes a single reticle with an intra-reticle synchronous NoC. |
| `Q3` | Batcher specification: Batcher.mem capacity and bandwidth, aggregate AICORE-side bandwidth, cores per Batcher, parallel dispatch channels | hardware | Whitepaper Appendix A | Batcher timing parameters are declared inputs, never constants. |
| `Q4` | Position of DDR relative to local DRAM | hardware | Whitepaper Appendix A | The model keeps the instruction/constant path (DDR -> Batcher.mem -> I$/D$) separate from the payload path (local DRAM -> L1 -> L0). |
| `Q5` | Target model dimensions: H, I, expert count, top-k, head count, weight precision for DeepSeek-V4 Pro | workload | Whitepaper Appendix A | No concrete partition or latency figure is produced without these. |
| `Q6` | MoE load-imbalance policy under invariant E1 | workload | Whitepaper Appendix A | Member cores must not conditionally skip a round; whether the mechanism is a fixed capacity factor with zero sends or something else is open. |
| `Q7` | Collective arena placement: UB or L1 (Calendar S-2) | hardware | Whitepaper Appendix A | Determines the tile address-space qualifier and the double-buffer budget. |
| `Q8` | Weight layout in local DRAM and the prefetch path to L0B | hardware | Whitepaper Appendix A | Determines whether MTE stages local DRAM through L1. |
| `Q9` | Davinci <-> WSE-Lite interface form and round-trip latency | system | Whitepaper Appendix A | Round-trip latency is a declared input to the latency model. |
| `Q10` | Whether the two WSE-Lite instances are identically configured | system | Whitepaper Appendix A | — |
| `Q11` | Production weight precision and mixed-precision acceptability | workload | Whitepaper Appendix A | — |
| `Q12` | Degradation path for a faulty core or link (Calendar C-11) | system | Whitepaper Appendix A | Drives whether the .rodata table stays an A-class value or degrades to a load-time buffer (Calendar §3.11). |
| `S-1` | Freeze of operand widths and units for expVal / capacity / epoch, and the reused operand slots | hardware-isa | Calendar §6.3 | The model uses uint32 for all three, following the Calendar baseline. |
| `S-2` | Arena address space and naming (ubuf vs cbuf) for the send and receive facades | hardware+software | Calendar §6.3 | Duplicate of whitepaper Q7. |
| `S-3` | Machine encoding of the symmetric address | hardware-isa | Calendar §6.3 | Affects lowering only; the PTO interface is unchanged. |
| `S-4` | Machine mnemonics for the send and receive instructions | isa-review | Calendar §6.3 | Documentation only. |
| `S-5` | Two small semantics: sid handling in the Calendar direction, and the ordering meaning of the report instruction's pipe operand | hardware-isa | Calendar §6.3 | Determines whether a barrier before Step4 can be elided. |
| `S-6` | Packet / segment identity de-duplication, including multicast copies per land point | hardware | Calendar §6.3 | No software-side substitute: without it expVal can be met early. |
| `S-7` | Frozen shape of the three-state mock | software | Calendar §6.3 | — |
| `C-1` | Send-side 80 bit operand encoding: scheme A (two GPR slots or one even/odd pair plus a 6 bit immediate) vs scheme B (latch into an SPR) | hardware-isa | Calendar §6.3 | Scheme A adds 2 data-plane instructions; scheme B adds 3 plus a fence. The call site is identical either way. |
| `C-3` | Reduction element type field in the flit header | noc+isa | Calendar §6.3 | Must be fixed before the header format freezes. AllGather-only is not blocked, because redOp is dormant there. |
| `C-4` | Global synchronisation accuracy of the internal NoC / BSP time base | noc+bsp | Calendar §6.3 | Physical realizability of invariant O2; no software interface change. |
| `C-8` | Static table shape for per-row routing in ReduceScatter / Scatter | compiler | Calendar §6.3 | A third table dimension multiplies both DDR footprint and per-core D-cache residency by shardCount. |
| `C-10` | Complete definition of reduction semantics under {P, L} | noc | Calendar §6.3 | Gates opening the Reduce / AllReduce / ReduceScatter branches. |
| `C-11` | Degradation path when a faulty core or link makes each instance's topology different | system+compiler | Calendar §6.3 | Duplicate of whitepaper Q12. |
| `C-12` | D-cache strategy for the .rodata table, and whether keyCount <= 16 suffices | compiler | Calendar §6.3 | — |

## Assumed (5)

| id | title | owner | source | current treatment |
| --- | --- | --- | --- | --- |
| `C-2` | Flit header carriage: per-flit copy (baseline) vs per-packet header with per-packet context in the NoC | noc | Calendar §6.3 | The model implements the per-flit baseline, which is what the 12 B / 19% overhead figure describes. (decision 0001) |
| `C-5` | epochTag width and wraparound policy, including the cross-launch counter initial value | hardware+compiler | Calendar §6.3 | The model follows the Calendar baseline: per-launch counter starting at 1, with launch-boundary drain. epochTag is a declared 8-16 bit parameter. (decision 0001) |
| `C-6` | epochTag carriage: implicit context established by the receive command vs an explicit send operand | hardware-isa | Calendar §6.3 | The model follows the Calendar baseline (implicit context). (decision 0001) |
| `C-7` | blockId acquisition: block_idx SPR vs kernel argument | hardware+runtime | Calendar §6.3 | The model assumes the SPR path (zero loads) and models the argument path as the documented fallback. (decision 0001) |
| `C-9` | Static table layout: key-major vs node-major | compiler | Calendar §6.3 | The model defaults to the key-major baseline and also models the node-major variant, because the 4x D-cache reduction is free. (decision 0005) |

## Resolved (0)

| id | title | owner | source | current treatment |
| --- | --- | --- | --- | --- |
| _(none)_ | — | — | — | — |

No item is `resolved` yet: every adopted reading is an _assumption_ with an
explicit record, not a settled hardware decision. `C-2`, `C-5`, `C-6`, and `C-7`
are assumed by [decision 0001](../decisions/0001-adopt-calendar-baseline-defaults.md);
`C-9` is assumed by [decision 0005](../decisions/0005-static-table-layout.md).

## See also

- [CLI reference: `open-items`](cli.md#open-items) for the command and its flags.
- [Decision 0003](../decisions/0003-keep-open-items-explicit.md) for why the model
  refuses to default.
- [Roadmap](../roadmap.md) for which items gate each future stage.
