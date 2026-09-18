# Changelog

All notable changes to wse-model are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository scaffolding: governance documents, packaging, lint/format
  configuration, CI, documentation skeleton, and the model package layout.
- Design sources under `docs/design/`: the WSE system architecture whitepaper
  v0.1 and the WSE Calendar scheme.
- Pure-Python semantic core for the WSE NoC and Calendar closure:
  - topology and platform descriptors with both the 40-node and 48-node
    readings of open item `Q1` kept explicit;
  - `routeBits` bit-pair codec with the Calendar §2.2.1 golden vector;
  - `CalendarRouteEntry` 16 B layout and register-pair view;
  - `keyId` / `opcode` / `redOp` / `epoch` / `expVal` semantics;
  - structural validation: legal bit pairs, induced subgraph is a tree,
    source on path, land-set completeness, send/receive conservation,
    `selfLand` consistency;
  - stateless per-hop NoC forwarding and `CalReg` slot release model;
  - flit header overhead accounting.
- Unit and contract tests for the above, including the frozen FFN `keyId 0`
  and `keyId 1` encodings.
- `wse-model` CLI with `topology`, `calendar`, `run`, `report`, `check`, and
  `open-items` command groups, all with `--json` output.
- Machine-readable schemas under `schemas/`: the route-table descriptor and the
  kernel-object manifest, each with contract tests that enforce them.
- Runnable scenarios under `examples/`, executed as integration tests:
  the FFN two-phase AllGather closure, a route-table validation walk-through,
  the flit-header cost comparison across the two readings of `Q1`, and the
  F1/F2/F3 compiled-product self-checks.
- Compiler-side model (`wse_model.compiler`): the F1/F2/F3 prohibitions of
  Calendar §3.10 evaluated over a declared symbol and section manifest, so the
  invariant is checkable without a compiler and a toolchain that cannot produce
  the manifest fails rather than passing by omission.
- Compiler-side deployment package (`wse_model.compiler.package`): the five
  artifacts of whitepaper §13.3, the artifact version agreement, the per-call-site
  immediates, and the same-`opcode` concurrency rule of Calendar §2.3.1/§2.7.1 as
  a check rather than a re-derivation. `wse-model check package` reports 26
  distinct checks.
- A public-API contract test that pins every namespace's `__all__`.
- `wse_model.analysis.dcache`: the D-cache residency and cold-miss account of
  Calendar §3.8, including the 4x entry-to-line amplification, the
  `Batcher.mem` versus DDR refill split, and the `C-9` layout comparison.
- `wse_model.analysis.latency`: the five-block latency budget of whitepaper
  §19.1, with the two open inputs (`Q3`, `Q9`) required rather than defaulted.
- Repository-standards gate (`tools/check_repo_standards.py`) and a script that
  builds the native ACIR tools (`tools/build-acir-tools.sh`).
- The `agentic_circuit` model layer under `src/wse_model/acir/`, expressing the
  same Calendar node semantics as schedulable ACIR processes.

### Changed

- The `agentic-circuit` frontend is not published on PyPI, so the model layer
  is bootstrapped from a `PTO-ISA/pyCircuit` checkout; the pure-Python
  semantic core keeps no runtime dependencies.
