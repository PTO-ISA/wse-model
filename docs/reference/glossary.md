# Glossary

Terminology from whitepaper Appendix B and the Calendar glossary, plus the code
symbol that implements each term. Where a term is design context that the model
does not implement, the last column says so rather than inventing a symbol.

The design documents are written in Chinese; this table uses the English term and
gives the Chinese term where the documents use one consistently.

## System and hardware

| Term | Meaning | Implementing symbol |
| --- | --- | --- |
| **AICORE** | the WSE compute core: one Cube + one Vector at 1.4 GHz | `wse_model.analysis.platform.AicoreSpec`; `wse_model.core`; `TopologyProfile.aicore_nodes` |
| **Batcher** | the only bridge between the external world and the AICORE array; contains `Batcher.mem` | `wse_model.host.batcher.BatcherMem`, `BatcherResponsibility`, `dispatch_paths()` |
| **UB (Unified Buffer)** | the 384 KB on-chip Vector workspace | `wse_model.core.buffers.BufferKind.UB`, `ON_CHIP_BUFFERS["UB"]` |
| **UB bus** | the external interconnect, 8 fabric lanes + 1 host lane | `wse_model.host.ub_bus.UbBus`, `UbLane`, `FABRIC_LANES`, `HOST_LANES` |
| **local DRAM** | per-AICORE private memory, 384 MB at 1 TB/s, 2 KB page | `wse_model.core.dram.LocalDram`, `LocalDramLayout` |
| **Cube / Vector / FixPipe** | the compute pipes; Cube `M×K×N` per cycle, Vector 256 B/cycle | `wse_model.core.pipelines.Pipe`, `wse_model.core.cube.MatmulTiming`, `VectorTiming` |
| **MTE1–MTE4** | the memory pipes; MTE3 is the inter-core send path, MTE4 the receive accounting | `wse_model.core.pipelines.Pipe.MTE1` … `Pipe.MTE4`, `INDEPENDENT_FROM_MTE4` |
| **Davinci** | the host accelerator WSE serves as a coprocessor | not modelled; interface is open item `Q9` |
| **WSE-Lite** | the deployable WSE instance (two per decode step in the design) | `TopologyProfile` chooses a profile; instance count is `Q10` |
| **PTO / PTO-ISA** | Parallel Tile Operation, the tile-level virtual ISA | not modelled; owned by `PTO-ISA/pto-spec` |
| **Bisheng** | the compiler that lowers CCE to Davinci binaries | not modelled |
| **BSP** | the hardware/firmware entity that aligns each group's time origin | modelled in effect by `AlignmentDomain` and `LaunchConstraints`; no BSP object |
| **Reticle** | the die boundary; the model assumes a single synchronous reticle | `TopologyProfile`; multi-reticle is open item `Q2` |
| **PG** | partial-good information: which cores and links are usable | not modelled; degradation is `Q12` / `C-11` |

## Calendar encoding

