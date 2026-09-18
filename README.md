# WSE Model

<p align="center">
  <strong>Architecture-level model of the WSE accelerator, built on the pyCircuit <code>agentic_circuit</code> frontend.</strong>
</p>

<p align="center">
  <a href="https://github.com/PTO-ISA/wse-model/actions/workflows/ci.yml"><img src="https://github.com/PTO-ISA/wse-model/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/PTO-ISA/wse-model" alt="BSD 3-Clause license"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10 or later"></a>
  <a href="docs/architecture/overview.md"><img src="https://img.shields.io/badge/model-architecture-blue" alt="Architecture model"></a>
</p>

WSE is a **bandwidth-for-latency** accelerator: each AICORE owns a private
384 MB local DRAM at 1 TB/s instead of sharing a global HBM, which turns the
decode-stage memory-bound operators (MoE FFN, attention Q/K/V/O projection)
into compute-bound work. With no global memory there is also no shared-memory
path between cores, so every split tensor must be reassembled by explicit
collective communication over the NoC — orchestrated by **Calendar**, which
moves both path and timeslot decisions into compile time.

This repository is the executable model of that system.

## What is modeled

| Area | Model content | Source of truth |
| --- | --- | --- |
| **Calendar encoding** | `routeBits` bit-pair bitmap, `CalendarRouteEntry` layout, `keyId`/`opcode`/`redOp`/`expVal`, golden vectors | [Calendar §2](docs/design/wse-calendar-scheme.md) |
| **Calendar validation** | legal bit pairs, induced-subgraph-is-a-tree, reachability, land-set completeness, send/receive conservation, `selfLand` consistency | [Calendar §2.7.2](docs/design/wse-calendar-scheme.md) |
| **NoC** | 2D mesh topology, flit header overhead, stateless per-hop forwarding, `CalReg` slot release, merge/de-duplication | [Whitepaper §5](docs/design/wse-system-architecture-whitepaper.md), [Calendar §1.8](docs/design/wse-calendar-scheme.md) |
| **AICORE** | Cube/Vector throughput with tile-accurate `M`-fill, local DRAM with the 2 KB page rule, L0A/L0B/L0C/L1/UB fit checks, MTE1–MTE4 pipeline independence | [Whitepaper §3](docs/design/wse-system-architecture-whitepaper.md) |
| **Batcher / UB bus** | single external entry point, four responsibilities at three frequencies, the two disjoint paths, 9-lane bus, shared-`Batcher.mem` refill split | [Whitepaper §6](docs/design/wse-system-architecture-whitepaper.md) |
| **Compiler** | the F1/F2/F3 compiled-product prohibitions over a declared symbol manifest | [Whitepaper §10](docs/design/wse-system-architecture-whitepaper.md), [Calendar §3.10](docs/design/wse-calendar-scheme.md) |
| **Runtime** | load / per-launch / steady-state tiers, the three dispatch chains, three-version fault, `CalReg` install window, kickstart, wave and drain constraints | [Whitepaper §12, §14](docs/design/wse-system-architecture-whitepaper.md) |
| **Performance analysis** | balance points and minimum batches, the five-block latency budget, the D-cache residency account, and both a first-order and a tile-accurate roofline verdict ([decision 0006](docs/decisions/0006-two-roofline-verdicts.md)) | [Whitepaper §19](docs/design/wse-system-architecture-whitepaper.md), [Calendar §3.8](docs/design/wse-calendar-scheme.md) |

## Repository layout

```text
src/wse_model/
  calendar/    routeBits codec, keys, opcodes, epochs, expVal, validation, table
  noc/         2D mesh, flit format, stateless forwarding, CalReg, delivery
  core/        AICORE pipelines, local DRAM, on-chip buffers, Cube/Vector timing
  host/        Batcher, UB bus, load/launch tiers, scheduling constraints
  compiler/    compiled-product self-checks (F1/F2/F3)
  analysis/    roofline, bandwidth, D-cache budget, latency breakdown
  acir/        agentic_circuit model modules (ACPy -> ACIR -> gfsim)
docs/          design sources, architecture, requirements, decisions
schemas/       machine-readable schemas for descriptors and reports
tests/         unit, contract, integration, golden, acir
tools/         developer, bootstrap, and standards scripts
examples/      runnable end-to-end scenarios
```

The model is deliberately split into **two layers**:

1. **Semantic core** (`wse_model.calendar`, `wse_model.noc`, ...) — pure
   Python. It owns the encoding, legality, and conservation rules. It runs
   everywhere with no toolchain and is the layer that golden vectors and
   compiler checks are written against.
2. **ACIR model** (`wse_model.acir`) — `agentic_circuit` modules that express
   the same semantics as schedulable processes, queues, resources, and
   committed state, so the model can be simulated with `gfsim` and emitted to
   PYC/C++/Verilog.

## Getting started

```bash
git clone https://github.com/PTO-ISA/wse-model.git
cd wse-model

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The pure-Python semantic core works with that alone:

```bash
make check
```

To build and test the `agentic_circuit` model layer you also need a pyCircuit
checkout, which provides the `agentic-circuit` distribution (it is not published
on PyPI) and the native ACIR binaries:

```bash
git clone https://github.com/PTO-ISA/pyCircuit.git ../pyCircuit
make bootstrap PYCIRCUIT_ROOT=../pyCircuit      # Python frontend
make acir-tools PYCIRCUIT_ROOT=../pyCircuit     # native acir-opt and friends
make acir                                       # the ACIR-layer tests
```

The native build needs LLVM/MLIR 22.1.8; `tools/build-acir-tools.sh` finds it
automatically under Homebrew or `/usr/lib/llvm-22`, or takes `LLVM_DIR` and
`MLIR_DIR`. The default gate deliberately does not require it.

## Quick start

```bash
# Inspect the canonical topology and its derived route-bit golden vectors
wse-model topology show
wse-model calendar encode --key golden

# Encode one FFN logical identity for a specific core
wse-model calendar encode --key row-allgather --source 0

# Validate the compiled route table (omit --table for the built-in FFN example)
wse-model calendar validate
wse-model calendar validate --table build/ffn.calendar.json

# Emit the aligned .rodata segment, under either layout
wse-model calendar emit --layout node-major

# Run the FFN two-phase AllGather closure end to end
wse-model run ffn-allgather

# AICORE timing, the Batcher/runtime picture, and the D-cache budget
wse-model report matmul --m 1 --k 4096 --n 4096 --precision fp16
wse-model report host
wse-model report runtime
wse-model report dcache

# The compiled-product self-checks of Calendar §3.10
wse-model check object --example

# Closed-form analysis and the unresolved design items
wse-model report roofline
wse-model report overhead
wse-model open-items --status open
```

Every command accepts `--json` for scripting. See
[`docs/reference/cli.md`](docs/reference/cli.md) for the full reference,
[`examples/`](examples/) for runnable scenarios, and
[`docs/index.md`](docs/index.md) for the documentation map.

## Status

Pre-alpha. The pure-Python semantic core and the Calendar/NoC closure are
implemented and tested; the ACIR model layer, the AICORE model, the Batcher/UB
model, and the compiler/runtime model follow. The model tracks the v0.1
whitepaper set dated 2026-09-17 and reports every unresolved item from
[Appendix A](docs/design/wse-system-architecture-whitepaper.md) rather than
assuming a value; see [`docs/roadmap.md`](docs/roadmap.md) and
[`docs/reference/open-items.md`](docs/reference/open-items.md).

## Contributing

Development changes land through pull requests. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`AGENTS.md`](AGENTS.md) before starting, and run `make check` before opening a
change.

## License

BSD 3-Clause. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
