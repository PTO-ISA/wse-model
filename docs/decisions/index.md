# Decision records

A **decision record** (also called an architecture decision record, ADR) fixes a
choice that the model has to make but that the design sources either leave open
or state in a way the model cannot follow verbatim. It is the mechanism
[`AGENTS.md`](../../AGENTS.md) hard rule 1 asks for: the model never silently
substitutes a plausible default for a value the sources leave open, and it never
edits `docs/design/` to make a divergence disappear.

## When a record is required

Write a decision record when any of the following is true.

- The model diverges from a statement in
  [`docs/design/`](../design/wse-system-architecture-whitepaper.md).
- The model adopts a reading of an open item from whitepaper Appendix A (`Q1`–`Q12`)
  or Calendar §6.3 (`S-1`–`S-7`, `C-1`–`C-12`). Adopting a reading changes the
  item's [`Resolution`](../../src/wse_model/open_items.py) from `open` to
  `assumed`; the record is referenced from the registry entry's `decision` field.
- A golden vector, an integer width, or an interface that a contract test freezes
  would change.
- A previously accepted record is superseded.

A record is **not** required for a change that only follows an existing record,
fixes a bug without changing semantics, or adds a test.

## Format

Files live in `docs/decisions/` and are named `NNNN-kebab-case-title.md`, where
`NNNN` is the next free zero-padded number. Nothing renumbers; superseded records
stay in place with their status updated.

Each record uses this structure:

```markdown
# NNNN. Title

- **Status**: proposed | accepted | superseded by NNNN | rejected
- **Date**: YYYY-MM-DD
- **Design sources**: the sections the decision reads
- **Code**: the symbols the decision governs

## Context

What the design sources say, and what they leave open.

## Decision

The reading the model adopts, stated so that a test could be written against it.

## Consequences

What changes if the reading changes, what is now blocked or unblocked, and what
remains open.

## References

Links to the design sections, the registry, and the proving tests.
```

The status vocabulary matters to the model: an `accepted` record that adopts a
reading must have moved the corresponding open item to `Resolution.ASSUMED` (or
`RESOLVED`) in `wse_model/open_items.py`, and
`tests/unit/test_analysis.py::test_every_adopted_reading_names_a_decision_record`
enforces that every assumed item names a record.

## Open items versus decisions

The two mechanisms are complementary and both are required.

| Mechanism | Lives in | Answers |
| --- | --- | --- |
| Open-item registry | `src/wse_model/open_items.py`, surfaced by `wse-model open-items` | Which values do the sources leave open, who owns them, and how does the model treat them today? |
| Decision record | `docs/decisions/` | Why did the model adopt the reading it adopted, and what would change if the reading changed? |

An item may be `assumed` (a reading is adopted) or `open` (no reading). An
`open` item must not be given a value at all: code that would produce a
materially different answer under the two readings calls
`wse_model.open_items.require_resolved` and fails closed. The registry and the
gate are described in
[Keep unresolved design items explicit](0003-keep-open-items-explicit.md).

## Index

| Record | Status | Adopts | Governs |
| --- | --- | --- | --- |
| [0001 Adopt the Calendar baseline readings for C-2, C-5, C-6, C-7](0001-adopt-calendar-baseline-defaults.md) | accepted | `C-2`, `C-5`, `C-6`, `C-7` | `wse_model/calendar/epoch.py`, `wse_model/noc/flit.py`, `wse_model/open_items.py` |
| [0002 Two-layer model with a pure-Python semantic core](0002-two-layer-model.md) | accepted | — | package layering, `wse_model.acir` |
| [0003 Keep unresolved design items explicit](0003-keep-open-items-explicit.md) | accepted | — | `wse_model/open_items.py`, `wse_model/errors.py` |
| [0004 Golden vectors are frozen contracts](0004-golden-vectors-are-contract.md) | accepted | — | `wse_model/fixtures.py`, `tests/golden/` |
| [0005 Static route-table layout](0005-static-table-layout.md) | accepted | `C-9` | `wse_model/calendar/table.py` |