| Term | Meaning | Implementing symbol |
| --- | --- | --- |
| **Calendar** | the scheme that moves path and timeslot decisions to compile time | `wse_model.calendar`, `wse_model.noc` |
| **`routeBits`** | the `2 × node_count` bit path bitmap, one `{P, L}` pair per node | `wse_model.calendar.route_bits.RouteBits` |
| **`{P, L}` pair** | `00` absent / `10` pass / `11` land-and-pass / `01` illegal | `wse_model.calendar.route_bits.BitPair` |
| **induced subgraph** | the `{P=1}` nodes with *every* physical link between them counted | `MeshTopology.induced_edges`, `validate.check_induced_tree`, `TreeAnalysis` |
| **reduction point** | a node with pair `11` and a downstream `P` neighbour, where a merge happens | no dedicated type; computed in `simulate_multicast` and reported by `BitPair.LAND` |
| **`opcode`** | the 3 bit timeslot-register index, determined by collective semantics | `calendar.collective.Collective`, `OPCODE_WIDTH_BITS`, `OPCODE_RESERVED` |
| **`redOp`** | the 3 bit reduction operator carried in the flit header | `calendar.collective.RedOp` |
| **reduction element type** | the missing 3 bit `vtype_t` field that `redOp` alone cannot supply | `calendar.collective.ReductionElementType` (name gated on `C-3`) |
| **`CalReg`** | the resident NoC timeslot register, indexed by `opcode` | `wse_model.noc.calreg.CalRegBank`, `CalRegSlot`, `CalRegImage` |
| **`keyId`** | the static table's key-dimension index | `calendar.key.CalendarKeyRef.key_id`, `CalendarKeyRegistry` |
| **`blockId`** | this core's NoC node number; the only runtime-varying index | used by `CalendarRouteTable.entry_index`; acquisition is `C-7` |
| **logical identity (`RouteKey`)** | `{programId, kernelId, phaseId, collective, groupRole}` | `calendar.key.RouteKey`, `GroupRole` |
| **`CalendarKeyRef`** | the indivisible constant pair `{keyId, opcode, redOp, routeVersion}` | `calendar.key.CalendarKeyRef` |
| **`CalendarRouteEntry`** | the 16 B `.rodata` entry: `routeBits[10] + landCount + flags + expectedRxBytes` | `calendar.entry.CalendarRouteEntry` |
| **`CalendarRouteRegs`** | the by-value register-pair view `{rbLo, rbHi}` | `calendar.entry.CalendarRouteRegs` (the design's own name, §5.8) |
| **`kCalendarRoute[key][node]`** | the static table, 16 B per entry, 64 B aligned | `calendar.table.CalendarRouteTable`, `KeyDefinition`, `TableLayout` |
| **`landCount`** | `popcount(L)`: this send's number of land nodes | `CalendarRouteEntry.land_count`, `CalendarRouteRegs.land_count` |
| **`selfLand`** | `flags.bit2`: whether the fabric lands the source's own copy | `RouteEntryFlags.SELF_LAND`, `CalendarRouteEntry.self_land` |
| **symmetric receive arena** | every member's `recvTile` at the same local offset | `calendar.geometry.SymmetricArena`, `ArenaSegment` |
| **`selfOff`** | a source's segment offset inside each arena row | `SymmetricArena.self_off`, `ArenaSegment.offset` |
| **`expVal`** | the expected remote valid payload bytes; the completion test | `PayloadGeometry.exp_val`, `ReceiveAccount.exp_val` |
| **`capacity`** | the receive range's byte capacity | `PayloadGeometry.capacity`, `ReceiveAccount.capacity` |
| **`collectionEpoch`** | the per-round receive identity that carries the discrimination duty | `calendar.epoch.EpochCounter`, `RecvContext`, `ReceiveAccount.epoch` |
| **`CalendarNextEpoch`** | the core-local per-`opcode` round counter | `calendar.epoch.EpochTracker.next_epoch` |
| **`flagId`** | the cross-core semaphore id that `opcode` doubles as | `calendar.collective.AlignmentDomain` (the `opcode` is the id) |
| **`nBurst` / `lenBurst`** | the reused align-DMA row count and bytes per row | `PayloadGeometry.n_burst`, `PayloadGeometry.row_bytes` |
| **`CalendarRouteEntry.flags`** | `isMember` / `isRoot` / `selfLand` | `calendar.entry.RouteEntryFlags` |

## Collectives, delivery, and runtime

| Term | Meaning | Implementing symbol |
| --- | --- | --- |
| **`MTE3_NOC_SEND`** | the send form: source tile, symmetric destination, bitmap, opcode, `redOp` | `noc.network.SendPlan`, `Noc.send` |
| **`MTE4_NOC_RECV_WAIT`** | the receive/accounting form; it moves no bytes | `calendar.receive.ReceiveAccount`, `CoreIngress` |
| **`Batcher.mem`** | the shared staging and cache-refill level | `host.batcher.BatcherMem`, `RefillAccount` |
| **A / B / C value classes** | by dispatch time: with the binary / per launch / device-produced | `host.runtime.DispatchChain` and `RuntimeTier` are the nearest model; there is no dedicated type |
| **immediate channel** | a compile-time constant that folds into `.text` and travels in I-cache | no dedicated symbol; realised by `CalendarKeyRef` and the CLI immediates |
| **`.rodata` channel** | a compile-time constant indexed by a runtime variable, so it is materialised | `calendar.table`, `analysis.dcache.RouteTableResidency` |
| **arm lead time** | the window after alignment for the receive command and send descriptors to enqueue | `CalRegSlot.arm_lead_cycles`, `KeyDefinition.arm_lead_cycles` |
| **`conflictProof`** | the NoC algorithm's proof that the same-`opcode` timing guarantees hold | `KeyDefinition.conflict_proof`, `ValidationReport` warning `V-CONFLICT-PROOF-MISSING` |
| **invariant `O1`** | route and timeslot must come from the same logical identity | `CalendarKeyRegistry` (the software substitute for the missing hardware anchor) |
| **invariant `O3`** | post the receive before sending; drain sends before waiting | `run_allgather`, `PipeTracker.check_no_deadlock` |
| **invariant `E1`** | members of one `opcode` domain call the collective identically | `EpochTracker.assert_spmd_consistent` |
| **`SW-1`** | all Calendar traffic has drained before a launch boundary | `StopTheWorldWindow`, `Noc.drained`, `LaunchConstraints.require_phase_barrier` |
| **F1 / F2 / F3** | the compiled-product prohibitions: no writable Calendar state, no materialised key ref, a read-only 64 B-aligned table | `compiler.selfcheck.check_compiled_product` |
| **A-class table** | the emitted `.rodata` route table, a load-time constant | `calendar.table.CalendarRouteTable.to_bytes`, `to_dict` |

## See also

- [Calendar and NoC](../architecture/calendar-noc.md) for the rules behind the
  encoding terms.
- [Runtime and loading](../architecture/runtime.md) for the delivery terms.
- [Descriptors and schemas](descriptors.md) for the field names in the JSON.
