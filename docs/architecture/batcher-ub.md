# Batcher and UB bus

The Batcher is the **single external entry point** to the WSE die: every byte that
crosses the chip boundary passes through it, in both directions. The UB bus is the
interconnect outside it. The model captures the design's structure — the two
disjoint paths, the four responsibilities, the nine-lane bus, and the cold-miss
split — in [`wse_model.host`](../../src/wse_model/host/), while the parameters the
design leaves open (`Q3`) stay declared inputs.

Design sources: whitepaper [§2.1](../design/wse-system-architecture-whitepaper.md),
[§4.1](../design/wse-system-architecture-whitepaper.md),
[§6](../design/wse-system-architecture-whitepaper.md),
[§12.1](../design/wse-system-architecture-whitepaper.md),
[§14.1](../design/wse-system-architecture-whitepaper.md); Calendar
[§3.1](../design/wse-calendar-scheme.md), [§3.8.4](../design/wse-calendar-scheme.md),
[§3.9](../design/wse-calendar-scheme.md).

## The single external entry point

The whitepaper §2.1 draws two structural constraints around the Batcher:

- **There is exactly one external port.** Any byte entering an AICORE from off-chip
  passes through the Batcher, and every AICORE result is written back through it.
  Instruction and constant cache-miss refills take the same route.
- **The Batcher does not participate in inter-core exchange.** Core-to-core payload
  moves on the NoC; it never goes out to the Batcher and back.

`wse_model.host.batcher` models the four responsibilities as
`BatcherResponsibility` — `KERNEL_BINARY`, `WEIGHTS`, `ACTIVATIONS`, `RESULTS` —
with the direction `in` for the first three and `out` for the last. Each is paired
with a `DispatchFrequency` (`ONCE_PER_MODEL`, `ONCE_PER_KERNEL`,
`EVERY_INFERENCE`) in a `DispatchPath`, and `dispatch_paths()` returns the four
paths of whitepaper §12.1:

| Responsibility | Direction | Frequency | Destination |
| --- | --- | --- | --- |
| `KERNEL_BINARY` | in | once per kernel | DDR code and data segments; refilled into I$/D$ on a miss |
| `WEIGHTS` | in | once per model load | each core's local DRAM, 2 KB page aligned |
| `ACTIVATIONS` | in | every inference | each core's UB / L1 |
| `RESULTS` | out | every inference | back through the Batcher to the requesting device |

`BATCHER_MEM_PATH` records the refill channel in one string: `DDR -> Batcher.mem ->
I$/D$; never through local DRAM and never through L1`. The two refill granularities
are constants: `INSTRUCTION_BLOCK_BYTES` = 2048 for the I-cache and
`DATA_CACHE_LINE_BYTES` = 64 for the D-cache.

