# Calendar closure requirements

These are the normative, implemented, and tested requirements of the Calendar/NoC
closure. Every one holds in the current tree and names the test that proves it.
They are grouped by the part of the scheme they constrain, and each cites the
design section it comes from.

Scope: `WSEMODEL-CAL-*` covers `routeBits`, the `CalendarRouteEntry`, `keyId` /
`opcode` / `redOp` / identity, alignment and epochs, the §2.7.2 validation set,
flit formatting, forwarding, `CalReg`, landing geometry, the seven `expVal`
contracts, the FFN AllGather closure and its integration with the loader and
scheduler, the table layouts and schemas, the compiled-product self-checks and
deployment package, the D-cache budget, and the AICORE/host models. It does **not**
cover the compiler frontend (IR, group recognition, lowering, emission) or the
ACIR layer, because those are not implemented; see the [roadmap](../roadmap.md).

Proof command: `make check` runs `python -m pytest tests/unit -m unit` and
`python -m pytest tests/contracts -m contract`. The closure also has an
integration lane, `make integration`, and a frozen lane, `python -m pytest
tests/golden`, run by the `design-fidelity` CI job.

## A. `routeBits` encoding (Calendar §2.2, §2.2.1)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-001` | The `{P, L}` bit order is `routeBits[2i+1] = P_i` and `routeBits[2i] = L_i`, with bit `b` in byte `b // 8` at position `b % 8` (LSB first). | Calendar §2.2 | `tests/unit/test_route_bits.py::test_golden_vector_byte_layout_is_lsb_first` |
| `WSEMODEL-CAL-002` | The four pair encodings are `00` absent, `10` pass, `11` land-and-pass, and `01` illegal (`L=1` with `P=0`). | Calendar §2.2 | `tests/unit/test_route_bits.py::test_bit_pair_uses_low_bit_for_land_and_high_bit_for_pass` |
| `WSEMODEL-CAL-003` | The checked constructor rejects any land node that is not also a pass node, because that is the illegal `01` pair. | Calendar §2.2 | `tests/unit/test_route_bits.py::test_from_sets_rejects_a_land_node_that_does_not_pass` |
| `WSEMODEL-CAL-004` | Raw byte decoding preserves an illegal `01` pair instead of repairing it; rejection is the validator's job. | Calendar §2.2, §2.7.2 | `tests/unit/test_route_bits.py::test_from_bytes_preserves_illegal_pairs_for_validation` |
| `WSEMODEL-CAL-005` | The bitmap is `2 × node_count` bit, so 40 nodes give 10 B and 48 nodes give 12 B, and decoding requires exactly that byte length. | Calendar §2.2; open item `Q1` | `tests/unit/test_route_bits.py::test_width_scales_with_the_node_count` |
| `WSEMODEL-CAL-006` | The §2.2.1 consistency anchor decodes to pass `{N00, N01, N02, N03, N04, N10, N18, N19}`, land `{N04, N19}`, hex `AA 03 20 00 E0 00 00 00 00 00`. | Calendar §2.2.1 | `tests/unit/test_route_bits.py::test_golden_vector_matches_the_published_bytes` |
| `WSEMODEL-CAL-007` | The FFN `keyId 0` row `FE FF 00 …` and `keyId 1` row `02 00 03 00 03 00 03 00 00 00` are frozen. | Calendar §2.2.1 | `tests/golden/test_golden_vectors.py::test_ffn_key_encodings_are_unchanged` |

## B. The 16 B `CalendarRouteEntry` (Calendar §1.7, §2.6, §4.4.4)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-008` | At 40 nodes an entry occupies exactly 16 B, one GPR pair, and the bitmap-plus-tail layout admits at most 40 nodes. | Calendar §2.6 | `tests/unit/test_route_bits.py::test_entry_is_one_gpr_pair_at_40_nodes` |
| `WSEMODEL-CAL-009` | `rbLo` carries nodes 00–31; `rbHi[15:0]` carries nodes 32–39, `[23:16]` `landCount`, `[31:24]` `flags`, `[63:32]` `expectedRxBytes`; only `rbHi[15:0]` routes. | Calendar §1.7, §2.6, §4.4.4 | `tests/unit/test_route_bits.py::test_entry_register_pair_field_boundaries` |
| `WSEMODEL-CAL-010` | A declared `landCount` that disagrees with `popcount(L)` is rejected; the field exists only for cross-checking. | Calendar §2.6 | `tests/unit/test_route_bits.py::test_entry_rejects_a_land_count_that_disagrees_with_popcount` |
| `WSEMODEL-CAL-011` | `expectedRxBytes` must fit the entry's `uint32` field. | Calendar §2.6; open item `S-1` | `tests/unit/test_route_bits.py::test_entry_rejects_expected_rx_bytes_beyond_uint32` |
| `WSEMODEL-CAL-012` | A 48-node entry needs 18 B and cannot be emitted in the 16 B one-GPR-pair layout; the model raises rather than widen it. | Calendar §2.6; open item `Q1` | `tests/unit/test_route_bits.py::test_48_node_entry_cannot_fit_the_gpr_pair_layout` |
| `WSEMODEL-CAL-013` | The source's own `L` bit must equal `FabricSelfDelivery`; a disagreement means the local segment is missed or written twice. | Calendar §2.7.2; `HW-10` | `tests/unit/test_validate.py::test_self_land_bit_must_match_the_platform_trait` |

