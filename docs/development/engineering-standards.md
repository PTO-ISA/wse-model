# Engineering standards

These are the conventions the model follows and the gates enforce. They are the
mechanical part of `AGENTS.md`; the design rules are in that file and in
[Architecture overview](../architecture/overview.md).

## Code style

Configuration lives in [`pyproject.toml`](../../pyproject.toml), so the tool is
the authority rather than this page.

| Setting | Value |
| --- | --- |
| Line length | 100 (`[tool.ruff] line-length = 100`) |
| Target | `py310` |
| Lint rules | `select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "T20"]`, `ignore = ["E501"]` |
| Format | `ruff format`, `quote-style = "double"` |
| Exclusions | `docs/design` |

`E501` is ignored because the formatter owns wrapping; the 100-column limit is
still the target for hand-written code. `T20` bans `print` in library code, with
targeted exceptions: `src/wse_model/cli.py`, `tests/**/*.py`, and `tools/*.py` may
print, because that is their interface. `N803`/`N806`/`N815` are relaxed for
`src/wse_model/acir/**` and for tests, where the design's own names (`P`, `L`,
`rbLo`) are the point.

Run `make format` to apply safe fixes and formatting. CI runs both
`ruff check .` and `ruff format --check .`, so a change must be formatted, not
just lint-clean.

## Imports and module shape

- Imports are sorted by `ruff`'s `I` rules.
- Intra-package imports are absolute: `from wse_model.calendar.entry import ...`,
  never a relative import.
- Every module starts with `from __future__ import annotations`.
- Every module defines `__all__`, listing its public names. A symbol that is not
  in `__all__` is internal, even if importable.
- `wse_model/__init__.py` is deliberately minimal: errors, topology, and the
  version. Domain types are imported from their own packages, which keeps the
  package surface stable (the contract tests pin it).

## Typing

The model is annotated but does not require a type checker to run.

- All public functions and methods are annotated, including `-> None`. Private
  helpers are annotated too; the codebase reads as if `disallow_untyped_defs` were
  on even though `[tool.mypy]` leaves it off for gradual adoption.
- `[tool.mypy]` sets `python_version = "3.10"`, `warn_return_any = true`,
  `warn_unused_configs = true`, and `files = ["src/wse_model"]`.
- `make typecheck` runs `python -m mypy src/wse_model`. `mypy` is **not** in the
  `dev` extra, so install it explicitly to run that target; it is not part of
  `make check` or a required CI job.
- Widely-shared values use `dataclass(frozen=True)` for immutability, and
  `__slots__` for the small stateful classes. Mutable build-time objects (for
  example `CalendarRouteTable`) are plain dataclasses.
- Do not use a mutable default argument; use `field(default_factory=...)`.

## Docstrings

Every module, public class, and public function has a docstring. The style is
**reStructuredText field lists and cross-references**, the convention Sphinx and
MkDocs' Python tooling understand:

- Cross-references use roles such as `:mod:`wse_model.calendar.validate``,
  `:class:`CalendarError``, `:attr:`, `:meth:`, and `:func:`.
- The `__all__` list is the docstring's contract; a name listed there is public.
- Inline literals use double backticks.
- Constants are documented with a `#:` comment immediately above them, so the
  value and its source sit together (for example `ENTRY_SIZE_BYTES` and
  `EPOCH_TAG_MIN_BITS`).
- Design citations are prose, not links: "Calendar §2.6", "whitepaper §10.3".
  They name the source; they do not re-encode it.

Some docstrings are long on purpose. A rule that is subtle (the induced-subgraph
tree test, the `rbHi` ignore rule, the `expVal` contracts) explains *why* in the
module docstring, because the reasoning is what a future change would otherwise
break. Keep that, and keep it accurate.

## Tests

Test conventions are fixed by `[tool.pytest.ini_options]`:

| Setting | Value |
| --- | --- |
| `testpaths` | `tests` |
| `pythonpath` | `src` |
| Files | `test_*.py` |
| Classes | `Test*` |
| Functions | `test_*` |
| `addopts` | `-ra --tb=short` |

Markers declare the lane, and the Makefile selects on them:

| Marker | Lane | Command |
| --- | --- | --- |
| `unit` | fast, pure-Python semantic tests, no toolchain | `make unit` |
| `contract` | interface and schema stability | `make contract` |
| `integration` | end-to-end scenarios | `make integration` |
| `acir` | requires the `agentic-circuit` frontend and its native tools | `make acir` |

Apply the marker at module level with `pytestmark = pytest.mark.unit` (or a list,
as `tests/golden/test_golden_vectors.py` does). A test file belongs in the
directory that matches its lane: `tests/unit`, `tests/contracts`,
`tests/integration`, `tests/golden`, `tests/acir`.

Naming is behavioural, not structural: `test_illegal_bit_pair_is_reported_with_its_node`
says what must happen, not which function runs. When a test proves a requirement,
the requirement cites its exact function name (see
[Calendar closure requirements](../requirements/calendar-closure.md)).

Two rules from `CONTRIBUTING.md` and `AGENTS.md` that tests must respect:

- **Do not weaken a faithfulness test, golden vector, or fail-closed check to make
  a change pass.** A failing golden test means the model moved, not that the
  expectation is stale.
- A new behaviour needs a test that **fails without the change**. A test that
  passes both before and after proves nothing.

## Error handling: fail closed

The model fails closed. Every illegal encoding, structural violation, version
mismatch, or violated contract raises; nothing is a warning unless the design says
it is advisory (the two NoC timing guarantees and the alignment/footprint budgets
are warnings, and are reported as such).

Use the specific subclass, never a bare `Exception`, and never `raise
WseModelError` when a more precise type exists. The hierarchy in
[`wse_model/errors.py`](../../src/wse_model/errors.py):

| Error | Raised when |
| --- | --- |
| `WseModelError` | base class for everything the model raises |
| `TopologyError` | a node, coordinate, or link is outside the declared topology |
| `CalendarError` | base class for Calendar encoding and validation faults |
| `IllegalBitPairError` | a `{P, L}` pair took the value `01` (`L=1` with `P=0`) |
| `RouteTreeError` | the `{P=1}` induced subgraph is not a tree containing the source |
| `LandSetError` | the land set, `landCount`, or `selfLand` bit disagrees |
| `ConservationError` | send/receive byte conservation failed for a destination |
| `VersionMismatchError` | `topologyVersion` / `calendarVersion` / `routeVersion` disagree |
| `ReceiveContractError` | one of the seven `expVal` contracts (Calendar §4.5.2) was violated |
| `OpenItemError` | a value the design leaves open was requested without a choice |

Two conventions matter as much as the types:

- **A message explains the consequence and cites the source.** For example
  `ConservationError` says the two figures "must be equal because the value is the
  device-side expVal (Calendar §2.7.2)". A reader should not need the code to
  understand the fault.
- **An open value is refused, not defaulted.** Code that would produce a
  materially different answer under the readings of an open item calls
  `wse_model.open_items.require_resolved(item_id, consumer=...)` and lets
  `OpenItemError` propagate. See
  [decision 0003](../decisions/0003-keep-open-items-explicit.md).

Validation code accumulates `Diagnostic`s in a `ValidationReport` and converts
them to a `CalendarError` with `raise_if_failed()` at the boundary; the report can
also be inspected programmatically and serialised to JSON. Use that pattern for a
check set rather than raising on the first finding.

## Commits, pull requests, and provenance

- Branch names are descriptive and scoped to one change family.
- Keep one logical change per commit; rebase rather than merge `main`.
- **Do not add AI co-author lines to commits or pull request text.** This is
  `AGENTS.md` rule 8, and `tools/check_repo_standards.py` fails the build if a
  tracked text file contains one.
- A pull request description states what semantic rule or capability changed and
  why, the design section or decision record it follows, the exact commands run
  and their result, and any open item newly resolved or discovered.
- A change that touches `src/wse_model/acir/**` states the pinned pyCircuit
  revision.
- Design documents under `docs/design/` are never edited. A divergence lands in
  `docs/decisions/` and the manifest is regenerated with
  `python tools/check_design_sources.py --update` only after a reviewed
  design-document update.

## Related pages

- [Testing and gates](testing-and-gates.md) for the commands and what they prove.
- [Decision records](../decisions/index.md) for when a record is required.
- [`AGENTS.md`](../../AGENTS.md) for the design-level hard rules.
