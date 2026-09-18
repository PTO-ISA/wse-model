# Runtime and loading

The runtime turns compile-time artifacts into chip state and drives the Batcher
on every inference. The model captures its structure — the three frequency tiers,
the four dispatch chains and their destinations, the three-version check,
kickstart, and the scheduling constraints — in
[`wse_model.host.runtime`](../../src/wse_model/host/runtime.py) and
[`wse_model.noc.calreg`](../../src/wse_model/noc/calreg.py). What it does not
capture is a real transport: there is no PCIe, no task queue, and no device.

Design sources: whitepaper [§4.2](../design/wse-system-architecture-whitepaper.md),
[§10.3](../design/wse-system-architecture-whitepaper.md),
[§12](../design/wse-system-architecture-whitepaper.md),
[§13](../design/wse-system-architecture-whitepaper.md),
[§14](../design/wse-system-architecture-whitepaper.md); Calendar
[§1.5](../design/wse-calendar-scheme.md), [§3.6](../design/wse-calendar-scheme.md),
[§3.9](../design/wse-calendar-scheme.md), [§6.1](../design/wse-calendar-scheme.md).

## The three frequency tiers

Whitepaper §12 splits the runtime's work into three tiers. Confusing them is, the
document says, a common source of performance bugs; keeping them separate is the
point of Calendar's classification of values into A / B / C classes (whitepaper
§4.2, Calendar §3.1). `RuntimeTier` names them:

| Tier | `RuntimeTier` | What happens | Frequency |
| --- | --- | --- | --- |
| **Load** (装载期) | `LOAD` | kernel binary dispatch; weights written into each core's local DRAM; the `CalReg` die-wide image atomically installed; the three-version check; kickstart | once at model load |
| **Per launch** (每次 launch) | `PER_LAUNCH` | task descriptor; args buffer (including the `blockId` source); input tensors; the phase-boundary barrier | once per operator |
| **Runtime** (运行期) | `RUNTIME` | the runtime does not intervene | — |

The payoff of the classification is the steady state: because `routeBits` is
A-class and `CalReg` is installed once, **a launch dispatches no Calendar data at
all**. `Loader.steady_state_dispatch_bytes(activation_bytes=...,
descriptor_bytes=64)` returns exactly the activation plus descriptor bytes — no
Calendar data, no per-core expansion, no run-time descriptor fan-out.

## The dispatch chains

`DispatchChain` has four members — `KERNEL_BINARY`, `WEIGHTS`, `CALREG`, and
`ACTIVATIONS` — and `dispatch_chains()` returns each with its tier, whether it
goes `via_batcher`, its `destination`, and whether it passes `through_local_dram`
or `through_l1`:

| Chain | Tier | Via Batcher | Destination | Through local DRAM | Through L1 |
| --- | --- | --- | --- | --- | --- |
| `KERNEL_BINARY` (`.text` + `.rodata`) | load | yes | DDR code/data segments; refilled into I$ / D$ on a miss | no | no |
| `WEIGHTS` | load | yes | each core's local DRAM | yes | no |
| `CALREG` | load | **no** | NoC node timeslot registers | no | no |
| `ACTIVATIONS` | per launch | yes | each core's UB / L1 | no | no |

Two entries deserve emphasis. First, the kernel binary never passes through local
DRAM: the cache refill path is `Batcher.mem -> I$/D$`, and local DRAM is the
operator data plane. Second, `CALREG` is the only chain that does not pass through
the Batcher, because its destination is the NoC rather than an AICORE; whitepaper
§14.1 makes it an atomic write inside a stop-the-world window.

## The `Loader`

`Loader` models the load and launch sequence over an `InstallState`, without any
transport:

- `install_kernel(rodata_bytes=...)` — places `.text` and `.rodata`; the
  whitepaper notes this is indistinguishable from an ordinary dispatch.
- `install_weights(shard_bytes=...)` — rejects a shard that is not a 2 KB page
  multiple (whitepaper §3.4, §14.1).