## C. Opcode, `redOp`, and logical identity (Calendar §2.3, §2.4, §2.5)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-014` | `opcode` is 3 bit; codes 0 and 7 are reserved and must fault; `AllGather` is 1 and `Reduce` is 2. | Calendar §2.3 | `tests/unit/test_calendar_semantics.py::test_opcode_is_three_bits_and_zero_seven_are_reserved` |
| `WSEMODEL-CAL-015` | The first phase implements `AllGather` and `Reduce` only; the other four semantics are reserved code points. | Calendar §2.3 | `tests/unit/test_calendar_semantics.py::test_only_allgather_and_reduce_are_implemented_in_the_first_phase` |
| `WSEMODEL-CAL-016` | A reduction collective requires a `redOp`; a copy collective requires `RedOp.NONE`, because the field is dormant. | Calendar §2.4 | `tests/unit/test_calendar_semantics.py::test_key_ref_requires_red_op_exactly_for_reductions` |
| `WSEMODEL-CAL-017` | The reduction element type field is carried as a raw 3 bit code but its `vtype_t` name is gated on open item `C-3` and fails closed. | Calendar §2.4; open item `C-3` | `tests/unit/test_calendar_semantics.py::test_reduction_element_type_carries_the_code_but_refuses_to_name_it` |
| `WSEMODEL-CAL-018` | A logical identity is assigned one stable `keyId`, and re-registering the same identity is idempotent. | Calendar §2.5 | `tests/unit/test_calendar_semantics.py::test_registry_assigns_stable_key_ids` |
| `WSEMODEL-CAL-019` | Invariant `O1`: one identity maps to exactly one `(keyId, opcode)` pair, and a `keyId` never maps to two identities. | Calendar §2.5, §1.4 | `tests/unit/test_calendar_semantics.py::test_registry_defends_invariant_o1` |
| `WSEMODEL-CAL-020` | The table is capped at 16 logical identities; a 17th registration is refused. | Calendar §2.6, §3.8.4 | `tests/unit/test_calendar_semantics.py::test_registry_enforces_the_key_budget` |
| `WSEMODEL-CAL-021` | A `CalendarKeyRef` may not carry a reserved `opcode`. | Calendar §2.3, §2.5 | `tests/unit/test_calendar_semantics.py::test_key_ref_rejects_a_reserved_opcode` |
| `WSEMODEL-CAL-022` | A `CalendarKeyRef` whose `routeVersion` disagrees with the loaded table faults rather than degrading. | Calendar §2.5; whitepaper §10.3 | `tests/unit/test_calendar_semantics.py::test_key_ref_version_check_faults_on_mismatch` |

## D. Alignment and `collectionEpoch` (Calendar §1.5, §4.2, §4.5.2)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-023` | The alignment domain is partitioned by `opcode`, and the existing semaphore field is 4 bit by default (capacity 15). | Calendar §1.5, §4.2 | `tests/unit/test_calendar_semantics.py::test_alignment_domain_capacity_is_four_bits_by_default` |
| `WSEMODEL-CAL-024` | `HW-7` requires at least `ceil(log2(members + 1))` bits; 32 members and 40 members both need 6 bit. | Calendar §4.2; `HW-7` | `tests/unit/test_calendar_semantics.py::test_alignment_domain_width_requirement_matches_hw7` |
| `WSEMODEL-CAL-025` | An arrival count that overflows the semaphore faults instead of wrapping. | Calendar §4.2; `HW-7` | `tests/unit/test_calendar_semantics.py::test_alignment_domain_faults_on_wraparound` |
| `WSEMODEL-CAL-026` | The per-`opcode` round counter starts at 1, and the value before the first round is 0. | Calendar §1.5 | `tests/unit/test_calendar_semantics.py::test_epoch_counter_starts_at_one` |
| `WSEMODEL-CAL-027` | Wraparound is legal only once the previous epoch's traffic has drained; otherwise it faults. | Calendar §4.5.2 contract 7; open item `C-5` | `tests/unit/test_calendar_semantics.py::test_epoch_counter_wraparound_requires_a_drain` |
| `WSEMODEL-CAL-028` | `epochTag` is a declared parameter in the proposed 8–16 bit range; a width outside it is rejected. | Calendar §1.8; open item `C-5` | `tests/unit/test_calendar_semantics.py::test_epoch_tag_width_is_bounded_by_the_open_item_range` |
| `WSEMODEL-CAL-029` | Invariant `E1`: members of one `opcode` domain must report the same epoch; a divergent peer is detected and raises. | Calendar §1.4, §1.5 | `tests/unit/test_calendar_semantics.py::test_tracker_detects_spmd_divergence` |
| `WSEMODEL-CAL-030` | The receive context is discriminated by `{opcode, epoch}` and carries the AICORE / kernel / stream isolation identity. | Calendar §4.5; `HW-5` | `tests/unit/test_calendar_semantics.py::test_recv_context_key_is_opcode_and_epoch` |

