# AGENTS.md — WSE Model agent instructions

This repository builds the architecture-level model of the WSE accelerator on
top of the pyCircuit `agentic_circuit` frontend.

## Read first

- [`docs/design/wse-system-architecture-whitepaper.md`](docs/design/wse-system-architecture-whitepaper.md)
- [`docs/design/wse-calendar-scheme.md`](docs/design/wse-calendar-scheme.md)
- [`docs/architecture/overview.md`](docs/architecture/overview.md)
- [`docs/decisions/`](docs/decisions/) — accepted model decisions
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Ownership and scope

- This repository owns the WSE model: encoding, legality, conservation,
  scheduling, capacity, and performance semantics of the WSE system.
- `PTO-ISA/pyCircuit` owns the `agentic_circuit` language, its ACIR dialect,
  ACSim/gfsim, and the PYC/C++/Verilog backend. Never patch framework semantics
  from here; report the gap upstream and pin the consuming revision instead.
- `PTO-ISA/pto-spec` owns PTO instruction semantics. Do not duplicate PTO
  encoding or instruction handlers here.
- The design documents under `docs/design/` are **read-only source material**.
  Do not edit them. Record a divergence in `docs/decisions/` instead.

## Hard rules

1. **Never invent a value the design sources leave open.** Whitepaper Appendix A
   (`Q1`–`Q12`) and Calendar §6.3 (`S-*`, `C-*`) list unresolved items. Represent
   them as declared parameters with an explicit status, or fail loudly. A
   plausible-looking default that silently changes model results is a defect.
2. **Two layers, one semantics.** The pure-Python core in
   `src/wse_model/<domain>/` is the semantic authority. The ACIR modules in
   `src/wse_model/acir/` express the same rules; they must not disagree. A rule
   change lands in the core with a unit test first, then in the ACIR layer.
3. **Exact widths.** All integer widths in the model are exact and derived from
   the design documents: `routeBits` is `2 × node_count` bit, `opcode` is 3 bit,
   `redOp` is 3 bit, `epochTag` is an open parameter (8–16 bit), a route-table
   entry is 16 B. Do not widen, round, or "clean up" a width.
4. **Golden vectors are contract.** The Calendar §2.2.1 golden vector and the
   FFN `keyId 0` / `keyId 1` encodings are frozen test inputs. Any change to
   them is a breaking change requiring a decision record.
5. **Fail closed.** Illegal bit pairs (`01`), a cyclic induced subgraph, an
   inconsistent `selfLand` bit, or a failed version check are faults, not
   warnings.
6. **Keep unresolved dimensionality explicit.** Model both the 40-node
   (Calendar baseline) and 48-node (whitepaper hardware) readings of `Q1`; do
   not hard-code one and hide the other.
7. **No secrets, no telemetry, no network calls** in model code paths.
8. Do not add AI co-author lines to commits or pull request text.

## Verification

Run `make check` before opening or updating a pull request. It covers lint, the
pure-Python unit suite, and contract tests, and requires no toolchain. Changes
that touch `src/wse_model/acir/` additionally require the `agentic_circuit`
closure and must state the pinned pyCircuit revision.

## When to stop and ask

- The requested model behavior contradicts a design document.
- A design value is genuinely unresolved and the choice changes model output.
- A change would require patching `agentic_circuit` itself.