- `install_calreg(image)` — refuses unless `InstallState.drained`, which is the
  stop-the-world requirement.
- `check_versions(compiled, chip)` — delegates to `VersionSet.check`.
- `kickstart()` — requires the kernel, weights, `CalReg`, and a passing version
  check; sets `kicked_off`.
- `launch(activation_bytes=..., descriptor_bytes=64)` — requires `InstallState.ready`
  and a drained die.

`InstallState.ready` is the conjunction of `kernel_installed`, `weights_installed`,
`calreg_installed`, `versions_checked`, and `kicked_off`.

## The three-version check

Compiled artifacts carry three version numbers, and the load-time check requires
all three to agree (whitepaper §10.3, §14.2; `HW-13`). Any mismatch must **fault**;
degraded operation is not permitted.

| Version | Identifies |
| --- | --- |
| `topologyVersion` | the physical topology assumed at compile time |
| `calendarVersion` | the content of the timeslot registers |
| `routeVersion` | the content of the `routeBits` static table |

The three together replace the hardware anchor that would otherwise be a single
instruction atomically selecting both route and timeslot. That anchor does not
exist — `routeBits` travels in `.rodata` / D-cache and `opcode` in `.text` /
I-cache, two physically separate chains — so the version check plus the
`CalendarKeyRef` type discipline (invariant `O1`) is the substitute.

Two implementations exist. `wse_model.host.runtime.VersionSet(topology_version,
calendar_version, route_version)` checks a compiled set against a chip set in
`VersionSet.check(other)` and raises `VersionMismatchError` listing every
mismatched pair. `CalendarRouteTable.check_versions(topology_version=...,
calendar_version=..., route_version=...)` is the table-side form of the same
check, and `CalendarKeyRef.require_version(route_version=...)` the single-value
form for one call site. The wider install-time validation the whitepaper lists in
§14.2 — topology isomorphism, `selfOff` fill, per-node row coverage,
`expectedRxBytes == expVal`, legal symmetric address / capacity / `opcode`, and
`blockId` in range — is split between `CalendarRouteTable.validate`,
`SymmetricArena.validate_fill` / `check_conservation`, and
`LaunchConstraints.require_block_id`.

## Kickstart

Kickstart is the boundary between the load tier and the run tier. `Loader.kickstart()`
models its preconditions and effects: it sets `PC = entry`, sets the stack pointer,
and invalidates (and optionally preloads) I$ and D$, and it **moves no data**. After
kickstart the host can no longer intervene; everything that follows is on-die
autonomy.

This matters for Calendar because it is where the `blockId` source is fixed
(open item `C-7`): under the adopted reading, `block_idx` is written to an SPR at
kickstart so the runtime route lookup costs zero loads.
`LaunchConstraints.block_id_cost(from_spr=...)` reports both paths: the SPR costs
0 loads and keeps the value A-class; the kernel argument costs 1 load and makes it
B-class.

## The launch-boundary drain rule (`SW-1`)

`SW-1` is the rule that **all Calendar traffic on the die has drained before a
launch boundary**. The host enforces it by inserting a barrier between phases. It
is not an optimisation: cross-launch isolation of `collectionEpoch` depends on it
entirely. The epoch counter lives on a kernel-local object and resets every launch
(under the adopted `C-5` reading), so a stranded copy from the previous launch
under the same `{opcode, epoch}` would be counted by the new launch's receive
command and `expVal` could be met early.

Three pieces model it:

- `wse_model.noc.calreg.StopTheWorldWindow` tracks a node's in-flight transfer
  count. `enter(count)`, `drain(count)`, `drained`, and
  `require_drained(action=...)` are the whole interface; `require_drained` raises
  `CalendarError` when traffic is still in flight.
- `wse_model.noc.network.Noc.drained` is the conjunction of every node's window.
  `Noc.send` charges each hop against every node's window, and `Noc.install_calreg`
  refuses to install unless the whole die is drained. `run_allgather` drains the
  round's transfers in Step5, so a completed phase leaves the die idle again.
