# Contributing to WSE Model

wse-model is maintained by PTO-ISA as the architecture-level model of the WSE
accelerator. Contributions must preserve the design documents' semantics and
include evidence appropriate to the change.

## Before you start

Read these sources of truth before changing model behavior:

- [`docs/design/wse-system-architecture-whitepaper.md`](docs/design/wse-system-architecture-whitepaper.md)
- [`docs/design/wse-calendar-scheme.md`](docs/design/wse-calendar-scheme.md)
- [`docs/decisions/`](docs/decisions/) — accepted model decisions
- [`AGENTS.md`](AGENTS.md) — hard rules for this repository
- [`docs/development/testing-and-gates.md`](docs/development/testing-and-gates.md)

The design documents are read-only inputs. When the model must diverge from
them, add a decision record under `docs/decisions/` and reference it from the
change.

## Prerequisites

- Python 3.10 or newer
- Git

The pure-Python semantic core needs nothing else. The `agentic_circuit` model
layer additionally needs a `PTO-ISA/pyCircuit` checkout; see
[`docs/development/getting-started.md`](docs/development/getting-started.md).

## Set up a checkout

```bash
git clone https://github.com/PTO-ISA/wse-model.git
cd wse-model
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## What to change, and where

| Change | Location |
| --- | --- |
| Encoding, legality, conservation rules | `src/wse_model/calendar/`, `src/wse_model/noc/` |
| Topology or platform constants | `src/wse_model/data/`, `schemas/` |
| Schedulable ACIR model | `src/wse_model/acir/` |
| Scenario or performance analysis | `src/wse_model/analysis/` |
| A new resolved design question | `docs/decisions/` |
| Interface stability | `tests/contracts/` + `schemas/` |

Two rules follow from the two-layer design:

1. Land a rule change in the pure-Python core **with a unit test first**, then
   mirror it into `src/wse_model/acir/`.
2. Never edit `docs/design/` in place. It is verbatim source material.

## Validate a change

Start with the smallest lane that proves the change, then widen:

```bash
make lint          # ruff
make unit          # fast semantic tests
make contract      # interface and schema stability
make integration   # end-to-end scenarios
make check         # the repository gate: lint + unit + contract
```

Changes touching `src/wse_model/acir/` must also run the `agentic_circuit`
closure and state the pinned pyCircuit revision in the pull request.

## Reporting a change

A pull request description must state:

- what semantic rule or capability changed, and why;
- the design-document section or decision record it follows;
- the exact commands run and their result;
- any newly resolved or newly discovered open item from whitepaper Appendix A
  or Calendar §6.3.

## Commit and review conventions

- Branch names are descriptive and scoped to one change family.
- Keep one logical change per commit; rebase rather than merge `main`.
- Do not add AI co-author lines to commits or pull request text.
- Do not weaken a faithfulness test, golden vector, or `fail-closed` check to
  make a change pass.

## License

By contributing you agree that your contribution is licensed under the BSD
3-Clause License in [`LICENSE`](LICENSE).
