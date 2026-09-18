# Compiler

The model is a **consumer** of compiled artifacts, not a compiler. `wse_model.compiler`
models what the toolchain must emit and the checks the product must pass — the
F1/F2/F3 prohibitions of Calendar §3.10, the per-call-site immediates of
Calendar §2.7.3 step 4, the artifact list of whitepaper §13.3, and the
same-`opcode` concurrency rule of Calendar §2.3.1 / §2.7.1. It does **not** contain
an IR, group recognition, lowering, or `.rodata` emission; see
[What is not modelled](#what-is-not-modelled).

Design sources: whitepaper [§7](../design/wse-system-architecture-whitepaper.md),
[§8](../design/wse-system-architecture-whitepaper.md),
[§10](../design/wse-system-architecture-whitepaper.md),
[§13](../design/wse-system-architecture-whitepaper.md); Calendar
[§2.3.1](../design/wse-calendar-scheme.md), [§2.5](../design/wse-calendar-scheme.md),
[§2.7](../design/wse-calendar-scheme.md), [§3.10](../design/wse-calendar-scheme.md).

## The compiled-product self-checks (F1/F2/F3)

[`wse_model.compiler.selfcheck`](../../src/wse_model/compiler/selfcheck.py) checks
a **declared** symbol and section manifest rather than parsing ELF. That is what
`llvm-nm` / `llvm-readelf` would report, and making it explicit means the invariant
is testable without a compiler and a toolchain that cannot produce the manifest
fails the check rather than passing by omission.

| Rule | Rejected | Diagnostics |
| --- | --- | --- |
| **F1** | any writable Calendar static state in `.data` / `.bss` — under SPMD a writable global is shared by every core and is a race that makes epochs and route bits non-deterministic | `F1` |
| **F2** | a materialised `CalendarKeyRef` (`kRowAllGather`, `kColAllGather`), because taking its address demotes `opcode` from an I-cache immediate to a D-cache load | `F2` |
| **F3** | `kCalendarRoute` not being a read-only `.rodata` object, `.rodata` below 64 B alignment, or a size other than `keyCount × nodeCount × 16` | `F3`, `F3-PADDING` (warning) |

The model types are `ObjectFile`, `Symbol`, `SymbolKind`, `Section`, and
`SectionInfo`; `load_object_file` reads a `wse-model/kernel-object/1` JSON manifest
from a path, a JSON string, or a mapping; and `check_compiled_product` runs the
three rules and returns a `ValidationReport`. A symbol is Calendar-owned if its
name contains `calendar` case-insensitively or starts with `kCal`.

`wse-model check object` exposes this; the manifest format is documented in
[Descriptors and schemas](../reference/descriptors.md).

## The deployment package

[`wse_model.compiler.package`](../../src/wse_model/compiler/package.py) assembles
the compiler's outputs into one object so the package can be validated as a whole
rather than in pieces.

### The five artifacts

`deployment_artifacts()` returns the whitepaper §13.3 list:

| Artifact | Form | Destination |
| --- | --- | --- |
| kernel machine code | `.text` | DDR code segment |
| `routeBits` static table | `.rodata`, 64 B aligned | DDR data segment |
| `CalReg` mirror | separate binary section | NoC node timeslot registers |
| three version numbers | metadata | checked at load time |
| model weights | per-core slices | each core's local DRAM |

### Call-site immediates

`CallSiteImmediate` is the constant bundle one Calendar call site compiles down to
(Calendar §2.7.3 step 4): `key_id`, `opcode`, `red_op`, `route_version`, plus the
conservation-checked `exp_val`, `capacity`, `self_off_stride`, and `n_burst`. Its
`key_ref` property returns the indivisible `CalendarKeyRef`, which is invariant
`O1`'s landing point: the call site cannot pass a `keyId` from one identity with an
`opcode` from another. A reserved `opcode` is refused at construction.

`DeploymentPackage.call_site_immediates()` derives one bundle per logical identity
from the table and its geometry. For the FFN it produces the published numbers:
phase B with `expVal` 10752, `capacity` 12288, `selfOffStride` 192, `nBurst` 8; and
phase C with `expVal` 36864, `capacity` 49152, `selfOffStride` 1536.

### `build_package` and `DeploymentPackage.validate`

`build_package(table=..., calreg=..., kernel_object=..., weight_shard_bytes=...,
conflict_proofs=...)` refuses outright if the table and the `CalReg` mirror carry
different `calendarVersion` values, because Calendar §2.7 says both come from one
algorithm call.

`DeploymentPackage.validate(concurrent=...)` then runs, and merges into one
`ValidationReport`:

1. the full route-table check set (`CalendarRouteTable.validate`);
2. the F1/F2/F3 product checks, when a kernel object is supplied;
3. **artifact version agreement** — the `CalReg` mirror's `calendarVersion` must
   equal the table's (`V-CALREG-VERSION`), and a `CalReg` entry no identity uses is
   a warning (`V-CALREG-ORPHAN`);
4. the same-`opcode` concurrency rule and the presence of the algorithm's
   `conflictProof`;
5. weight-shard 2 KB page alignment (`V-WEIGHT-ALIGN`);
6. `.rodata` 64 B alignment (`V-RODATA-ALIGN`).

`ValidationReport.merge` preserves the sub-report's `checks_run`, so a skipped
check cannot look like a passing one. The FFN package reports **26 distinct
checks**; `wse-model check package` prints `OK (26 checks)`.

`DeploymentPackage.to_dict()` emits the package as JSON under the schema name
`wse-model/deployment-package/1`. There is no standalone JSON Schema file or
contract test for that object yet; the route-table and kernel-object schemas are
the frozen ones.

### The same-`opcode` concurrency rule

`check_opcode_domains(table, concurrent=..., proofs=...)` implements Calendar
§2.3.1 and §2.7.1 as a **check, not a re-derivation**. The model does not rewrite
the scheduling algorithm; it verifies the structural precondition and the presence
of the algorithm's proof:

- Two logical identities that share an `opcode` must not be concurrent. They share
  one `CalReg[opcode]` entry **and** one alignment semaphore domain, so they cannot
  each align; declaring them concurrent raises `V-OPCODE-CONCURRENT` with "the
  phase split must be redone".
- Every identity must carry a `conflictProof`; a missing one is the warning
  `V-NO-CONFLICT-PROOF`, because the no-conflict guarantee belongs to the NoC
  algorithm and software cannot re-derive it.

Reserved opcodes need no check here: `RouteKey` refuses to carry one, so a table
loaded from JSON with `INVALID` or `EXTENSION` fails closed at construction before
it reaches this check.

The FFN is the live example. Both phases use `opcode 1`, so they are legal only as
**separate phases**; `wse-model check package` passes, while
`wse-model check package --concurrent` declares them concurrent and exits 1 with
`V-OPCODE-CONCURRENT`. That is the check the design's phase splitting exists to
satisfy.

## What is not modelled

- **An IR, group recognition, and collective analysis.** There is no frontend, so
  the model cannot derive a logical identity, a group, or an inter-collective
  concurrency relation from a program.
- **Lowering and emission.** The five artifacts are described; nothing produces
  them. `CalendarRouteTable.to_bytes` emits the table's bytes, but there is no
  code generator, no assembler, and no linker.
- **The five compile-time steps** of Calendar §2.7.3 as a process. The package
  models the *shape* of the outputs (step 4's immediates, step 5's artifacts) and
  the checks a real compiler would run.
- **The compiler's own diagnostics.** `DeploymentPackage.validate` is a model of
  what must hold, not the toolchain's implementation of it.

## Open items that gate a compiler frontend

| Item | What it blocks |
| --- | --- |
| `Q5` | target model dimensions; without them no concrete partition or lowering |
| `Q6` | the MoE load-imbalance policy under `E1`, which decides whether a member may skip a round |
| `C-1` | the send-side operand encoding (scheme A vs scheme B), which changes the lowered instruction sequence |
| `C-3` | the reduction element type field, which must be fixed before the flit header freezes and which `CalendarKeyRef` would have to carry |
| `C-8` | the static table shape for per-row routing (`ReduceScatter` / `Scatter`) |
| `C-9` | the table layout, assumed key-major ([decision 0005](../decisions/0005-static-table-layout.md)) |
| `C-12` | the D-cache strategy and whether `keyCount <= 16` suffices |
| `Q7` / `S-2` | the arena address space, which changes the tile type |
| `Q12` / `C-11` | topology isomorphism, which decides link-time constant vs load-time buffer |

## See also

- [Decision 0002](../decisions/0002-two-layer-model.md) for the core/ACIR split.
- [Descriptors and schemas](../reference/descriptors.md) for the manifest formats.
- [Requirements: Calendar closure](../requirements/calendar-closure.md) for the
  test-backed statements, including the self-checks and the package checks.
- [Roadmap](../roadmap.md) for what a compiler frontend still needs.
