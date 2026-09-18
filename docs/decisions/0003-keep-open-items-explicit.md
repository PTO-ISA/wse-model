# 0003. Keep unresolved design items explicit

- **Status**: accepted
- **Date**: 2026-09-17
- **Design sources**: whitepaper
  [Appendix A](../design/wse-system-architecture-whitepaper.md); Calendar
  [§6.3](../design/wse-calendar-scheme.md)
- **Code**: `wse_model/open_items.py`, `wse_model/errors.py`,
  `wse_model/analysis/latency.py`, `wse_model/calendar/collective.py`,
  `wse_model/calendar/table.py`, `wse_model/cli.py`

## Context

Whitepaper Appendix A lists `Q1`–`Q12` and Calendar §6.3 lists `S-1`–`S-7` and
`C-1`–`C-12`: values and interface choices that the design documents explicitly do
not fix. Several of them change model output if guessed:

- `Q1` decides whether `routeBits` is 80 bit (40 nodes) or 96 bit (48 nodes), and
  therefore whether a route-table entry still fits one 16 B GPR pair.
- `Q3` and `Q9` supply the Batcher dispatch time and the Davinci/WSE-Lite
  round-trip latency without which the five-block latency budget has no total.
- `C-3` and `C-10` gate the reduction semantics and the flit header's element
  type field.
- `C-9` chooses the static table layout.

A plausible-looking default that silently changes a result is exactly the defect
[`AGENTS.md`](../../AGENTS.md) hard rule 1 forbids. But refusing to model anything
until every item is resolved would also be useless.

## Decision

Unresolved items are **first-class, queryable objects**, and a value is attached
to one only by a decision record.

1. `wse_model.open_items.OPEN_ITEMS` registers every item as an `OpenItem` with an
   `id`, a `title`, a `source` (whitepaper Appendix A or Calendar §6.3), an
   `owner`, a `Resolution`, a `note` describing the current treatment, and an
   optional `decision` record id.
2. `Resolution` has three states: `OPEN` (no reading; consumers must not depend on
   a value), `ASSUMED` (a reading is adopted from a stated assumption and must
   name a decision record), and `RESOLVED` (decided by a record).
3. A parameter that stands in for an open item carries the item id and its
   resolution. Code whose numerical or structural result changes materially
   between the readings calls `require_resolved(item_id, consumer=...)`, which
   raises `OpenItemError` while the item is `OPEN`.
4. `wse_model.open_items.open_item(item_id)` looks an item up by id and raises
   `KeyError` for an unknown id, so a typo cannot silently create an unregistered
   item.
5. The CLI exposes the registry: `wse-model open-items` prints every item as JSON,
   and `--status {open,assumed,resolved}` filters it. The
   [open-items reference](../reference/open-items.md) is generated from that
   command.
6. `tests/unit/test_analysis.py::test_whitepaper_and_calendar_items_are_all_registered`
   proves the registry is complete, and
   `test_every_adopted_reading_names_a_decision_record` proves no item is assumed
   without a record.

## Where the gate is applied today

| Consumer | Item | Behaviour while open |
| --- | --- | --- |
| `wse_model.analysis.latency.LatencyBudget.blocks` | `Q3` | raises `OpenItemError` rather than producing a total |
| `wse_model.analysis.latency.LatencyBudget.total_seconds` | `Q3`, `Q9` | raises `OpenItemError` with the item's title |
| `wse_model.calendar.collective.ReductionElementType.name` | `C-3` | raises `OpenItemError`; the raw code is carried but never named |
| `wse_model.collective.run_allgather` | `C-10` | refuses to model a non-AllGather collective |
| `wse_model.noc.network.allgather_geometry_check` | `C-10` | refuses to model a non-AllGather closure |
| `wse_model.calendar.entry.CalendarRouteEntry.to_bytes` | `Q1` structurally | raises when the entry no longer fits the 16 B layout (48 nodes) |
| `wse_model.calendar.table.TableLayout.open_item` | `C-9` | reports which layout carries an open item |

## Consequences

- A reader can always ask what the model assumes, by running
  `wse-model open-items`, instead of reading a hard-coded number out of the code.
- Adding a value for an open item without a record is a visible, test-failing
  change, not a quiet one.
- Some functionality is deliberately unavailable. There is no total latency
  figure, no named reduction element type, and no reduction collective closure
  until the relevant items are decided. That is the intended failure mode.
- A record that adopts a reading must move the item to `Resolution.ASSUMED` (or
  `RESOLVED`) in the same change.

## Known gaps

The registry is complete, but not every invented encoding is routed through the
gate. `wse_model.calendar.collective.RedOp` assigns numeric codes to `SUM`, `MAX`,
`MIN`, `PROD` "in the order the design document lists them", because Calendar §2.4
does not fix the codes. That assignment is documented in the module docstring and
every *use* of a reduction operator is gated on `C-10`, but the codes themselves
are not a registered open item and `RedOp` construction does not call
`require_resolved`. If the codes change, no test currently fails. A future change
should either register the encoding or route it through `C-10`.

## References

- [Decision-record convention](index.md).
- [Adopt the Calendar baseline readings](0001-adopt-calendar-baseline-defaults.md).
- Proving tests: `tests/unit/test_analysis.py::test_require_resolved_raises_for_open_items_and_passes_for_assumed_ones`,
  `tests/unit/test_analysis.py::test_open_item_lookup_rejects_unknown_ids`,
  `tests/unit/test_calendar_semantics.py::test_reduction_element_type_carries_the_code_but_refuses_to_name_it`.