## E. The §2.7.2 structural check set (Calendar §2.7.2)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-031` | An illegal `01` pair is reported as an error naming the offending node. | Calendar §2.7.2 | `tests/unit/test_validate.py::test_illegal_bit_pair_is_reported_with_its_node` |
| `WSEMODEL-CAL-032` | The source must have `P=1` so the flit starts on its own path. | Calendar §2.7.2 | `tests/unit/test_validate.py::test_source_must_have_p_set` |
| `WSEMODEL-CAL-033` | A simple induced path is accepted as a tree, and the reached set is exactly the path. | Calendar §2.2, §2.7.2 | `tests/unit/test_validate.py::test_a_simple_path_is_a_tree` |
| `WSEMODEL-CAL-034` | A 2×2 block of `P=1` nodes is rejected as cyclic, because the induced subgraph contains all four links. | Calendar §2.2, §2.7.2 | `tests/unit/test_validate.py::test_a_two_by_two_block_is_rejected_as_cyclic` |
| `WSEMODEL-CAL-035` | A disconnected `{P=1}` induced subgraph is rejected, because unreached land nodes would never receive the flit. | Calendar §2.7.2 | `tests/unit/test_validate.py::test_a_disconnected_induced_subgraph_is_rejected` |
| `WSEMODEL-CAL-036` | Adjacency is *induced*: two adjacent `P=1` nodes share a live link whether or not the algorithm intended it. | Calendar §2.2 | `tests/unit/test_noc.py::test_induced_edges_include_unintended_adjacency` |
| `WSEMODEL-CAL-037` | The land set must equal the semantics' destination set, and `landCount` must equal `popcount(L)`. | Calendar §2.7.2 | `tests/unit/test_validate.py::test_land_set_completeness_and_land_count` |
| `WSEMODEL-CAL-038` | For every destination, the land-set sum must equal the entry's `expectedRxBytes`, which is the device-side `expVal`. | Calendar §2.7.2, §2.8 | `tests/unit/test_validate.py::test_table_conservation_is_checked_against_the_declared_rx_bytes` |
| `WSEMODEL-CAL-039` | `keyCount` must not exceed 16, and the per-core D-cache residency must stay within budget. | Calendar §3.8.4 | `tests/unit/test_validate.py::test_budget_rejects_more_than_sixteen_keys` |
| `WSEMODEL-CAL-040` | A key must have exactly one row per topology node; the table is emitted for all nodes with no per-core pruning. | Calendar §2.5, §2.7.3 | `tests/unit/test_validate.py::test_table_rejects_a_row_count_that_does_not_cover_every_node` |
| `WSEMODEL-CAL-041` | The entry-layout guard reports the 48-node case as unemittable, naming open item `Q1`. | Calendar §2.6; open item `Q1` | `tests/unit/test_validate.py::test_entry_layout_guard_flags_the_48_node_case` |

## F. Flit format and forwarding (Calendar §1.8, §2.2)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-042` | The per-flit header is 12 B at 40 nodes (10 B `routeBits` + 1 B `opcode`/`redOp` + 1 B `epochTag`), i.e. 18.75% of a 64 B link. | Calendar §1.8; whitepaper §5.4 | `tests/unit/test_noc.py::test_header_is_twelve_bytes_at_40_nodes` |
| `WSEMODEL-CAL-043` | When a byte run is split into flits, the same header is replicated on every flit and the last flit is padded to the link width. | Calendar §1.8 | `tests/unit/test_noc.py::test_split_payload_replicates_the_header_and_pads_the_tail` |
| `WSEMODEL-CAL-044` | Forwarding follows the bitmap: `L=1` lands, and egress is the `P=1` neighbours minus the ingress port. | Calendar §2.2 | `tests/unit/test_noc.py::test_forwarding_follows_the_bitmap_path` |
| `WSEMODEL-CAL-045` | A flit is never sent back out of the port it arrived on. | Calendar §2.2 | `tests/unit/test_noc.py::test_forwarding_never_includes_the_ingress_port` |
| `WSEMODEL-CAL-046` | A cyclic induced subgraph is reported as duplicate landings and unexpanded revisits, not as a non-terminating simulation. | Calendar §2.2; §4.5.2 contract 5 | `tests/unit/test_noc.py::test_a_cycle_is_reported_as_duplicate_landings_not_an_infinite_loop` |

