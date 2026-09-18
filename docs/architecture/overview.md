# Architecture overview

This page is the map of the implemented model: which module owns which rule, how a
route bitmap becomes a completed collective, and which layering rules the code is
required to obey. It describes what exists in `src/wse_model/` today; the
[roadmap](../roadmap.md) states what does not.

## Module map

### Top-level modules

| Module | Responsibility |
| --- | --- |
| [`wse_model/__init__.py`](../../src/wse_model/__init__.py) | The public package surface: the error classes, `MeshTopology`, `TopologyProfile`, the `CALENDAR_BASELINE` and `WHITEPAPER_HARDWARE` profiles, `topology_profile`, and `__version__`. It is deliberately small; the domain packages are imported explicitly. |
| [`wse_model/version.py`](../../src/wse_model/version.py) | The single source of truth for the package version (`0.1.0`), consumed by packaging, the CLI, and emitted reports. The repository-standards gate checks it against `pyproject.toml`. |
| [`wse_model/errors.py`](../../src/wse_model/errors.py) | The fail-closed error hierarchy rooted at `WseModelError`: `TopologyError`, `CalendarError` and its subclasses (`IllegalBitPairError`, `RouteTreeError`, `LandSetError`, `ConservationError`, `ReceiveContractError`), `VersionMismatchError`, and `OpenItemError`. Every illegal encoding, structural violation, or failed consistency check raises one of these. |
| [`wse_model/open_items.py`](../../src/wse_model/open_items.py) | The registry of design values the sources leave open: `OpenItem`, `Resolution` (`OPEN` / `ASSUMED` / `RESOLVED`), the `OPEN_ITEMS` table covering `Q1`–`Q12`, `S-1`–`S-7`, `C-1`–`C-12`, and the `require_resolved` gate that fails closed while an item is open. |
| [`wse_model/topology.py`](../../src/wse_model/topology.py) | The NoC topology descriptors. `MeshTopology` is a rectangular 2D mesh with dimension-ordered physical adjacency (`node = row * cols + col`) that defines adjacency only and never routes. `TopologyProfile` adds the AICORE / I/O assignment. Both readings of `Q1` are first-class: `CALENDAR_BASELINE` (5×8 = 40), `WHITEPAPER_HARDWARE` (6×8 = 48), and `WHITEPAPER_HARDWARE_40_AICORE` (6×8 with 8 I/O nodes). |
| [`wse_model/fixtures.py`](../../src/wse_model/fixtures.py) | The canonical fixtures transcribed from the design documents: `GOLDEN_ROUTE_BITS` (the §2.2.1 consistency anchor), `golden_route_bits`, `group_allgather_bitmap`, `row_groups`, `col_groups`, and `ffn_example`, which compiles the FFN two-phase AllGather and asserts the two published hex rows so the reconstruction cannot drift. |
| [`wse_model/collective.py`](../../src/wse_model/collective.py) | The integration point: `run_allgather` drives one collective phase through Step0–Step6 using a compiled route table, enforcing `O3` (post before send), `E1` (uniform epoch across members), and byte-accounting completion. `AllGatherReport` and `MemberState` describe the outcome. |
| [`wse_model/cli.py`](../../src/wse_model/cli.py) | The `wse-model` command-line interface: a thin, deterministic front end over the semantic core. Every command can emit JSON. See the [CLI reference](../reference/cli.md). |
| [`wse_model/__main__.py`](../../src/wse_model/__main__.py) | Allows `python -m wse_model` to run the CLI. |

### `wse_model.calendar` — the encoding and legality of the Calendar scheme

