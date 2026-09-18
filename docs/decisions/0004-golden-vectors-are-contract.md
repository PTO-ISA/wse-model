# 0004. Golden vectors are frozen contracts

- **Status**: accepted
- **Date**: 2026-09-17
- **Design sources**: Calendar
  [§2.2.1](../design/wse-calendar-scheme.md), [§2.6](../design/wse-calendar-scheme.md),
  [§2.8](../design/wse-calendar-scheme.md); whitepaper
  [§19.2](../design/wse-system-architecture-whitepaper.md)
- **Code**: `wse_model/fixtures.py`, `tests/golden/test_golden_vectors.py`,
  `tests/unit/test_route_bits.py`

## Context

Calendar §2.2.1 publishes a consistency anchor: for `source = N00`, the pass set
`{N00, N01, N02, N03, N04, N10, N18, N19}`, the land set `{N04, N19}`, and the
resulting 10 B bitmap `AA 03 20 00 E0 00 00 00 00 00`. The document states that
the compiler, packager, RTL, simulator, and runtime dump must all agree on it
byte for byte. The same section publishes the FFN `keyId 0` and `keyId 1` rows and
their expected receive byte counts.

These values are the model's contract with its sources. If the model can change
them without ceremony, then "the model matches the design document" stops meaning
anything, and a compiler that consumes the model's tables cannot rely on them.

## Decision

The Calendar §2.2.1 golden vector and the FFN `keyId 0` / `keyId 1` rows are
**frozen test inputs**.

1. `wse_model.fixtures` transcribes the published values:
   `GOLDEN_PASS_NODES`, `GOLDEN_LAND_NODES`, `GOLDEN_ROUTE_BITS`, and the FFN
   geometry constants `FFN_PHASE_B_ROW_BYTES = 192` and
   `FFN_PHASE_C_ROW_BYTES = 1536`.
2. `wse_model.fixtures.ffn_example` reconstructs the two documented group shapes
   and then **asserts the two published hex rows**, raising `CalendarError` if the
   reconstruction drifts. The fixture cannot silently become a different routing
   algorithm.
3. `tests/golden/test_golden_vectors.py` freezes the published numbers
   independently of the fixture: the golden row, the two FFN rows, the two
   `expectedRxBytes` values (10752 and 36864), the land counts (7 and 3), the FFN
   table footprint (1280 B, two D-cache lines per core), the entry size (16 B),
   the opcode width (3 bit), the reserved opcodes (`{0, 7}`), the flit header
   costs (12 B / 14 B), the roofline numbers (11.5 / 45.9 / 91.8 FLOP/Byte and
   minimum batch 6 / 23 / 46), and the topology shapes (5×8 = 40, 6×8 = 48).
4. Changing any expectation in `tests/golden/` is a **breaking change**. It
   requires a new decision record that states which design source changed or which
   reading was adopted, and it requires the design-source manifest to be
   regenerated with `python tools/check_design_sources.py --update` if the change
   came from an intentional design-document update.
5. A faithfulness test, golden vector, or fail-closed check is never weakened to
   make a change pass. When model and document disagree, the disagreement is
   reported, not absorbed.

## Consequences

- The golden lane is the model's design-fidelity check. The `design-fidelity` CI
  job runs `python tools/check_design_sources.py` (the design documents are
  unmodified) and `python -m pytest tests/golden` (the model still reproduces
  them).
- The FFN rows are a *fixture*, not a routing algorithm: Calendar §2.7 forbids
  software rewriting the NoC's routing algorithm, so production bitmaps arrive
  from the NoC provider and are validated, never generated. The frozen rows exist
  only so the model has a self-checking example.
- A 48-node table cannot be emitted under the frozen 16 B entry layout. That is
  not a licence to change the golden vector; it is the structural consequence of
  open item `Q1` and is reported as such.

## References

- [Adopt the Calendar baseline readings](0001-adopt-calendar-baseline-defaults.md).
- [Static route-table layout](0005-static-table-layout.md).
- Proving tests: `tests/golden/test_golden_vectors.py::test_golden_route_bits_are_unchanged`,
  `test_ffn_key_encodings_are_unchanged`, `test_ffn_expected_receive_bytes_are_unchanged`,
  `test_entry_size_and_opcode_width_are_unchanged`, `test_flit_header_costs_are_unchanged`.
- `tests/unit/test_route_bits.py::test_golden_vector_matches_the_published_bytes`
  and `test_golden_vector_byte_layout_is_lsb_first`.