## G. `CalReg` residency (Calendar §3.9)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-047` | A node installs and indexes one resident slot per `opcode`; `CalReg[opcode]` returns the installed content. | Calendar §3.9 | `tests/unit/test_noc.py::test_calreg_install_and_lookup` |
| `WSEMODEL-CAL-048` | A reserved code (`0`, `7`) or an uninstalled code faults; there is no default entry. | Calendar §2.3, §3.9 | `tests/unit/test_noc.py::test_calreg_rejects_reserved_and_uninstalled_opcodes` |
| `WSEMODEL-CAL-049` | The die-wide image installs byte-identically into every node, and each node keeps its own bank. | Calendar §2.7.3 step 5, §3.9 | `tests/unit/test_noc.py::test_calreg_image_installs_into_every_node_atomically` |
| `WSEMODEL-CAL-050` | A `CalReg` install is refused while any node has Calendar traffic in flight. | Calendar §3.9; whitepaper §12.3 | `tests/unit/test_noc.py::test_calreg_install_requires_a_drained_die` |

## H. Landing geometry (Calendar §2.8, §4.4.6)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-051` | `srcGap`, `dstGap`, `nBurst`, and `capacity` are derived from the tile geometry (`sendRowStride - rowBytes`, `recvRowStride - rowBytes`, `rowCount`, `recvRowCount × recvRowStride`). | Calendar §2.8 | `tests/unit/test_geometry.py::test_gaps_are_derived_from_the_strides` |
| `WSEMODEL-CAL-052` | `recvRowCount` must equal `rowCount`. | Calendar §2.8 | `tests/unit/test_geometry.py::test_recv_row_count_must_match_row_count` |
| `WSEMODEL-CAL-053` | `R-1` is a correctness rule: the send row stride must be a multiple of 32 B, and an unaligned stride is rejected. | Calendar §2.8, §4.4.6 | `tests/unit/test_geometry.py::test_r1_requires_a_32_byte_multiple_source_stride` |
| `WSEMODEL-CAL-054` | `R-2` is efficiency only: `rowBytes` need not be a link-width multiple. | Calendar §4.4.6 | `tests/unit/test_geometry.py::test_r2_row_bytes_need_not_be_a_link_multiple` |
| `WSEMODEL-CAL-055` | `expVal = rowCount × rowBytes × landCount`, with `landCount` counting remote land sources only; the FFN phase B value is 10752 and phase C is 36864. | Calendar §2.8, §2.2.1 | `tests/unit/test_geometry.py::test_exp_val_is_row_count_times_row_bytes_times_land_count` |
| `WSEMODEL-CAL-056` | A packed arena's `selfOff(rank) = rank × rowBytes` and `dst_address(rank, r) = recvSymBase + r × rowStride + selfOff(rank)`. | Calendar §2.8 | `tests/unit/test_geometry.py::test_packed_arena_self_off_is_rank_times_row_bytes` |
| `WSEMODEL-CAL-057` | `A3`: the members' `selfOff` segments must tile every arena row with no gap and no overlap. | Calendar §2.8 | `tests/unit/test_geometry.py::test_a3_requires_a_gapless_tiling_of_every_row` |
| `WSEMODEL-CAL-058` | The land-set byte sum must equal the declared `expectedRxBytes` and must fit the arena capacity. | Calendar §2.7.2, §2.8 | `tests/unit/test_geometry.py::test_conservation_matches_the_entry_expected_bytes` |