| Module | Responsibility |
| --- | --- |
| [`calendar/route_bits.py`](../../src/wse_model/calendar/route_bits.py) | The `routeBits` codec. `BitPair` is the four-value `{P, L}` enum with the on-wire integer order `L \| (P << 1)`; `RouteBits` is an immutable `2 × node_count` bitmap with checked (`from_sets`) and unchecked (`from_bytes`) constructors. It maps between pairs and bytes and never routes or validates reachability. |
| [`calendar/entry.py`](../../src/wse_model/calendar/entry.py) | The 16 B `CalendarRouteEntry` (`routeBits[10]`, `landCount`, `flags`, `expectedRxBytes`) and the `CalendarRouteRegs` register-pair view that mirrors Calendar §1.7 field for field. `RouteEntryFlags` defines `isMember`, `isRoot`, and `selfLand`. |
| [`calendar/collective.py`](../../src/wse_model/calendar/collective.py) | Collective semantics and widths: `Collective` (the six semantics plus the reserved codes 0 and 7), `RedOp`, `ReductionElementType` (whose name resolution is gated on `C-3`), and `AlignmentDomain`, which models the alignment semaphore arithmetic and the `HW-7` width requirement. |
| [`calendar/key.py`](../../src/wse_model/calendar/key.py) | Logical identity and the inseparable constant pair: `RouteKey = {programId, kernelId, phaseId, collective, groupRole}`, `GroupRole` (a parameterised role such as `ROW(my_row)`, not a concrete group), `CalendarKeyRef`, and `CalendarKeyRegistry`, which assigns `keyId` values and defends invariant `O1`. |
| [`calendar/epoch.py`](../../src/wse_model/calendar/epoch.py) | Per-round `collectionEpoch` accounting: `EpochCounter` (per core, per `opcode`, starts at 1, wraparound only when drained), `EpochTracker` (all counters of one core, plus the SPMD-consistency check), and `RecvContext` (the `{opcode, epoch}` context a receive command establishes). |
| [`calendar/geometry.py`](../../src/wse_model/calendar/geometry.py) | Landing geometry: `PayloadGeometry` derives `srcGap`, `dstGap`, `nBurst`, `capacity`, and `expVal = rowCount × rowBytes × landCount` from tile geometry; `SymmetricArena` and `ArenaSegment` implement the symmetric address `recvSymBase + row × recvRowStride + selfOff(rank)` and the `A3` fill check. |
| [`calendar/receive.py`](../../src/wse_model/calendar/receive.py) | The receive side: `ReceiveAccount` implements the seven `expVal` contracts of Calendar §4.5.2 as fail-closed checks; `CoreIngress` is the per-core ledger that defers and adopts early arrivals so contract 4 holds; `Segment` and `SegmentId` carry the de-duplication identity. |
| [`calendar/validate.py`](../../src/wse_model/calendar/validate.py) | Structural validation: `check_induced_tree`, `validate_route_bits` (the §2.7.2 per-source check set), `validate_entry_layout`, and `validate_table_budget`, plus the `Diagnostic` / `ValidationReport` / `Severity` machinery. |
| [`calendar/table.py`](../../src/wse_model/calendar/table.py) | The compiled artifact: `CalendarRouteTable` (`kCalendarRoute[keyId][node]`), `KeyDefinition`, the `TableLayout` key-major / node-major choice, both address computations, byte emission with 64 B alignment, the table-level validation set, the three-version check, and JSON serialisation. |

### `wse_model.noc` — the mesh and its behaviour

| Module | Responsibility |
| --- | --- |
| [`noc/flit.py`](../../src/wse_model/noc/flit.py) | Flit formatting. `FlitHeader` computes the per-flit header (`routeBits` + `opcode`/`redOp` + `epochTag`) and its overhead; `split_payload` and `flit_count` model the hardware replicating one header over every flit of a run. |
| [`noc/forward.py`](../../src/wse_model/noc/forward.py) | The two stateless forwarding rules. `simulate_multicast` expands the `{P=1}` **induced** subgraph, deduplicates landings, refuses to diverge on a cycle, and returns a `MulticastTrace` with hop count, depth, link load, and duplicate nodes. |
| [`noc/calreg.py`](../../src/wse_model/noc/calreg.py) | The resident timeslot register. `CalRegSlot` / `CalRegBank` implement per-`opcode` residency, illegal-code faults, and refused rewrites; `StopTheWorldWindow` tracks in-flight traffic; `CalRegImage.install_into` installs the die-wide mirror only into drained nodes. |
| [`noc/network.py`](../../src/wse_model/noc/network.py) | The NoC as a whole: `Noc` owns the register banks, windows, ingress ledgers, and epoch trackers; `Noc.send` turns a `SendPlan` into flits, forwards them, and accounts every landing; `SendOutcome` reports volume (flits, hops, wire bytes, header bytes, payload delivered). Timing is not modelled here. |

