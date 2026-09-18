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
- `wse-model` CLI with `topology`, `calendar`, and `run` command groups.