## I. The seven `expVal` contracts (Calendar §4.5.2)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-059` | Contract 1: the accounting unit is valid payload bytes; a self-sourced segment is marked non-counting even when `L_self = 1`. | Calendar §4.5.2 contract 1 | `tests/unit/test_receive_contracts.py::test_contract_1_the_unit_is_payload_bytes` |
| `WSEMODEL-CAL-060` | Contract 2: a wrong `opcode`, a wrong epoch, or a write outside `[dst, dst + capacity)` faults rather than being absorbed. | Calendar §4.5.2 contract 2 | `tests/unit/test_receive_contracts.py::test_contract_2_wrong_epoch_faults` |
| `WSEMODEL-CAL-061` | Contract 4: a legal arrival that predates the receive command is buffered and adopted, never lost. | Calendar §4.5.2 contract 4 | `tests/unit/test_receive_contracts.py::test_contract_4_early_arrivals_are_not_missed` |
| `WSEMODEL-CAL-062` | Contract 5: a duplicate segment is not double counted. | Calendar §4.5.2 contract 5 | `tests/unit/test_receive_contracts.py::test_contract_5_duplicate_segments_are_not_double_counted` |
| `WSEMODEL-CAL-063` | Contract 5: multicast copies are de-duplicated per land point, so two paths reaching one core count once. | Calendar §4.5.2 contract 5; `HW-15` | `tests/unit/test_receive_contracts.py::test_contract_5_multicast_copies_dedupe_per_land_point` |
| `WSEMODEL-CAL-064` | Contract 6: an `expVal` greater than `capacity` faults rather than blocking forever. | Calendar §4.5.2 contract 6 | `tests/unit/test_receive_contracts.py::test_contract_6_exp_val_above_capacity_faults` |
| `WSEMODEL-CAL-065` | Contract 7: the epoch must be unique within its `opcode` domain; two active receives for one `{opcode, epoch}` fault. | Calendar §4.5.2 contract 7 | `tests/unit/test_receive_contracts.py::test_contract_7_two_active_receives_for_one_epoch_fault` |
| `WSEMODEL-CAL-066` | A receive for a reserved `opcode` faults. | Calendar §2.3, §4.5.2 | `tests/unit/test_receive_contracts.py::test_reserved_opcode_receive_faults` |
| `WSEMODEL-CAL-067` | A receive command cannot be retired until it is complete. | Calendar §4.5 | `tests/unit/test_receive_contracts.py::test_retire_requires_completion` |

## J. The AllGather closure (Calendar §1.2, §17.2)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-068` | The FFN two-phase AllGather completes on every one of the 32 member cores, with phase B at 10752 B and phase C at 36864 B. | Calendar §2.2.1, §2.8 | `tests/integration/test_ffn_allgather.py::test_ffn_two_phase_allgather_completes_on_every_member` |
| `WSEMODEL-CAL-069` | Both FFN phases share `opcode 1`, so the core counters yield epoch 1 and then epoch 2. | Calendar §1.5, §2.3.1 | `tests/integration/test_ffn_allgather.py::test_shared_opcode_domain_advances_the_epoch_across_phases` |
| `WSEMODEL-CAL-070` | Every member of a row group receives exactly from the other seven, i.e. `8 × 192 × 7` bytes. | Calendar §2.2.1 | `tests/integration/test_ffn_allgather.py::test_every_member_of_a_row_group_receives_from_the_other_seven` |
| `WSEMODEL-CAL-071` | The phase report exposes tree depth and header cost, with header bytes strictly between zero and the wire volume. | Calendar §1.8 | `tests/integration/test_ffn_allgather.py::test_the_phase_reports_the_header_cost_and_tree_depth` |
| `WSEMODEL-CAL-072` | After a completed phase the die is drained again, which is the `SW-1` precondition. | Calendar §1.5; whitepaper §12.3 | `tests/integration/test_ffn_allgather.py::test_launch_boundary_drain_is_observable` |
| `WSEMODEL-CAL-073` | Running a phase with no `CalReg` image installed faults before any send. | Calendar §3.9 | `tests/integration/test_ffn_allgather.py::test_running_a_phase_without_installed_calreg_faults` |
| `WSEMODEL-CAL-074` | The closure refuses to model any reduction collective until the reduction semantics of open item `C-10` are defined. | Calendar §2.4, §6.3 `C-10` | `tests/integration/test_ffn_allgather.py::test_the_closure_refuses_to_model_reduce` |
| `WSEMODEL-CAL-075` | Every FFN member source's bitmap is a clean tree walk that lands exactly its group minus itself. | Calendar §2.2, §2.7.2 | `tests/integration/test_ffn_allgather.py::test_the_ffn_row_bitmaps_are_valid_trees` |

## K. Table layouts and the route-table schema (Calendar §3.8.3, §3.8.4)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-076` | Node-major residency is `ceil(keyCount / 4)` lines versus `keyCount` for key-major, a 4× reduction at the 16-key budget. | Calendar §3.8.3; open item `C-9` | `tests/unit/test_validate.py::test_node_major_layout_uses_four_times_fewer_lines` |
| `WSEMODEL-CAL-077` | Both layouts emit the same 16 B entries and the same total bytes, differing only in order; the FFN is 2 lines key-major and 1 line node-major. | Calendar §3.8.3 | `tests/contracts/test_table_schema.py::test_both_layouts_emit_the_same_bytes_in_a_different_order` |
| `WSEMODEL-CAL-078` | The FFN table is 2 × 40 × 16 B = 1280 B with two 64 B D-cache lines per core (128 B). | Calendar §3.8.4 | `tests/golden/test_golden_vectors.py::test_ffn_table_footprint_matches_the_document` |
| `WSEMODEL-CAL-079` | The serialised table carries the frozen schema name `wse-model/calendar-route-table/1`, and an unknown schema is rejected. | Calendar §2.6 | `tests/contracts/test_table_schema.py::test_route_table_schema_name_is_frozen` |
| `WSEMODEL-CAL-080` | The serialised table always contains the required top-level, key, and entry fields. | Calendar §2.6 | `tests/contracts/test_table_schema.py::test_route_table_required_fields_are_present` |
| `WSEMODEL-CAL-081` | The emitted table validates against `schemas/calendar-route-table.schema.json`. | Calendar §2.6 | `tests/contracts/test_table_schema.py::test_emitted_table_validates_against_the_published_schema` |
| `WSEMODEL-CAL-082` | Both readings of open item `Q1` are first-class profiles: 5×8 with 40 AICOREs and 6×8 with 48. | Whitepaper Appendix A `Q1` | `tests/unit/test_noc.py::test_the_whitepaper_hardware_profile_has_48_nodes` |