### `wse_model.analysis` — closed-form performance arithmetic

| Module | Responsibility |
| --- | --- |
| [`analysis/platform.py`](../../src/wse_model/analysis/platform.py) | The platform constants transcribed from the design documents, each carrying its source: clocks, local DRAM size and bandwidth, on-chip buffer capacities, Vector/FixPipe width, Cube precision shapes (`PRECISIONS`, `PrecisionSpec`), and the UB bus lane rates. `AicoreSpec` summarises one AICORE. |
| [`analysis/bandwidth.py`](../../src/wse_model/analysis/bandwidth.py) | The four published bandwidths (`BANDWIDTHS`), the local-DRAM-to-NoC-link ratio, `flit_header_cost`, `collective_transfer_seconds`, and `two_phase_allgather_bytes`. |
| [`analysis/roofline.py`](../../src/wse_model/analysis/roofline.py) | The roofline that motivates the architecture: arithmetic intensity `2 × batch`, the balance point per precision, and the minimum batch to escape the memory-bound regime. |
| [`analysis/dcache.py`](../../src/wse_model/analysis/dcache.py) | The route table's D-cache budget. `DCacheSpec` is the per-core cache (16 KB, 64 B lines, four 16 B entries per line); `RouteTableResidency` computes lines per core, die-wide lines, refill requests, the `Batcher.mem` / DDR split, the inherent 4× entry-to-line amplification, and the "one cold miss per operator" caveat. `dcache_budget` builds one. |
| [`analysis/latency.py`](../../src/wse_model/analysis/latency.py) | The five-block latency budget. Three blocks are computed from declared volumes; the Batcher block (`Q3`) and the round-trip block (`Q9`) are declared inputs, and `total_seconds` raises `OpenItemError` rather than inventing them. |

### `wse_model.core` — the AICORE

| Module | Responsibility |
| --- | --- |
| [`core/pipelines.py`](../../src/wse_model/core/pipelines.py) | The pipe set (`Pipe`) and the Calendar ordering rules: `INDEPENDENT_FROM_MTE4` names the pipes that must keep flowing while an MTE4 wait is unsatisfied, `PipeTracker` enforces and checks it (`check_no_deadlock`), `PipeBarrier` models the "MTE3 barrier waits for the actual send" rule, and `calendar_step_pipes()` maps Step0–Step6 onto pipes. |
| [`core/dram.py`](../../src/wse_model/core/dram.py) | The per-core local DRAM (384 MB, 1 TB/s, 2 KB page): page arithmetic (`pages_touched`, `pages_for_rows`), `read_seconds`, `bandwidth_efficiency`, and `expert_capacity`. `LocalDramLayout` declares the blocking and `require_fill_path()` raises open item `Q8`. |
| [`core/buffers.py`](../../src/wse_model/core/buffers.py) | The L0A/L0B/L0C/L1/UB hierarchy as `BufferKind` and `BUFFER_CAPACITY_BYTES`, with `TileRequirement` / `BufferResidency` / `fit_check` for double-buffered fit checks. `BufferResidency.arena_placement()` raises open item `Q7` / `S-2`. |
| [`core/cube.py`](../../src/wse_model/core/cube.py) | Cube and Vector timing: `MatmulShape`, `matmul_timing()` and `MatmulTiming` (cycles, compute and fetch seconds, arithmetic intensity, memory-bound verdict, balance point, roofline seconds), and `VectorTiming` at 256 B/cycle. |

### `wse_model.host` — the Batcher, the UB bus, and the runtime

