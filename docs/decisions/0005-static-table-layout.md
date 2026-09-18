# 0005. Static route-table layout defaults to key-major and also models node-major

- **Status**: accepted
- **Date**: 2026-09-17
- **Design sources**: Calendar
  [§2.6](../design/wse-calendar-scheme.md), [§3.8.3](../design/wse-calendar-scheme.md),
  [§3.8.4](../design/wse-calendar-scheme.md), [§6.3 `C-9`](../design/wse-calendar-scheme.md);
  whitepaper [§11.5](../design/wse-system-architecture-whitepaper.md)
- **Code**: `wse_model/calendar/table.py`, `wse_model/calendar/validate.py`,
  `wse_model/noc/network.py`

## Context

Calendar §2.6 fixes the shape of the emitted table as
`kCalendarRoute[keyId][node]`: one 16 B entry per logical identity and source node,
with all nodes emitted and no per-core pruning. Because a core is selected by the
runtime `blockId`, every core's two loads name
`base + keyId*640 + blockId*16` and `+8`, which for different keys are 640 B
apart. Each core therefore residents one 64 B D-cache line per key.

Calendar §3.8.3 identifies an honest 4× amplification that is not about the table
size: a 64 B line holds four entries (cells `4k..4k+3`), and a core uses only one
of them, so 48 B of every line it touches is a neighbour's row. Transposing the
table to `kCalendarRoute[node][keyId]` makes a core's `keyCount` entries
contiguous, so they occupy `ceil(keyCount/4)` lines. The document states that
instruction count, addressing shape, and total bytes are unchanged, that the
change touches no hardware dependency and no call site, and that `C-9` is
**not adopted as the authoritative layout** in the design document — the baseline
remains key-major, with a recommendation to decide before `keyCount > 4`.

## Decision

The model adopts the design document's baseline as the **default** and implements
the node-major variant as a first-class alternative, so `C-9` is `ASSUMED` under
decision `0005`:

1. `wse_model.calendar.table.TableLayout` has two members, `KEY_MAJOR` and
   `NODE_MAJOR`, and `KEY_MAJOR` is the default of `CalendarRouteTable`,
   `build_table`, `ffn_example`, `wse-model calendar emit`, and
   `wse-model run ffn-allgather`.
2. `CalendarRouteTable.entry_index` implements both address computations:
   `keyId * node_count + node` for key-major and `node * key_count + keyId` for
   node-major. `entry_offset` multiplies by the frozen 16 B entry size, and
   `table_bytes` is identical under both layouts.
3. `TableLayout.d_cache_lines_per_core` returns `key_count` for key-major and
   `ceil(key_count * 16 / 64)` for node-major, and
   `CalendarRouteTable.d_cache_bytes_per_core` derives bytes from it.
   `wse_model.noc.network.table_layout_lines` exposes the same computation for a
   table plus an override layout.
4. `wse_model.calendar.validate.validate_table_budget` checks the residency under
   both readings (`node_major=False` and `node_major=True`) against the
   `MAX_KEY_COUNT` budget.
5. `TableLayout.open_item` reports `"C-9"` for `NODE_MAJOR` and `None` for
   `KEY_MAJOR`, so a consumer can tell which layout carries an open item.
6. `CalendarRouteTable.to_dict` records the chosen `layout`; the JSON schema
   `wse-model/calendar-route-table/1` accepts `"key-major"` and `"node-major"`.

## The residency difference

| | key-major (default) | node-major (`C-9` variant) |
| --- | --- | --- |
| Entry address for core `n`, key `k` | `k * node_count * 16 + n * 16` | `n * key_count * 16 + k * 16` |
| Lines per core at `keyCount = 2` (the FFN) | 2 lines = 128 B | 1 line = 64 B |
| Lines per core at `keyCount = 16` (the budget cap) | 16 lines = 1 KB | 4 lines = 256 B |
| Lines per core in general | `keyCount` | `ceil(keyCount / 4)` |
| Instruction count, addressing shape, total bytes | — | identical |
| Cold misses per core per key | 1 per key (the second load shares the line) | 1 for the whole table (all keys share the line) |

The "4×" is the asymptotic and full-budget figure (`16 → 4` lines). For the FFN's
two logical identities it is `2 → 1` lines, i.e. 128 B → 64 B: the first four keys
fit one line, so the reduction is `min(4, keyCount)`-fold. The design document's
recommendation to decide before `keyCount > 4` is exactly where key-major's
per-core residency starts to grow linearly while node-major's stays at one line.

## Consequences

- The default output is bit-for-bit the layout the design document describes, so
  the golden trace is unaffected; `tests/contracts/test_table_schema.py::test_both_layouts_emit_the_same_bytes_in_a_different_order`
  proves the two layouts contain the same set of 16 B entries and the same total
  bytes, and `tests/unit/test_validate.py::test_node_major_layout_uses_four_times_fewer_lines`
  proves the residency arithmetic.
- Because `C-9` is assumed rather than resolved, the node-major reading is
  available but not authoritative. A compiler that emits node-major addresses must
  record that it did so through the `layout` field, which the schema and the
  contract test both read.
- If `C-9` is resolved to node-major as the authoritative layout, the default
  flips in `TableLayout` and the FFN fixture; address arithmetic, instruction
  count, and total bytes do not change, but the emitted byte order and the
  per-core residency do. A new record would be required because the default
  emitted artifact changes.
- If a third layout appears (for example the `C-8` per-shard dimension), it
  multiplies both the DDR footprint and the per-core residency by `shardCount`
  and breaks the "constant subscript" property that keeps residency decoupled
  from the table size. `C-8` remains open and unmodelled.

## References

- Registry entry: `wse_model/open_items.py` (`C-9`).
- Design text: Calendar §3.8.3 (the full comparison), §3.8.4 (the budget), §6.3
  (`C-9`).
- Proving tests: `tests/unit/test_validate.py::test_node_major_layout_uses_four_times_fewer_lines`,
  `tests/contracts/test_table_schema.py::test_both_layouts_emit_the_same_bytes_in_a_different_order`,
  `tests/golden/test_golden_vectors.py::test_ffn_table_footprint_matches_the_document`.
- [Calendar and NoC deep dive](../architecture/calendar-noc.md).