## L. Compiled-product self-checks and the D-cache budget (Calendar §3.8, §3.10)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-083` | F1: no writable Calendar static state may appear in `.data` or `.bss`; a writable `CalendarChannel` is a race under SPMD and is rejected. | Calendar §3.10 (F1) | `tests/unit/test_compiler_selfcheck.py::test_f1_rejects_a_writable_calendar_symbol` |
| `WSEMODEL-CAL-084` | F2: a `CalendarKeyRef` constant must not be materialised, because taking its address demotes `opcode` from an I-cache immediate to a D-cache load. | Calendar §3.10 (F2) | `tests/unit/test_compiler_selfcheck.py::test_f2_rejects_a_materialized_key_ref` |
| `WSEMODEL-CAL-085` | F3: `kCalendarRoute` must be a read-only object in a 64 B-aligned `.rodata` section of exactly `keyCount × nodeCount × 16` bytes. | Calendar §2.6, §3.10 (F3) | `tests/unit/test_compiler_selfcheck.py::test_f3_requires_64_byte_rodata_alignment` |
| `WSEMODEL-CAL-086` | The declared kernel-object manifest carries the frozen schema `wse-model/kernel-object/1` and the example manifest validates against the published JSON Schema. | Calendar §3.10 | `tests/unit/test_compiler_selfcheck.py::test_the_example_manifest_validates_against_the_published_schema` |
| `WSEMODEL-CAL-087` | The FFN route table residents 2 D-cache lines (128 B) per core key-major and 1 line (64 B) node-major. | Calendar §3.8.4 | `tests/unit/test_analysis.py::test_ffn_d_cache_residency_matches_the_document` |
| `WSEMODEL-CAL-088` | Die-wide, the FFN table occupies 20 distinct lines and generates 80 refill requests, of which only 20 reach DDR and 60 are served by the shared `Batcher.mem`. | Calendar §3.8.4 | `tests/unit/test_analysis.py::test_die_wide_line_count_and_refill_split` |
| `WSEMODEL-CAL-089` | The node-major transpose halves the FFN refill requests (80 to 40) without changing the bytes or instructions. | Calendar §3.8.3 | `tests/unit/test_analysis.py::test_node_major_halves_the_refill_requests_at_keycount_two` |
| `WSEMODEL-CAL-090` | The inherent amplification is the entry-to-line ratio, 4× (four 16 B entries per 64 B line); the FFN table occupies 0.7812% of a 256-line D-cache. | Calendar §3.8.3 | `tests/unit/test_analysis.py::test_amplification_is_the_entry_to_line_ratio` |

