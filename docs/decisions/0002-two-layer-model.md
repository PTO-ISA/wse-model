# 0002. Two-layer model with a pure-Python semantic core

- **Status**: accepted
- **Date**: 2026-09-17
- **Design sources**: whitepaper [§5](../design/wse-system-architecture-whitepaper.md),
  [§7](../design/wse-system-architecture-whitepaper.md),
  [§10](../design/wse-system-architecture-whitepaper.md),
  [§14](../design/wse-system-architecture-whitepaper.md); Calendar
  [§2](../design/wse-calendar-scheme.md), [§4](../design/wse-calendar-scheme.md)
- **Code**: `src/wse_model/__init__.py`, `src/wse_model/calendar/`,
  `src/wse_model/noc/`, `src/wse_model/analysis/`; the planned
  `src/wse_model/acir/`

## Context

The repository builds the architecture-level model of WSE on top of the pyCircuit
`agentic_circuit` frontend. That frontend can simulate schedulable processes and
emit PYC/C++/Verilog, but it requires a native toolchain (see
[Testing and gates](../development/testing-and-gates.md)) and it is the wrong
place to freeze encoding and legality rules: those rules must be checkable in
every CI lane, including the toolchain-free ones.

At the same time, a model that exists only as prose plus a simulator cannot be
consumed by a compiler: the compiler boundary needs concrete artifacts (route
tables, golden vectors, version numbers) that a scheduler does not naturally
produce.

## Decision

The model is split into **two layers with one semantics**:

1. **The pure-Python semantic core** — `wse_model.calendar`, `wse_model.noc`,
   `wse_model.analysis`, `wse_model.topology`, `wse_model.open_items` and the
   shared modules around them. It owns encoding, legality, conservation,
   capacity, and closed-form performance rules. It has no runtime dependencies
   (`pyproject.toml` declares `dependencies = []`) and runs everywhere.
2. **The ACIR model layer** — `src/wse_model/acir/`, `agentic_circuit` modules
   that express the same rules as schedulable processes, queues, resources, and
   committed state so that the model can be simulated with `gfsim` and emitted to
   PYC/C++/Verilog.

The core is the **authority**. The ACIR layer must not disagree with it. A rule
change lands in the core **with a unit test first**, then is mirrored into the
ACIR layer. If the two cannot agree, the ACIR layer is wrong or the rule is not
yet ready to land.

## Consequences

- Every rule that matters has a toolchain-free test. `make check` (lint + unit +
  contract) proves the semantic core without pyCircuit.
- The artifacts the compiler consumes — the `wse-model/calendar-route-table/1`
  JSON, the emitted `.rodata` bytes, the golden vectors — are produced and
  frozen by the core, not by a simulation.
- The `agentic_circuit` layer is additive: adding it must not change a single
  core result. Any behavioural difference is a defect in the ACIR layer.
- A change that touches `acir/` additionally requires the `agentic_circuit`
  closure and must state the pinned pyCircuit revision.
- `PTO-ISA/pyCircuit` owns the `agentic_circuit` language and its backends. This
  repository never patches framework semantics; it reports the gap upstream and
  pins the consuming revision.

## Current status

The semantic core is the implemented layer: `calendar/`, `noc/`, `analysis/`,
`core/`, `host/`, `compiler/`, and the shared modules around them, all tested by
the toolchain-free unit, contract, integration, and golden lanes.

The ACIR layer is present and importable (`src/wse_model/acir/`, with tests under
`tests/acir/`), but it is **in progress and not exercised by the default gate**:
its tests require the `agentic_circuit` frontend and the native ACIR tools, so
they run only under `make acir` or the opt-in `acir` CI job. The core remains the
authority, and nothing in the core depends on the ACIR layer. See the
[roadmap](../roadmap.md).

## References

- [`AGENTS.md`](../../AGENTS.md) hard rule 2.
- [Architecture overview](../architecture/overview.md) for the module map.
- Proving tests: `tests/contracts/test_table_schema.py::test_package_exports_are_stable`
  and the unit suite in `tests/unit/`.