| Module | Responsibility |
| --- | --- |
| [`host/ub_bus.py`](../../src/wse_model/host/ub_bus.py) | The external bus: `UbLane` (fabric / host), `FABRIC_LANES` = 8, `HOST_LANES` = 1, `TOTAL_LANES` = 9, and `UbBus` with a lane-budget check, per-lane transfer arithmetic, and `local_dram_over_fabric_ratio()`. |
| [`host/batcher.py`](../../src/wse_model/host/batcher.py) | The Batcher: `BatcherResponsibility` (4), `DispatchFrequency` (3), `DispatchPath` and `dispatch_paths()`, `BATCHER_MEM_PATH`, the 2 KB / 64 B refill granularities, `RefillAccount`, `BatcherMem`, and `BatcherSpec` whose four `Q3` fields all default to `None` and whose `require()` fails closed. |
| [`host/runtime.py`](../../src/wse_model/host/runtime.py) | The three `RuntimeTier`s, the four `DispatchChain`s and `dispatch_chains()`, `VersionSet.check`, `InstallState`, `Loader` (install kernel / weights / `CalReg`, check versions, kickstart, launch, steady-state bytes), `LaunchConstraints` (the four §12.3 constraints), and `Scheduler`. |

### `wse_model.compiler` — what the toolchain must emit

| Module | Responsibility |
| --- | --- |
| [`compiler/selfcheck.py`](../../src/wse_model/compiler/selfcheck.py) | The F1/F2/F3 self-checks of Calendar §3.10 over a **declared** symbol and section manifest rather than an ELF parse: `Symbol`, `Section`, `SymbolKind`, `ObjectFile`, `SectionInfo`, `load_object_file`, and `check_compiled_product`. F1 rejects writable Calendar static state, F2 rejects a materialised `CalendarKeyRef`, and F3 checks the `kCalendarRoute` section, alignment, size, and read-only-ness. The manifest schema is `schemas/kernel-object.schema.json` (`wse-model/kernel-object/1`). |
| [`compiler/package.py`](../../src/wse_model/compiler/package.py) | The compiled deployment package: `deployment_artifacts()` (the whitepaper §13.3 list), `CallSiteImmediate` (the Calendar §2.7.3 step-4 constants and the indivisible `CalendarKeyRef`), `DeploymentPackage` / `build_package`, and `check_opcode_domains`. `DeploymentPackage.validate` merges the route-table checks, the F1/F2/F3 product checks, artifact version agreement, the same-`opcode` concurrency rule, weight-shard page alignment, and `.rodata` alignment. See [Compiler](compiler.md). |

### Packages still being added or absent

- `src/wse_model/acir/` is present and importable but **in progress**. Its tests
  live under `tests/acir/` and are opt-in, because they require the
  `agentic_circuit` frontend and the native ACIR tools; they are not exercised by
  the default `make check` gate. See
  [decision 0002](../decisions/0002-two-layer-model.md).
- `src/wse_model/data/` does not exist. The README's layout table is the target
  shape.

## Data flow: from a route bitmap to `expVal` completion

The closure is a single path. Each step names the symbol that performs it.

1. **Encode or receive the bitmap.** A route bitmap is either built with a checked
   constructor (`RouteBits.from_sets`, which rejects `L=1` with `P=0`) or decoded
   from bytes (`RouteBits.from_bytes`, which preserves an illegal `01` so that
   validation can reject it). The bit order is fixed: `routeBits[2i+1] = P_i`,
   `routeBits[2i] = L_i`, LSB first within each byte.
2. **Bind it to a logical identity.** `CalendarKeyRegistry.register` assigns a
   `keyId` to a `RouteKey` and refuses to bind one `keyId` to two identities,
   which is how invariant `O1` ("routing and timeslot are same-source") is
   defended in software.
3. **Compile it into a 16 B entry.** `CalendarRouteEntry` joins the bitmap with
   `landCount`, `flags` (`isMember` / `isRoot` / `selfLand`), and
   `expectedRxBytes`. `CalendarRouteTable` stores one entry per `(keyId, node)`
   and can emit the `.rodata` bytes under either table layout.
4. **Validate the table.** `CalendarRouteTable.validate` runs the §2.7.2 set:
   entry fits the GPR pair, per-source structural checks (`validate_route_bits`:
   legal pairs, `P_self`, induced-subgraph-is-a-tree, land-set completeness,
   `selfLand` consistency), send/receive conservation, arm reachability, the
   presence of the NoC algorithm's `conflictProof`, and the table budget.