## M. Core pipes, host dispatch, and open-item gates (Calendar §4.7; whitepaper §6, §12)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-091` | The pipe set matches the design: `PIPE_S`, `PIPE_MTE1..4`, `PIPE_M`, `PIPE_V`, `PIPE_FIX`. | Whitepaper §9.1; Calendar §4.1 | `tests/unit/test_core.py::test_the_pipe_set_matches_the_design` |
| `WSEMODEL-CAL-092` | `SCALAR` and `PIPE_MTE3` stay dispatchable while a `PIPE_MTE4` wait is unsatisfied, so the collective cannot deadlock (invariant `O3`). | Calendar §4.7 | `tests/unit/test_core.py::test_mte3_and_scalar_stay_dispatchable_while_mte4_waits` |
| `WSEMODEL-CAL-093` | A `PIPE_MTE3` barrier may return only once the queued sends have actually been sent. | Calendar §4.7 | `tests/unit/test_core.py::test_the_mte3_barrier_must_wait_for_the_actual_send` |
| `WSEMODEL-CAL-094` | Step0–Step6 map onto the documented pipes. | Calendar §1.2, §1.7 | `tests/unit/test_core.py::test_calendar_steps_map_onto_the_documented_pipes` |
| `WSEMODEL-CAL-095` | Local DRAM's real access unit is the 2 KB page; an unaligned transfer costs more pages. | Whitepaper §3.4 | `tests/unit/test_core.py::test_page_granularity_is_the_real_access_unit` |
| `WSEMODEL-CAL-096` | The local-DRAM-to-L0B fill path is open item `Q8` and fails closed rather than assuming a path. | Whitepaper Appendix A `Q8` | `tests/unit/test_core.py::test_the_fill_path_into_l0b_is_open_item_q8` |
| `WSEMODEL-CAL-097` | The collective arena's level (UB or L1) is open item `Q7` / `S-2` and fails closed. | Whitepaper Appendix A `Q7`; Calendar §6.3 `S-2` | `tests/unit/test_core.py::test_arena_placement_is_open_item_q7` |
| `WSEMODEL-CAL-098` | The Batcher carries four responsibilities at three frequencies. | Whitepaper §6.1 | `tests/unit/test_host.py::test_the_four_responsibilities_and_their_frequencies` |
| `WSEMODEL-CAL-099` | The cache refill path is `DDR -> Batcher.mem -> I$/D$` and never passes through local DRAM or L1. | Whitepaper §4.1 | `tests/unit/test_host.py::test_the_cache_refill_path_avoids_local_dram_and_l1` |
| `WSEMODEL-CAL-100` | `Batcher.mem`'s four `Q3` parameters are undeclared by default and any timing request fails closed. | Whitepaper Appendix A `Q3` | `tests/unit/test_host.py::test_batcher_spec_is_undeclared_by_default_and_gates_on_q3` |
| `WSEMODEL-CAL-101` | The refill split matches Calendar §3.8.4: shared `Batcher.mem` absorbs all but one request per distinct line. | Calendar §3.8.4 | `tests/unit/test_host.py::test_refill_split_matches_the_calendar_account` |
| `WSEMODEL-CAL-102` | The runtime has exactly three frequency tiers. | Whitepaper §12 | `tests/unit/test_host.py::test_the_three_frequency_tiers` |
| `WSEMODEL-CAL-103` | `CalReg` is the only dispatch chain that does not go through the Batcher. | Whitepaper §14.1 | `tests/unit/test_host.py::test_calreg_is_the_only_chain_that_bypasses_the_batcher` |
| `WSEMODEL-CAL-104` | Any mismatch among `topologyVersion`, `calendarVersion`, and `routeVersion` faults rather than degrading. | Whitepaper §10.3, §14.2; `HW-13` | `tests/unit/test_host.py::test_version_check_faults_on_any_mismatch` |
| `WSEMODEL-CAL-105` | A launch requires a drained die and dispatches no Calendar data (`SW-1`). | Whitepaper §12.3; Calendar §6.1 | `tests/unit/test_host.py::test_launch_requires_a_drained_die_and_sends_no_calendar_data` |
| `WSEMODEL-CAL-106` | A wave may not split a syncing group. | Whitepaper §12.3 constraint 1 | `tests/unit/test_host.py::test_a_wave_may_not_split_a_syncing_group` |
| `WSEMODEL-CAL-107` | A weight layout must be blocked on 2 KB pages; an unaligned row stride is rejected. | Whitepaper §3.4 | `tests/unit/test_core.py::test_layout_requires_two_kilobyte_blocking` |
| `WSEMODEL-CAL-108` | A phase barrier requires a drained die, so the previous launch's stragglers cannot be counted into this epoch. | Whitepaper §12.3 constraint 2, `SW-1` | `tests/unit/test_host.py::test_a_phase_barrier_requires_a_drain` |
| `WSEMODEL-CAL-109` | `blockId` acquired from the `block_idx` SPR costs zero loads and stays an A-class value; the argument path costs one load. | Whitepaper §12.3 constraint 4; Calendar `C-7` | `tests/unit/test_host.py::test_block_id_from_the_spr_costs_no_load` |
| `WSEMODEL-CAL-110` | The model reports two roofline verdicts — tile-accurate and first-order — and freezes both, so neither can quietly replace the other. | Whitepaper §1, §19.2; decision 0006 | `tests/golden/test_golden_vectors.py::test_the_two_roofline_verdicts_are_frozen` |