- `LaunchConstraints.require_phase_barrier(drained=...)` is the scheduling-level
  form: it raises when a launch boundary is attempted with traffic in flight.
  `Loader.install_calreg` and `Loader.launch` both check the same property.

`tests/integration/test_ffn_allgather.py::test_launch_boundary_drain_is_observable`
and `tests/unit/test_noc.py::test_launch_boundary_requires_a_drained_die` cover it.

## Other scheduling constraints

Whitepaper §12.3 lists four constraints the runtime must honour.
`LaunchConstraints` implements all four as fail-closed checks, and `Scheduler`
tracks them across a sequence of launches:

| Constraint | `LaunchConstraints` method | Failure mode |
| --- | --- | --- |
| schedule by complete group; a wave must not split a syncing group | `check_wave(waves=..., groups=...)` | a split group can never satisfy its rendezvous |
| insert a barrier at the phase boundary (`SW-1`) | `require_phase_barrier(drained=...)` | the previous launch's stragglers are counted into this launch's epoch |
| write `CalReg` only inside a stop-the-world window | `require_calreg_window(in_flight=...)` | a rewrite races traffic in flight |
| provide `blockId` in range | `require_block_id(block_id=..., node_count=...)` | the route-table node index is out of range |

`Scheduler.schedule(waves=..., drained=...)` applies the barrier and wave checks
and counts launches.

The runtime must **not** pre-create `collectionEpoch` and must **not** allocate a
notify counter. The Host cannot see the round number inside a kernel; each round's
epoch comes from the core's own counter.

## What is and is not modelled

| Symbol | What it does | What it does not do |
| --- | --- | --- |
| `RuntimeTier`, `DispatchChain`, `dispatch_chains()` | name the tiers and the four chains with destinations and exclusions | do not move bytes |
| `VersionSet.check` | three-way version fault | is not wired to a device read |
| `Loader` / `InstallState` | models the load sequence and its preconditions | no transport, no real device, no timing |
| `LaunchConstraints` / `Scheduler` | enforce the four scheduling constraints | no wave construction or load balancing |
| `Noc.drained`, `StopTheWorldWindow` | model die-wide quiescence | no launch boundary of their own |
| `CalRegImage.install_into` | installs the die-wide image if every node is drained | no transport, no version check |

Everything else in this page — the actual PCIe transfer, the task queue, the
device-side install — is documented design intent. See the
[roadmap](../roadmap.md).

## Open items that gate a fuller runtime model

| Item | Why it blocks |
| --- | --- |
| `C-5` | the `epochTag` width / wraparound policy and the cross-launch counter convention; `SW-1` is only sufficient under the adopted "per-launch from 1, drain before wrap" reading |
| `C-6` | whether the epoch is implicit receive-side context or an explicit send operand, which changes the launch-time interface |
| `C-7` | `blockId` acquisition (SPR vs kernel argument), which decides the args surface and the cost of the route lookup |
| `Q12` / `C-11` | the degradation path for a faulty core or link; if topology is not guaranteed isomorphic, the table degrades to a load-time buffer and the loader gains a per-instance recomputation |
| `S-3`, `S-4` | the machine encoding of the symmetric address and the instruction mnemonics |
| `S-5` | the send `sid` semantics and the report instruction's pipe operand, which decide whether a barrier before Step4 can be elided |
| `Q3`, `Q9` | Batcher dispatch time and the device round-trip, which set the per-launch fixed cost |

## See also

- [Decision 0001](../decisions/0001-adopt-calendar-baseline-defaults.md) for the
  adopted readings of `C-5`, `C-6`, and `C-7`.
- [Calendar and NoC](calendar-noc.md) for `CalReg` and the epoch model.
- [Batcher and UB bus](batcher-ub.md) for the dispatch chains' interconnect.
