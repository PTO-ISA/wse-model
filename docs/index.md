# WSE Model documentation

WSE is a **bandwidth-for-latency** accelerator: each AICORE owns a private 384 MB
local DRAM at 1 TB/s instead of sharing a global HBM. That removes the shared
memory path between cores, so a split tensor can only be reassembled by explicit
collective communication over the NoC. **Calendar** is the scheme that makes that
communication cheap by moving both the path decision and the timeslot decision
into compile time.

This repository is the **architecture-level executable model** of that system. It
turns the two design documents into code that can encode a route bitmap, validate
a compiled route table, forward flits, account payload bytes against `expVal`, and
compute the closed-form performance figures — and it reports, rather than guesses,
every value the design documents leave open.

The model tracks the v0.1 whitepaper set dated 2026-09-17. The pure-Python
Calendar/NoC closure is implemented and tested, as are the AICORE, Batcher/UB,
and runtime models and the compiled-product self-checks. The compiler frontend and
the `agentic_circuit` layer are not finished. The [roadmap](roadmap.md) states
exactly what exists.

## The two-layer model

The model is deliberately split into two layers with **one semantics**
([decision 0002](decisions/0002-two-layer-model.md)).

1. **Pure-Python semantic core** — every package under
   [`src/wse_model/`](../src/wse_model/) except the planned `acir/`. It owns the
   encoding, legality, conservation, capacity, and closed-form performance rules.
   It declares `dependencies = []`, runs anywhere with Python 3.10+, and is the
   layer that golden vectors, contract tests, and the compiler boundary are
   written against. **This layer is the authority.**
2. **ACIR model layer** — `src/wse_model/acir/`. It expresses the same rules as
   schedulable `agentic_circuit` processes, queues, resources, and committed
   state, so the model can be simulated with `gfsim` and emitted to
   PYC/C++/Verilog. It must not disagree with the core. It is in progress: its
   tests are opt-in (`make acir`, requiring the pyCircuit native toolchain) and
   are not exercised by the default gate. The core is the authority.

A change to a rule lands in the core **with a unit test first**, then is mirrored
into the ACIR layer. Changes that touch `acir/` additionally require the
`agentic_circuit` closure and must state the pinned pyCircuit revision.

## How to read the design sources

`docs/design/` holds the two **read-only source documents**. They are verbatim
input material, guarded by a SHA-256 manifest (`docs/design/MANIFEST.json`) and
checked by [`tools/check_design_sources.py`](../tools/check_design_sources.py) in
the `design-fidelity` CI job.

| Document | What it fixes |
| --- | --- |
| [WSE system architecture whitepaper v0.1](design/wse-system-architecture-whitepaper.md) | System positioning, hardware architecture, software stack, compile/load/run flow, MoE FFN and attention mapping, performance trade-offs, Appendix A open items, Appendix B glossary |
| [WSE Calendar scheme](design/wse-calendar-scheme.md) | `routeBits`, `opcode`/`redOp`, logical identity, the 16 B `CalendarRouteEntry`, compile-time generation, the `.rodata`/D-cache and `CalReg` delivery chains, the two new hardware instructions, §6.3 open items, glossary |

Read them in that order on a first pass: the whitepaper gives the system context
that makes Calendar's constraints intelligible. Then read this documentation in
the order below.

The design documents are **not** edited in place. When the model must diverge, or
when it adopts a reading of an open item, the divergence is recorded in
[`docs/decisions/`](decisions/index.md) and the open item's status is updated in
[`wse_model.open_items`](../src/wse_model/open_items.py).

### Where the design sources are open, and how the model reacts

Whitepaper Appendix A (`Q1`–`Q12`) and Calendar §6.3 (`S-1`–`S-7`, `C-1`–`C-12`)
list values the documents explicitly do not fix. The model never substitutes a
plausible default for one. Instead:

- the value is registered in `wse_model.open_items` with an owner and a
  `Resolution`;
- code whose result changes materially between the readings calls
  `require_resolved` and fails closed;
- an adopted reading is recorded in `docs/decisions/` and referenced from the
  registry entry.

See [Open items](reference/open-items.md) for the live registry, and
[decision 0003](decisions/0003-keep-open-items-explicit.md) for the mechanism.

## Documentation map

| Page | Read it for |
| --- | --- |
| [Roadmap](roadmap.md) | What exists today, what does not, and which open items gate each future stage |
| [Architecture overview](architecture/overview.md) | The module map, the data flow from a route bitmap to `expVal` completion, and the layering rules |
| [Calendar and NoC](architecture/calendar-noc.md) | The deep dive: bit order, the 16 B entry, induced-tree rule, forwarding, `CalReg`, epochs, the seven `expVal` contracts, symmetric addressing, the §2.7.2 check set, and the two table layouts |
| [AICORE](architecture/aicore.md) | The platform constants, the roofline arithmetic and its two verdicts, the `wse_model.core` model, and what is not modelled |
| [Batcher and UB bus](architecture/batcher-ub.md) | The single external entry point, the two disjoint paths, the nine-lane bus, the refill account, and the declared `Q3` parameters |
| [Runtime and loading](architecture/runtime.md) | The three frequency tiers, three dispatch chains, version check, kickstart, and the launch-boundary drain rule |
| [Compiler](architecture/compiler.md) | The compiled-product self-checks (F1/F2/F3), the deployment package, the call-site immediates, and the same-`opcode` concurrency rule |
| [Requirements index](requirements/index.md) | How requirements are written, identified, and validated |
| [Calendar closure requirements](requirements/calendar-closure.md) | The numbered, implemented-and-tested requirements for the Calendar/NoC closure |
| [Decision records](decisions/index.md) | The ADR convention, when a record is required, and the index of accepted records |
| [Getting started](development/getting-started.md) | Prerequisites, environment setup, the `agentic_circuit` bootstrap path, and a worked CLI walkthrough |
| [Testing and gates](development/testing-and-gates.md) | The change-to-gate matrix, the exact commands, and what each gate proves |
| [Engineering standards](development/engineering-standards.md) | Code style, typing, docstrings, test conventions, and the fail-closed error policy |
| [CLI reference](reference/cli.md) | Every command, flag, output shape, and exit code |
| [Descriptors and schemas](reference/descriptors.md) | The route-table, kernel-object, and deployment-package JSON, field by field |
| [Open items](reference/open-items.md) | The full registry, grouped by status, generated from the code |
| [Glossary](reference/glossary.md) | Terminology from whitepaper Appendix B and the Calendar glossary, with the implementing symbol |

## Quick orientation

```bash
# The canonical topology and the Calendar §2.2.1 golden vector
wse-model topology show
wse-model calendar encode --key golden

# Validate and emit the compiled FFN route table
wse-model calendar validate
wse-model calendar emit --layout node-major

# Run the FFN two-phase AllGather closure end to end
wse-model run ffn-allgather

# What the design leaves open
wse-model open-items --status assumed
```

[Getting started](development/getting-started.md) shows the real output of each of
these, and [CLI reference](reference/cli.md) documents every flag.
