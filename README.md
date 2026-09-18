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
| **AICORE** | Cube/Vector throughput, local DRAM bandwidth, L0A/L0B/L0C/L1/UB capacity, MTE1–MTE4 pipelines | [Whitepaper §3](docs/design/wse-system-architecture-whitepaper.md) |
| **Batcher / UB bus** | single external entry point, dispatch and gather-back, cold-miss refill path | [Whitepaper §6](docs/design/wse-system-architecture-whitepaper.md) |
| **Compiler** | group/collective recognition, phase splitting, immediate materialization, `.rodata` emission, self-checks F1–F3 | [Whitepaper §10, §13](docs/design/wse-system-architecture-whitepaper.md) |
| **Runtime** | load / launch / steady-state frequencies, three-version check, `CalReg` atomic install, kickstart | [Whitepaper §12, §14](docs/design/wse-system-architecture-whitepaper.md) |

## Repository layout

```text
src/wse_model/
  calendar/    routeBits codec, keys, opcodes, epochs, expVal, validation
  noc/         2D mesh, flit format, stateless forwarding, CalReg
  core/        AICORE pipelines, buffers, local DRAM
  host/        Batcher, UB bus, runtime and loader
  compiler/    frontend IR, group/collective lowering, table emission
  analysis/    roofline, bandwidth budget, latency breakdown
  acir/        agentic_circuit model modules (ACPy -> ACIR -> gfsim)
  data/        canonical topology and platform descriptors (JSON)
docs/          design sources, architecture, requirements, decisions
schemas/       machine-readable schemas for descriptors and reports
tests/         unit, contract, integration, golden
tools/         developer and bootstrap scripts
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

To build and simulate the `agentic_circuit` model layer you also need the
pyCircuit checkout that provides the `agentic-circuit` distribution (it is not
published on PyPI):

```bash
git clone https://github.com/PTO-ISA/pyCircuit.git ../pyCircuit
make bootstrap PYCIRCUIT_ROOT=../pyCircuit
```

## Quick start

```bash
# Inspect the canonical topology and its derived route-bit golden vectors
wse-model topology show

# Encode one row-wise AllGather key and validate it
wse-model calendar encode --key row-allgather --source 0

# Validate every key in a compiled route table
wse-model calendar validate --table build/ffn.calendar.json

# Run the FFN two-phase AllGather scenario end to end
wse-model run examples/ffn_allgather.py
```

See [`docs/index.md`](docs/index.md) for the full documentation map and
[`examples/`](examples/) for runnable scenarios.

## Status

Pre-alpha. The semantic core and the Calendar/NoC closure are the current
focus; AICORE, Batcher, and the runtime model follow. The model tracks the
v0.1 whitepaper set dated 2026-09-17 and reports every unresolved item from
[Appendix A](docs/design/wse-system-architecture-whitepaper.md) rather than
assuming a value; see [`docs/roadmap.md`](docs/roadmap.md).

## Contributing

Development changes land through pull requests. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`AGENTS.md`](AGENTS.md) before starting, and run `make check` before opening a
change.

## License

BSD 3-Clause. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