## N. The deployment package (whitepaper §13.3; Calendar §2.7.3, §3.10)

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-111` | The compiler emits exactly five artifacts: kernel machine code, the `routeBits` table in 64 B-aligned `.rodata`, the `CalReg` mirror, the three version numbers, and per-core weight slices. | Whitepaper §13.3 | `tests/unit/test_compiler_package.py::test_the_five_documented_artifacts` |
| `WSEMODEL-CAL-112` | A conforming FFN package validates, running the structural, conservation, F1/F2/F3, version-agreement, concurrency, weight-page, and `.rodata`-alignment checks. | Calendar §2.7.2, §3.10 | `tests/unit/test_compiler_package.py::test_a_conforming_ffn_package_validates` |
| `WSEMODEL-CAL-113` | The per-call-site immediates reproduce the published values: phase B `expVal` 10752, `capacity` 12288, `selfOffStride` 192, `nBurst` 8; phase C `expVal` 36864, `selfOffStride` 1536. | Calendar §2.7.3 step 4, §2.8 | `tests/unit/test_compiler_package.py::test_call_site_immediates_match_the_published_numbers` |
| `WSEMODEL-CAL-114` | The call-site `keyId` and `opcode` stay indivisible in a `CalendarKeyRef` (invariant `O1`). | Calendar §2.5 | `tests/unit/test_compiler_package.py::test_the_key_ref_keeps_key_and_opcode_together` |
| `WSEMODEL-CAL-115` | The route table and the `CalReg` mirror must come from one algorithm call and carry the same `calendarVersion`; `build_package` refuses otherwise, and `validate` reports `V-CALREG-VERSION`. | Calendar §2.7; whitepaper §10.3 | `tests/unit/test_compiler_package.py::test_build_refuses_a_calreg_from_a_different_algorithm_call` |
| `WSEMODEL-CAL-116` | Two logical identities sharing an `opcode` must not be concurrent; declaring the FFN's two phases concurrent raises `V-OPCODE-CONCURRENT` and requires the phase split to be redone. | Calendar §2.3.1, §2.7.1 | `tests/unit/test_compiler_package.py::test_ffn_phases_share_opcode_one_and_must_not_be_concurrent` |
| `WSEMODEL-CAL-117` | The FFN's two phases over one `opcode` are accepted when they are declared sequential. | Calendar §2.3.1 | `tests/unit/test_compiler_package.py::test_seqential_phases_over_one_opcode_are_accepted` |
| `WSEMODEL-CAL-118` | A missing `conflictProof` is a warning, never a silent pass, because the no-conflict guarantee belongs to the NoC algorithm. | Calendar §2.7.1 | `tests/unit/test_compiler_package.py::test_a_missing_conflict_proof_is_a_warning_not_a_silent_pass` |
| `WSEMODEL-CAL-119` | Weight shards must be 2 KB page aligned, because that is local DRAM's real write granularity. | Whitepaper §3.4, §14.1 | `tests/unit/test_compiler_package.py::test_unpaged_weight_shards_are_rejected` |
| `WSEMODEL-CAL-120` | Every public namespace's `__all__` is pinned, so a removal or rename is a deliberate contract change; the semantic core imports without the ACIR toolchain. | `AGENTS.md` layer rule | `tests/contracts/test_public_api.py::test_public_all_matches_the_pinned_set` |

## O. The integrated compile → load → launch → collective flow

| ID | Statement | Design source | Proving test |
| --- | --- | --- | --- |
| `WSEMODEL-CAL-121` | The FFN deployment package compiles and validates as a whole. | Whitepaper §13.3; Calendar §2.7 | `tests/integration/test_load_and_launch.py::test_the_package_compiles_and_validates` |
| `WSEMODEL-CAL-122` | The loader places the package, kickstarts, and then both FFN phases complete over the package's own table and timeslot mirror. | Whitepaper §12, §14 | `tests/integration/test_load_and_launch.py::test_load_kickstart_then_run_both_phases` |
| `WSEMODEL-CAL-123` | A `topologyVersion` mismatch faults before kickstart, so a wrong-topology package never runs. | Whitepaper §10.3, §14.2; `HW-13` | `tests/integration/test_load_and_launch.py::test_the_version_check_faults_before_kickstart` |
| `WSEMODEL-CAL-124` | Every row group is a schedulable unit and a wave may not split one. | Whitepaper §12.3 constraint 1 | `tests/integration/test_load_and_launch.py::test_every_row_group_is_a_schedulable_unit` |
| `WSEMODEL-CAL-125` | The emitted `.rodata` segment round-trips through the JSON schema. | Calendar §2.6, §2.7.3 | `tests/integration/test_load_and_launch.py::test_the_compiled_table_is_emitted_and_reloadable` |
| `WSEMODEL-CAL-126` | `blockId` indexes the emitted table's node dimension and selects the right row. | Whitepaper §12.3 constraint 4; Calendar §2.5 | `tests/integration/test_load_and_launch.py::test_block_id_indexes_the_emitted_table` |

## Related pages

- [Calendar and NoC](../architecture/calendar-noc.md) for the narrative behind
  these requirements.
- [Descriptors and schemas](../reference/descriptors.md) for the JSON the schema
  requirements describe.
- [Testing and gates](../development/testing-and-gates.md) for how to run each
  lane.
