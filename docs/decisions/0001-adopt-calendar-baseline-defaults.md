# 0001. Adopt the Calendar baseline readings for C-2, C-5, C-6, C-7

- **Status**: accepted
- **Date**: 2026-09-17
- **Design sources**: Calendar [§1.5](../design/wse-calendar-scheme.md),
  [§1.8](../design/wse-calendar-scheme.md), [§2.2](../design/wse-calendar-scheme.md),
  [§3.7](../design/wse-calendar-scheme.md), [§4.5.2](../design/wse-calendar-scheme.md),
  [§6.3](../design/wse-calendar-scheme.md); whitepaper
  [§12.3](../design/wse-system-architecture-whitepaper.md)
- **Code**: `wse_model/open_items.py`, `wse_model/calendar/epoch.py`,
  `wse_model/noc/flit.py`, `wse_model/calendar/receive.py`,
  `wse_model/collective.py`

## Context

Calendar §6.3 lists four items that the design document leaves open but that the
model cannot avoid representing if it is to compute a flit header, an epoch, or a
per-core route row. The document states a **baseline** for each while leaving the
alternative open for review:

- **`C-2` flit header carriage** — (a) per-flit copy of the whole header, which
  keeps the NoC fully stateless and is the reading behind the published
  "about 12 B, about 19%" figure, versus (b) a per-packet header with per-packet
  context retained in the NoC.
- **`C-5` `epochTag` width and wraparound** — the field is proposed at 8–16 bit;
  the document's working reading is a per-launch counter starting at 1, with
  wraparound legal only after the previous epoch has drained.
- **`C-6` `epochTag` carriage** — the receive command establishes an implicit
  per-round `{opcode, epoch}` context that the send's flit header draws from,
  versus an explicit `epoch` operand on the send.
- **`C-7` `blockId` acquisition** — the `block_idx` SPR (zero loads) versus a
  kernel argument (one load per use).

These are readings of still-open items, not resolutions. The hardware interface
is not frozen, and a later review may choose differently.

## Decision

The model adopts the Calendar baseline reading of each item and records it as
`Resolution.ASSUMED` in `wse_model/open_items.py`, under decision `0001`:

| Item | Adopted reading |
| --- | --- |
| `C-2` | per-flit header copy |
| `C-5` | `epochTag` is a declared 8–16 bit parameter, default 8 bit; the per-launch counter starts at 1 and may wrap only after the previous epoch drains |
| `C-6` | the receive command establishes the round's implicit `{opcode, epoch}` context |
| `C-7` | `blockId` comes from the `block_idx` SPR; the argument path is the documented fallback |

## Code that depends on the reading

| Symbol | Depends on | What it assumes |
| --- | --- | --- |
| `wse_model.noc.flit.FlitHeader` | `C-2`, `C-5` | a header object replicated on every flit; `epoch_tag_bits` bounded to 8–16 |
| `wse_model.noc.flit.DEFAULT_EPOCH_TAG_BITS` | `C-5` | the 8 bit end of the proposed range |
| `wse_model.noc.flit.split_payload` | `C-2` | the same `FlitHeader` instance is carried by every `Flit` of a run |
| `wse_model.noc.network.SendOutcome.header_bytes_moved` | `C-2` | header bytes are paid once per flit per hop |
| `wse_model.calendar.epoch.EPOCH_TAG_MIN_BITS`, `EPOCH_TAG_MAX_BITS` | `C-5` | the proposed 8–16 bit range |
| `wse_model.calendar.epoch.EpochCounter.next` | `C-5` | first round is 1; `drained=False` at capacity is a fault |
| `wse_model.calendar.epoch.EpochTracker` | `C-5`, `C-6` | one counter per `opcode` domain per core, reset each launch |
| `wse_model.calendar.epoch.RecvContext` | `C-6` | the round context is `{opcode, epoch}` plus the AICORE / kernel / stream isolation key |
| `wse_model.calendar.receive.ReceiveAccount` | `C-6`, `C-5` | the account carries the epoch the receive command established |
| `wse_model.collective.run_allgather` | `C-6`, `C-7` | one counter-derived epoch is shared by the receive account and every send in the round; the per-source row is selected by node id |
| `wse_model.open_items.OPEN_ITEMS["C-2" ... "C-7"]` | all four | `resolution=ASSUMED`, `decision="0001"` |

## What changes if a reading changes

- **If `C-2` becomes per-packet headers**: the flit header stops being a per-flit
  cost. `FlitHeader.header_bytes`, `flit_count`, and `SendOutcome.wire_bytes`
  would be recomputed per packet, and the published 12 B / 18.75% overhead figure
  at 40 nodes would no longer describe the model. `tests/golden/test_golden_vectors.py::test_flit_header_costs_are_unchanged`
  would need a new expectation and therefore a new record.
- **If `C-5` freezes a width other than 8 bit, or requires a monotonic
  cross-launch counter**: `DEFAULT_EPOCH_TAG_BITS` changes, the flit header size
  changes at the 16 bit end only if it crosses a byte boundary (8 bit and 16 bit
  are both whole bytes, so the 12 B header holds), and `EpochCounter` would need a
  per-`blockId` GM slot and a read-modify-write per round instead of a
  kernel-local object.
- **If `C-6` becomes an explicit send operand**: the model would need a second
  representation of the epoch (send operand and receive context) and a check that
  they agree. Today `SendPlan.epoch` and `ReceiveAccount.epoch` are the same
  value in `run_allgather`, but the model does not *enforce* that coupling; it is
  a shared value, not a checked one.
- **If `C-7` becomes the argument path**: route selection gains an extra
  potentially missing load that can serialise with the payload wait. The model
  does not currently simulate that load, so the `C-7` note in the registry is
  ahead of the code: both readings produce the same row index here. A future
  AICORE or compiler model must add the cost.
- **If any of these becomes `Resolution.OPEN`**: `require_resolved` starts
  failing for consumers, which is the intended behaviour — a value must not be
  silently assumed.

## References

- Registry entries: `wse_model/open_items.py` (`C-2`, `C-5`, `C-6`, `C-7`).
- Proving tests: `tests/unit/test_calendar_semantics.py::test_epoch_counter_starts_at_one`,
  `tests/unit/test_calendar_semantics.py::test_epoch_counter_wraparound_requires_a_drain`,
  `tests/unit/test_calendar_semantics.py::test_epoch_tag_width_is_bounded_by_the_open_item_range`,
  `tests/unit/test_noc.py::test_split_payload_replicates_the_header_and_pads_the_tail`,
  `tests/unit/test_analysis.py::test_every_adopted_reading_names_a_decision_record`.
- Read next: [Keep unresolved design items explicit](0003-keep-open-items-explicit.md);
  [Static route-table layout](0005-static-table-layout.md).
