# Testing and gates

The repository proves every rule with a gate, and each gate has a lane that
matches the change. This page gives the change-to-gate matrix, the exact command
for each gate, and what each one actually proves.

The default gate is deliberately toolchain-free: `make check` is `lint + unit +
contract` and needs nothing but Python. The `agentic_circuit` closure is opt-in.

## Change-to-gate matrix

| Change touches | Run at minimum | Also required |
| --- | --- | --- |
| Documentation (`docs/**`, `README.md`, `mkdocs.yml`) | `make check` | `python -m mkdocs build --strict`; markdownlint (pre-commit) |
| A semantic rule in the pure-Python core | `make unit` | `make contract` if an interface moved; a new test that fails without the change |
| A golden vector, width, or published number | `python -m pytest tests/golden` | A decision record; `python tools/check_design_sources.py` if a design document changed |
| The route-table or kernel-object JSON | `make contract` | The matching `schemas/*.schema.json` and its contract test |
| An end-to-end scenario or example | `make integration` | The example scripts in `examples/` still run clean |
| The CLI | `make unit` (the CLI contract tests) | The `CLI smoke` step in CI |
| Packaging, version, governance, workflows | `python tools/check_repo_standards.py` | `make lint` |
| `src/wse_model/acir/**` | `make acir` | The `agentic_circuit` closure and the pinned pyCircuit revision |

Rule of thumb from `CONTRIBUTING.md`: start with the smallest lane that proves the
change, then widen. `make check` is the minimum for any pull request.

## The gates

### Lint

```console
$ make lint
python3 -m ruff check .
```

Plus, in CI, `python -m ruff format --check .` and markdownlint over every
`**/*.md` except `docs/design/**` and `CHANGELOG.md`. `ruff` is configured in
`pyproject.toml` with `line-length = 100` and the rule set
`E, F, W, I, N, UP, B, A, C4, T20`. Lint proves the code stays readable,
import-sorted, and free of obvious defects; it proves nothing about semantics.

### Unit tests

```console
$ make unit
python3 -m pytest tests/unit -m unit
```

The unit lane is the semantic core's proof. It runs with no toolchain and no
network, on every supported Python version, and covers the encoding, the
validation rules, the NoC, `CalReg`, the geometry and `expVal` contracts, the
AICORE pipes, the host dispatch model, the compiler self-checks, and the analysis
arithmetic. Every rule change lands here with a test that fails without the change.

### Contract tests

```console
$ make contract
python3 -m pytest tests/contracts -m contract
```

The contract lane freezes the interfaces other tools consume: the package's
exported symbols and version, the `wse-model/calendar-route-table/1` schema name
and required fields, byte-for-byte round-tripping, deterministic JSON, both table
layouts, and the top-level keys of the CLI JSON. A failure here means a consumer
would break, even if the semantics are still correct.

### Integration tests

```console
$ make integration
python3 -m pytest tests/integration
```

The integration lane runs the FFN two-phase AllGather closure end to end:
completion on every member, the shared-`opcode` epoch advance, the drain after a
launch, the `CalReg`-required fault, the reduction refusal, and the tree validity
of every FFN bitmap. It also executes every script in `examples/` in a subprocess,
so an example that reaches past the public API fails the build.

### Golden vectors

```console
$ python -m pytest tests/golden -q
13 passed in 0.03s
```

The golden lane is the design-fidelity check: the Calendar §2.2.1 vector, the two
FFN rows, the `expectedRxBytes` values, the land counts, the FFN table footprint,
the entry size and opcode width, the flit header costs, the roofline numbers, the
two roofline verdicts, and the topology shapes. A change to any expectation is a
breaking change and needs a decision record
([decision 0004](../decisions/0004-golden-vectors-are-contract.md)).

### Design fidelity

```console
$ python tools/check_design_sources.py
design sources OK: 2 files, 246033 bytes
```

This verifies that `docs/design/` is present and matches the SHA-256 manifest in
`docs/design/MANIFEST.json`. It is the guard that makes `docs/design/` read-only
source material rather than a document someone edits to match the code. The CI
`design-fidelity` job runs this check and the golden lane together.

### Repository standards