`Batcher.mem` is a **dual-role** part: it stages the data plane and it is also the
control-plane relay for every I-Cache / D-Cache miss refill. The second role is
easy to miss and it decides the cold-start cost: because `Batcher.mem` is shared,
simultaneous cold misses by many cores do not cost `N × DDR latency`.
`RefillAccount(distinct_lines, requesters_per_line, line_bytes)` makes that split
explicit: `requests = distinct_lines × requesters_per_line`,
`ddr_backed_requests = distinct_lines`, and
`mem_served_requests = requests - ddr_backed_requests`. `BatcherMem` provides
`instruction_refill(distinct_blocks=..., requesters_per_line=...)` (2 KB blocks),
`data_refill(distinct_lines=..., requesters_per_line=...)` (64 B lines, the
Calendar table's path), `capacity_check(resident_bytes=...)`, and
`weight_page_check(weight_bytes=...)`.

For the FFN table this yields the account Calendar §3.8.4 gives: 20 distinct lines,
four cores sharing each, so 80 requests of which only 20 reach DDR and 60 are
absorbed by `Batcher.mem`. The same arithmetic is reported structurally by
`wse-model report dcache`.

## The two disjoint paths

Whitepaper §4.1 is the load-bearing picture: there are **two paths, and they do
not intersect**.

### Path one — instruction and constant

```text
DDR (.text + .rodata) -> Batcher.mem -> I-Cache (2 KB block) -> fetch/decode
                                     -> D-Cache (64 B line) -> scalar GPR
```

This path carries kernel code, immediates, the `.rodata` static route table, and
kernel arguments. Calendar §3.1 puts the cache refill channel precisely:
`D-Cache miss -> MSHR -> BIU -> Batcher.mem -> (miss) DDR -> 64 B line fill`, and
`I-Cache miss -> fetch -> Batcher.mem -> (miss) DDR -> 2 KB block fill`. It **does
not** pass through local DRAM and it **does not** pass through L1.

This is what makes the Calendar delivery story work. Calendar §3.2 classifies the
four Calendar values: `opcode`, `redOp`, `expVal`, `capacity`, and `selfOff` are
A-class immediates that fold into `.text` (I-Cache, zero D-cache traffic); the
`routeBits` table is an A-class `.rodata` object indexed by the runtime `blockId`
(D-Cache, `keyCount` lines per core); `blockId` is the only B-class value; and
`CalReg` is A-class but never enters a core cache at all. The model implements the
cache-shape consequences of this in `wse_model.calendar.table`,
`wse_model.analysis.dcache`, and `wse_model.noc.flit`, not as a cache simulator.

### Path two — payload

```text
local DRAM (2 KB page) <-> L1 / UB <-> L0A / L0B <-> Cube
L1 / UB <-> NoC <-> peer core arena
```

This path carries weights, activations, and intermediate results. It never uses
I-Cache or D-Cache. Cross-core traffic is the Calendar closure described in
[Calendar and NoC](calendar-noc.md); the arena itself is a UB or L1 region, which
is open item `Q7` / `S-2`.

The reason the two paths must stay disjoint is the bandwidth asymmetry: per-core
local DRAM (1 TB/s) is about 7.8× one NoC link (128 GB/s) and about 4.5× the
external fabric path (224 GB/s). Reading weights on core is cheap; moving anything
of weight scale between cores or off-chip cancels the advantage.

## The UB bus

[`wse_model.host.ub_bus`](../../src/wse_model/host/ub_bus.py) models the external
bus. `UbLane` has two members, `FABRIC` and `HOST`, with `lanes`, `bytes_per_sec`,
and `gb_per_s`; the constants are `FABRIC_LANES` = 8, `HOST_LANES` = 1, and
`TOTAL_LANES` = 9.

| Lane allocation | Rate | Use | Model symbol |
| --- | --- | --- | --- |
| 8 lanes | `8 × 224 Gbps = 224 GB/s` | die-to-die / to Davinci fabric | `UbLane.FABRIC`, `BANDWIDTHS["ub_fabric"]` |
| 1 lane | `1 × 112 Gbps = 14 GB/s` | in-rack Host CPU | `UbLane.HOST`, `BANDWIDTHS["ub_host"]` |
| 9 lanes total | — | — | `TOTAL_LANES` |

`UbBus(fabric_lanes=8, host_lanes=1)` rejects any allocation that exceeds the
nine-lane budget, and exposes `bandwidth(lane)`, `transfer_seconds(nbytes, lane)`,
`bytes_in(seconds, lane)`, and `weights_can_reside_only(weight_bytes=...,
local_dram_seconds=...)`, which answers whether crossing the bus would dominate
reading the same weights locally.

`local_dram_over_fabric_ratio()` returns `1e12 / 224e9 ≈ 4.464`, the ratio behind
the design's premise that only activations may cross the bus and weights must
reside. (`wse_model.analysis.bandwidth.local_dram_vs_noc_ratio()` gives the
different, 7.8125× ratio against one NoC link.)

`wse-model report bandwidth` prints the four published bandwidths plus the
NoC/DRAM ratio. Its UB entries are:

```json
"ub_fabric": { "name": "ub_fabric", "bytes_per_sec": 224000000000.0, "GB_per_s": 224.0,
               "source": "whitepaper §6.3: 8 x 224 Gbps = 224 GB/s" },
"ub_host":   { "name": "ub_host",   "bytes_per_sec": 14000000000.0,  "GB_per_s": 14.0,
               "source": "whitepaper §6.3: 1 x 112 Gbps = 14 GB/s" }
```

## The declared-but-open Batcher parameters

`BatcherSpec` holds the four values open item `Q3` leaves undefined, and **every
field defaults to `None`**, meaning *not declared*:

| Field | Meaning |
| --- | --- |
| `mem_capacity_bytes` | `Batcher.mem` capacity |
| `mem_bandwidth_bytes_per_sec` | `Batcher.mem` bandwidth |
| `cores_per_batcher` | how many cores one Batcher serves |
| `parallel_channels` | whether dispatch is multi-channel |

`is_declared` is true only when all four are supplied. `require(consumer=...)`
calls `require_resolved("Q3", ...)` and therefore raises `OpenItemError` while the
item is open, and `dispatch_seconds(nbytes)` refuses until the spec is declared.
`BatcherMem.capacity_check` does the same for a declared capacity.

Two observations from whitepaper §6.3 that the model records but does not enforce:
the fabric bandwidth (224 GB/s) is far below one core's local DRAM (1 TB/s), so
weights must reside; and the host channel (14 GB/s) is control-plane scale, fit for
commands and small metadata but not on the inference critical path.

## Where the Batcher appears in the model today

1. **`analysis.platform`** records the lane rates and derives the two byte rates.
2. **`analysis.bandwidth`** exposes them as `Bandwidth` objects.
3. **`analysis.dcache`** computes the route table's die-wide refill split.
4. **`host.ub_bus`** and **`host.batcher`** model the bus lane budget, the four
   dispatch paths, the refill account, and the open `Q3` parameters.
5. **`analysis.latency.LatencyBudget`** uses `ub_fabric` for the device-to-device
   transfer block, and treats the Batcher dispatch/gather time as a **declared
   input**. `LatencyBudget.blocks()` calls `require_resolved("Q3", ...)` and
   `LatencyBudget.total_seconds()` raises `OpenItemError` for `Q3` and `Q9`.
6. **`host.runtime.Loader`** models the three load-time chains, where the `CalReg`
   image is the only one that does **not** go through the Batcher.

## What is not modelled

- **`Batcher.mem` capacity and bandwidth behaviour.** The capacity is a declared
  input and `capacity_check` compares against it; there is no buffer, occupancy,
  or eviction model.
- **Aggregate AICORE-side bandwidth, cores per Batcher, parallel dispatch
  channels.** None is in the design sources; all four are `Q3`.
- **The asynchronous Batcher ↔ AICORE boundary.** There is no handshake, no
  readiness signal, and no Batcher cycle.
- **Cold-miss timing.** The refill *counts* are modelled; the latency is not.
- **Host and descriptor traffic beyond a byte count.** `Loader.launch` counts
  activation and descriptor bytes; there is no task queue.
- **DMA and TASSIGN.** The payload path is rows and segments, not descriptors.

## Open items that gate a fuller Batcher/UB model

| Item | Why it blocks the model |
| --- | --- |
| `Q3` | **Batcher specification**: `Batcher.mem` capacity and bandwidth, aggregate AICORE-side bandwidth, cores per Batcher, parallel dispatch channels. `BatcherSpec.require` and the latency budget both refuse without it. |
| `Q4` | **Position of DDR relative to local DRAM.** The documents show `DDR -> Batcher.mem -> I$/D$`, but the requirement describes only local DRAM. Until it is settled, the model keeps the two paths separate as a declared reading. |
| `Q9` | **Davinci ↔ WSE-Lite interface form and round-trip latency.** The other declared input the latency total needs. |
| `Q2` | whether a WSE-Lite is one reticle or several, which decides the fabric's structure and cross-reticle bandwidth. The model assumes a single reticle. |

All four are `Resolution.OPEN`; see
[Open items](../reference/open-items.md) and
[decision 0003](../decisions/0003-keep-open-items-explicit.md).

## See also

- [AICORE](aicore.md) — the other end of both paths.
- [Runtime and loading](runtime.md) — the dispatch chains and the `CalReg` bypass.
- [Requirements: Calendar closure](../requirements/calendar-closure.md) — the
  tested rules that do exist.
