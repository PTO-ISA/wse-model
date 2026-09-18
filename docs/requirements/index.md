# Requirements

This repository keeps its normative statements as **numbered, test-backed
requirements** under `docs/requirements/`. A requirement is not a wish or a plan:
it is a statement the implemented code satisfies today and that a named test
proves. Anything not yet implemented belongs in the [roadmap](../roadmap.md), not
here.

## Identification

Requirements are identified as `WSEMODEL-<AREA>-NNN`:

- `WSEMODEL` is the project id prefix declared in
  [`ndf.yaml`](../../ndf.yaml) under `id_prefixes`.
- `<AREA>` is a short uppercase area tag. The current area is `CAL` (the
  Calendar/NoC closure).
- `NNN` is a zero-padded sequence number, unique within the area.

The ids are stable. A requirement is never renumbered; it is edited when its
statement changes, and superseded requirements are called out explicitly in the
change that supersedes them. Because the requirements are backed by tests, a
change that breaks one is a change that breaks behaviour, and the test fails
before the id needs editing.

## Authoring rules

Each requirement states exactly three things:

1. **Statement** — one normative sentence, in the present tense, describing a rule
   the model enforces.
2. **Design source** — the section of
   [`docs/design/`](../design/wse-system-architecture-whitepaper.md) that fixes
   the rule. A rule with no design-source citation is either a decision (see
   below) or a bug.
3. **Proving test** — the exact test function name that fails if the rule is
   removed. A requirement whose only evidence is prose is not accepted.

A requirement must hold across the whole supported Python range (3.10–3.13) and
must be provable without the `agentic_circuit` toolchain. Rules that require that
toolchain belong to the ACIR layer and are gated separately.

## Requirements and decisions

The two are complementary. A **requirement** records what the model does because
the design source says so. A [**decision record**](../decisions/index.md) records
what the model does where the design source is silent or open, or where the model
must diverge. The two meet at the open-item registry: an adopted reading moves an
item to `Resolution.ASSUMED`, names the decision record, and — once a test exists —
can be stated as a requirement as well.

## `ndf.yaml`

[`ndf.yaml`](../../ndf.yaml) is the machine-readable declaration of where
requirements live and what they depend on:

```yaml
format_version: "0.2"
project: wse-model
roots:
  - docs/requirements/**/*.md
id_prefixes:
  - WSEMODEL
domains:
  - compiler
  - model
  - noc
  - runtime
  - tile
policies: {}
dependencies:
  pycircuit:
    path: vendor/pyCircuit
    graph: true
  pto-spec:
    path: vendor/pto-spec
    graph: true
```

What it fixes:

- `roots` — only Markdown under `docs/requirements/` contributes requirement ids.
  Architecture, decisions, reference, and development pages do not.
- `id_prefixes` — every requirement id starts with `WSEMODEL`. A new area must use
  the same prefix with a new area tag, not a new prefix.
- `domains` — requirements are tagged by domain. The Calendar/NoC closure maps to
  `model` and `noc`; the unimplemented areas (`compiler`, `runtime`, `tile`) have
  no requirements yet because they have no code to prove.
- `policies` — empty: there are no per-domain policy overrides.
- `dependencies` — the external specification graphs the model tracks. Note that
  the `path:` values are the declared relative locations, and the repository does
  **not** vendor those checkouts. In practice the pyCircuit frontend is consumed
  through `PYCIRCUIT_ROOT` (default `../pyCircuit`), as described in
  [Getting started](../development/getting-started.md).

## Index

| Area | Requirements | Page |
| --- | --- | --- |
| `CAL` — Calendar/NoC closure | 126 | [Calendar closure](calendar-closure.md) |