```console
$ python tools/check_repo_standards.py
note: ci.yml jobs not required by governance: ['acir (opt-in)']
repository standards OK: 26 required files, version, governance, manifest, and trailer checks passed
```

This gate checks the things a standards-compliant repository must keep
consistent: the required governance, packaging, and documentation files exist; the
`pyproject.toml` version equals `wse_model.__version__`; `CHANGELOG.md` has an
`Unreleased` section; every required status-check context in
`.github/repository-governance.json` names a job `ci.yml` actually defines (with
matrix expansion resolved the way GitHub reports it); the design manifest and
`docs/design/` agree; and no tracked text file contains an AI co-author trailer.
It also runs `git diff --check` in CI for whitespace hygiene.

### Documentation build

```console
$ make docs
python3 -m mkdocs build --strict
```

The docs lane builds the site with `--strict`, so a broken internal link, a nav
entry that points at a missing page, or a warning fails the build. The `docs` CI
job runs exactly this.

### Coverage

```console
$ make coverage
python3 -m pytest --cov=wse_model --cov-report=term-missing --cov-report=xml
```

Coverage is informational: the CI `coverage` job uploads `coverage.xml` as an
artifact but does not set a threshold. It exists to show which rules have no test,
not to substitute for one.

### The default gate

```bash
make check
```

`make check` is `lint + unit + contract`, and it prints `wse-model gate passed` at
the end. It is the gate `AGENTS.md` requires before opening or updating a pull
request. The other lanes widen it; none of them replace it.

## The ACIR closure

The `agentic_circuit` layer is different: it needs the pyCircuit native toolchain,
which is a long LLVM-linked build. It is therefore **opt-in** and never part of the
default gate.

```bash
git clone https://github.com/PTO-ISA/pyCircuit.git ../pyCircuit
make bootstrap PYCIRCUIT_ROOT=../pyCircuit
bash tools/build-acir-tools.sh ../pyCircuit
export ACIR_OPT=... ACIR_QUEUE_CXXGEN=...
make acir
```

`make acir` first refuses unless `ACIR_OPT` is set, pointing at
`tools/build-acir-tools.sh`, and then runs `python -m pytest tests/acir -m acir`.
The CI `acir` job runs the same sequence behind the `WSE_MODEL_ACIR_CI` repository
variable, so it is not a required check.

**The rule:** a change that touches `src/wse_model/acir/**` must additionally run
the `agentic_circuit` closure and state the pinned pyCircuit revision in the pull
request. This is `AGENTS.md` rule 2 in practice: the pure-Python core is the
authority, and the ACIR layer has to prove it does not disagree.

The ACIR layer is present and importable, but `make acir` is opt-in because it
needs the native toolchain, so its tests are not part of the default gate. See the
[roadmap](../roadmap.md).

## CI jobs

| Job | Required | What it runs |
| --- | --- | --- |
| `lint` | yes | `ruff check`, `ruff format --check`, markdownlint, repository standards, whitespace hygiene |
| `test (3.10)` … `test (3.13)` | yes | unit + contract, integration, CLI smoke |
| `coverage` | yes | the full suite with coverage, uploaded as an artifact |
| `docs` | yes | `mkdocs build --strict` |
| `design fidelity` | yes | `tools/check_design_sources.py` and `tests/golden` |
| `acir (opt-in)` | no | pyCircuit checkout, native tool build, `pytest tests/acir` |

The required contexts are declared in
[`.github/repository-governance.json`](../../.github/repository-governance.json),
and `tools/check_repo_standards.py` keeps that file and `ci.yml` from drifting
apart. Branch protection on `main` requires all of them except the opt-in `acir`
job, with linear history and one approving review.

A separate tag-triggered `release.yml` verifies the tag against
`src/wse_model/version.py`, runs the gate, builds and validates the sdist and
wheel, and publishes only on an explicit non-dry-run dispatch.

## Related pages

- [Getting started](getting-started.md) for environment setup and the worked CLI
  walkthrough.
- [Engineering standards](engineering-standards.md) for the conventions the lint
  and test gates enforce.
- [Requirements: Calendar closure](../requirements/calendar-closure.md) for the
  requirement-to-test mapping.