5. **Post the receive command.** `run_allgather` derives each member's `expVal`
   from `PayloadGeometry.exp_val(landCount)` and posts a `ReceiveAccount` before
   any send, enforcing invariant `O3`.
6. **Inject the send.** `Noc.send` takes a `SendPlan` (source, bitmap, `opcode`,
   `epoch`, row geometry, `selfOff`, `self_delivery`, expected bytes), checks that
   `CalReg[opcode]` is installed, and builds one `FlitHeader` for the send.
7. **Forward the flits.** `simulate_multicast` walks the `{P=1}` induced subgraph
   from the source: at each node it lands if `L=1` and copies the flit to every
   physical neighbour with `P=1` except the ingress port. A cyclic subgraph
   produces duplicate landings rather than an infinite loop, and `Noc.send`
   refuses it outright.
8. **Account the delivered bytes.** Every landing becomes a `Segment` delivered to
   the destination's `CoreIngress`. `ReceiveAccount.deliver` counts only payload
   bytes that match the current `{opcode, epoch}` and fall inside
   `[dst, dst + capacity)`; it discards self-sourced bytes and duplicates, and it
   faults on a mismatch, an out-of-range write, or a counter overflow.
9. **Complete on `expVal`.** A receive command retires when
   `counted_bytes >= exp_val`. `run_allgather` drains the sends (Step5), checks
   every member's account, and only then retires them (Step6). The report's `ok`
   is the conjunction of all members' completion.

Two properties fall out of that path and are worth stating explicitly. First,
completion is **local byte accounting**, not a distributed protocol: there is no
`Notify`, no semaphore, and no write-with-notify. Second, the model never claims
the two timing guarantees of Calendar §2.7.1 ("no conflict within one `opcode`"
and "no two collectives share an `opcode` concurrently"). Those require the NoC
timing model; the table records the algorithm's `conflictProof` and the validator
warns when it is absent.

## Layering rules

The rules below are from [`AGENTS.md`](../../AGENTS.md) and are binding on every
change.

### Ownership and scope

- This repository owns the WSE model: encoding, legality, conservation,
  scheduling, capacity, and performance semantics.
- `PTO-ISA/pyCircuit` owns `agentic_circuit`, its ACIR dialect, ACSim/gfsim, and
  the PYC/C++/Verilog backend. Framework semantics are never patched from here; a
  gap is reported upstream and the consuming revision is pinned.
- `PTO-ISA/pto-spec` owns PTO instruction semantics. PTO encoding and instruction
  handlers are not duplicated here.
- `docs/design/` is read-only source material. A divergence is recorded in
  `docs/decisions/`, never by editing the document.

### Hard rules

1. **Never invent a value the design sources leave open.** Represent it as a
   registered `OpenItem` or fail loudly.
2. **Two layers, one semantics.** The pure-Python core in
   `src/wse_model/<domain>/` is the authority; the ACIR modules express the same
   rules and must not disagree. Land a rule change in the core with a unit test
   first.
3. **Exact widths.** `routeBits` is `2 × node_count` bit, `opcode` is 3 bit,
   `redOp` is 3 bit, `epochTag` is an open 8–16 bit parameter, and a route-table
   entry is 16 B. Do not widen, round, or "clean up" a width.
4. **Golden vectors are contract.** The Calendar §2.2.1 vector and the FFN
   `keyId 0` / `keyId 1` rows are frozen; changing them needs a decision record.
5. **Fail closed.** An illegal bit pair, a cyclic induced subgraph, an
   inconsistent `selfLand` bit, or a failed version check is a fault, not a
   warning.
6. **Keep unresolved dimensionality explicit.** Model both the 40-node and
   48-node readings of `Q1`; do not hard-code one and hide the other.
7. **No secrets, no telemetry, no network calls** in model code paths.
8. **No AI co-author lines** in commits or pull request text.

## Related pages

- [Calendar and NoC](calendar-noc.md) for the semantics behind every step above.
- [Requirements](../requirements/calendar-closure.md) for the numbered,
  test-backed statements.
- [Testing and gates](../development/testing-and-gates.md) for how each rule is
  proven.
