# Getting started

This page takes you from a clean checkout to a running CLI, then shows the
`agentic_circuit` bootstrap path and a worked walkthrough with the real output of
each command.

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.10 or newer | CI tests 3.10, 3.11, 3.12, and 3.13. `pyproject.toml` sets `requires-python = ">=3.10"`. |
| Git | to clone the repository, and required by `tools/check_repo_standards.py` and the design-source check. |

The pure-Python semantic core needs nothing else: `pyproject.toml` declares
`dependencies = []`. The `agentic_circuit` layer additionally needs a
`PTO-ISA/pyCircuit` checkout (see [below](#the-agentic_circuit-bootstrap-path)),
and building the ACIR native tools additionally needs LLVM/MLIR 22.1.8.

## Create the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The `dev` extra installs `pytest`, `pytest-cov`, `jsonschema`, `ruff`, and
`pre-commit`. The `docs` extra (`pip install -e ".[docs]"`) adds `mkdocs` and
`mkdocs-material` for building this site.

### The `make` targets

The Makefile is the developer entry point. `make help` lists everything:

```console
$ make help
  acir               Run the ACIR model-layer tests (requires the native ACIR tools)
  bootstrap          Install the package plus the pyCircuit agentic-circuit frontend
  check              Run the repository gate (lint + unit + contract)
  clean              Remove generated artifacts
  contract           Run interface and schema contract tests
  coverage           Run tests with a coverage report
  dev                Install with development extras
  docs               Build the documentation site
  docs-serve         Serve the documentation site locally
  format             Apply formatting and safe lint fixes
  help               Show this help
  install            Install the package in editable mode
  integration        Run end-to-end model scenarios
  lint               Run the linter
  pre-commit         Run all pre-commit hooks
  test               Run the full test suite
  typecheck          Run the type checker when mypy is available
  unit               Run the fast pure-Python unit tests
```

## Run the gate

`make check` is the repository gate. It is `lint + unit + contract`, and it
deliberately needs no toolchain so that the semantic core can always be validated.
A passing run ends with `wse-model gate passed`:

```console
$ make check
python3 -m ruff check .
All checks passed!
python3 -m pytest tests/unit -m unit
…
============================= 235 passed in 0.29s ==============================
python3 -m pytest tests/contracts -m contract
…
============================== 31 passed in 0.27s ==============================
wse-model gate passed
```

The other lanes are worth running directly while you work:

```console
$ make integration
============================== 21 passed in 0.44s ==============================

$ python -m pytest tests/golden -q
13 passed in 0.03s

$ python tools/check_design_sources.py
design sources OK: 2 files, 246033 bytes
```

The four test lanes together report `307 passed`:

```console
$ python -m pytest tests/unit tests/contracts tests/golden tests/integration -q
307 passed in 1.26s
```

Widen only as far as the change requires: `make integration` for end-to-end
scenarios, `make coverage` for a coverage report, and `make acir` for the ACIR
layer. [Testing and gates](testing-and-gates.md) gives the change-to-gate matrix.

## The `agentic_circuit` bootstrap path

The `agentic-circuit` frontend is **not published on PyPI**. It is distributed
from a `PTO-ISA/pyCircuit` checkout, so a plain `pip install -e .` cannot bring it
in. This is deliberate: the framework is pinned by revision, not by a wheel.

Clone the framework next to this repository and run the bootstrap script:

```bash
git clone https://github.com/PTO-ISA/pyCircuit.git ../pyCircuit
make bootstrap PYCIRCUIT_ROOT=../pyCircuit
```

`make bootstrap` runs [`tools/bootstrap-dev.sh`](../../tools/bootstrap-dev.sh),
which:

1. verifies that the checkout exists and contains `python/semantic-core` and
   `python/agentic-circuit`;
2. creates `.venv` if it does not exist (unless `--no-venv`);
3. installs `pycircuit-semantic-core` and `agentic-circuit` from the checkout;
4. installs `wse-model` with the `dev` extra;
5. imports all three packages to prove the environment;
6. prints the pinned pyCircuit revision at the end.

Its arguments are `--pycircuit-root PATH`, `--venv PATH`, `--no-venv`, and
`--python BIN`; `PYCIRCUIT_ROOT` is the environment fallback and defaults to
`../pyCircuit`. Run it with `-h` for the usage text.

`AGENTS.md` requires any change that touches `src/wse_model/acir/` to state the
pinned pyCircuit revision in the pull request. The bootstrap output is where that
revision comes from.

### ACIR native tools

The `agentic_circuit` frontend lowers a model through four native binaries
(`acir-opt`, `acir-queue-plan`, `acir-queue-cxxgen`, `acir-cxxgen`) that are not
shipped as wheels. Build them once from the checkout:

```bash
bash tools/build-acir-tools.sh ../pyCircuit
```

The script needs LLVM/MLIR 22.1.8 (it auto-detects `llvm@22` under Homebrew or
`/usr/lib/llvm-22`), builds `PYC_BUILD_AGENTIC_CIRCUIT=ON`, verifies the four
binaries exist, and prints the environment variables to export before running the
ACIR tests. It honours `LLVM_DIR`, `MLIR_DIR`, and `BUILD_JOBS`. The
`acir` CI job runs the same sequence behind the `WSE_MODEL_ACIR_CI` repository
variable, so it stays out of the default gate.

## Worked CLI walkthrough

Every command below was run against this checkout. Long JSON objects are shown
trimmed to the fields under discussion; the full object is what the command
prints.

### Version and topology

```console
$ wse-model --version
wse-model 0.1.0

$ wse-model topology show
{
  "name": "mesh-5x8",
  "rows": 5,
  "cols": 8,
  "node_count": 40,
  "route_bits_bits": 80,
  "route_bits_bytes": 10,
  "profile": "calendar-40",
  "aicore_count": 40,
  "io_count": 0,
  "description": "Calendar baseline: 40 NoC nodes as a 5 x 8 mesh, node = r * 8 + c. Fixes routeBits at 80 bit.",
  "open_item": "Q1"
}
```

`--profile` selects the other readings of `Q1`
(`whitepaper-48`, `whitepaper-48-40c`), and `--links` appends the physical link
list.

### Encode the golden vector

```console
$ wse-model calendar encode --key golden
{
  "key": "golden",
  "description": "The Calendar §2.2.1 consistency anchor (source N00)",
  "source": 0,
  "node_count": 40,
  "width_bits": 80,
  "width_bytes": 10,
  "hex": "AA 03 20 00 E0 00 00 00 00 00",
  "pass_nodes": [0, 1, 2, 3, 4, 10, 18, 19],
  "land_nodes": [4, 19],
  "land_count": 2,
  "illegal_nodes": [],
  "expected_hex": "AA 03 20 00 E0 00 00 00 00 00",
  "matches_published": true
}
```

`--key row-allgather --source 0` reproduces the FFN `keyId 0` row
`FE FF 00 00 00 00 00 00 00 00` with `land_count` 7; `--key col-allgather --source 0`
reproduces `02 00 03 00 03 00 03 00 00 00` with `land_count` 3.

### Validate and emit the FFN table

```console
$ wse-model calendar validate
route table: built-in FFN example
OK (6 checks)
```

The text form lists diagnostics when the table fails. `--table PATH` validates a
table written by `calendar emit` or by the compiler; a failing table exits 1:

```console
$ wse-model calendar validate --table build/ffn.calendar.json
route table: build/ffn.calendar.json
OK (6 checks)
```

Emit the aligned `.rodata` segment under either layout:

```console
$ wse-model calendar emit --layout node-major
{
  "topology": "mesh-5x8",
  "layout": "node-major",
  "key_count": 2,
  "table_bytes": 1280,
  "d_cache_bytes_per_core": 64,
  "versions": { "topologyVersion": 1, "calendarVersion": 1, "routeVersion": 1 },
  "segment_bytes": 1280,
  "alignment_bytes": 64,
  "hex": "…"
}
```

`--out PATH` writes the raw 1280 B segment as well as printing the JSON.

### Run the FFN closure

```console
$ wse-model run ffn-allgather
{
  "scenario": "ffn-allgather",
  "table": { "topology": "mesh-5x8", "layout": "key-major", "key_count": 2, "table_bytes": 1280, "d_cache_bytes_per_core": 128, "versions": { "topologyVersion": 1, "calendarVersion": 1, "routeVersion": 1 } },
  "phases": [
    { "phase": "phase_b_row_allgather", "key_id": 0, "opcode": 1, "epoch": 1, "member_count": 32, "ok": true, "max_tree_depth": 7, "peak_link_load": 8, "expVal": 10752 },
    { "phase": "phase_c_col_allgather", "key_id": 1, "opcode": 1, "epoch": 2, "member_count": 32, "ok": true, "max_tree_depth": 3, "peak_link_load": 4, "expVal": 36864 }
  ],
  "all_complete": true
}
```

`--phase b` or `--phase c` runs one phase; `--layout node-major` runs the
transposed table. The per-phase `expVal` values above are read from the first
member state.

### Reports and open items

```console
$ wse-model report roofline
{
  "clock_hz": 1400000000.0,
  "points": [
    { "precision": "fp16", "tflops": 11.469, "balance_flops_per_byte": 11.469, "min_batch_for_compute_bound": 5.73, "weights_bytes_per_element": 2.0 },
    { "precision": "fp8",  "tflops": 45.875, "balance_flops_per_byte": 45.875, "min_batch_for_compute_bound": 22.94, "weights_bytes_per_element": 1.0 },
    { "precision": "fp4",  "tflops": 91.75,  "balance_flops_per_byte": 91.75,  "min_batch_for_compute_bound": 45.88, "weights_bytes_per_element": 0.5 }
  ]
}

$ wse-model open-items --status assumed
{
  "total": 31,
  "returned": 5,
  "by_resolution": { "open": 26, "assumed": 5, "resolved": 0 },
  "items": [ … C-2, C-5, C-6, C-7, C-9 … ]
}
```

### Check a compiled product

```console
$ wse-model check object --example
OK (5 checks)

$ wse-model check object --object examples/data/ffn-kernel-object.json
OK (5 checks)

$ wse-model check package
OK (26 checks)
```

The `check object` command runs the F1/F2/F3 self-checks of Calendar §3.10 over a
declared symbol manifest. It exits 1 when a check fails and 2 when neither
`--object` nor `--example` is given.

`check package` assembles the whole FFN deployment package and validates it,
including the same-`opcode` concurrency rule: `check package --concurrent`
declares the FFN's two phases concurrent and exits 1 with `V-OPCODE-CONCURRENT`,
which is the phase-split rule failing on purpose.

## Runnable examples

The `examples/` directory holds plain scripts with a `main()`:

```bash
python examples/ffn_allgather.py
python examples/validate_route_table.py
python examples/header_cost.py
python examples/check_kernel_object.py
python examples/roofline_two_verdicts.py
python examples/dispatch_and_refill.py
python examples/deployment_package.py
```

They are executed in CI, so an example that reaches past the public API fails the
build. See [`examples/README.md`](../../examples/README.md) for what each one
shows.

## Where to go next

- [Documentation map](../index.md) for the whole set.
- [Architecture overview](../architecture/overview.md) for the module map and the
  data flow.
- [Calendar and NoC](../architecture/calendar-noc.md) for the semantics.
- [CLI reference](../reference/cli.md) for every command and flag.
- [Testing and gates](testing-and-gates.md) before opening a pull request.
