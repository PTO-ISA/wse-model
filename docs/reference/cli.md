# CLI reference

The `wse-model` command is a thin, deterministic front end over the semantic core.
Every command can emit JSON so results can be diffed, gated, or consumed by
another tool. This page documents every command, every flag, what it prints, and
its exit code.

## Invocation

```console
$ wse-model --version
wse-model 0.1.0
```

`python -m wse_model` runs the same entry point. The global options are:

| Option | Effect |
| --- | --- |
| `-h`, `--help` | print help for the current command and exit 0 |
| `--version` | print `wse-model <version>` and exit 0 |
| `--json` | emit machine-readable JSON |

`--json` is accepted both before and after the subcommand (the parser defines it
at both levels). It changes the output form only for the two commands that have a
human-readable form (`calendar validate` and `check object`); the others print
JSON unconditionally.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `1` | a validation report failed: `calendar validate` found errors, or `check object` failed a self-check |
| `2` | a usage error (argparse) or a model error (`WseModelError`), printed to stderr as `error: <message>` |

## Command tree

```text
wse-model
├── topology show [--profile NAME] [--links]
├── calendar
│   ├── encode [--key NAME] [--profile NAME] [--source N] [--self-delivery]
│   ├── validate [--table PATH]
│   └── emit [--layout key-major|node-major] [--out PATH]
├── run ffn-allgather [--phase b|c|both] [--layout key-major|node-major]
├── report roofline
├── report bandwidth
├── report overhead
├── report aicore
├── report dcache
├── report matmul [--m N --k N --n N] [--precision fp16|fp8|fp4] [--fetched-weight-bytes N]
├── report host
├── report runtime
├── check
│   ├── object [--object PATH | --example] [--key-count N] [--node-count N]
│   └── package [--concurrent]
└── open-items [--status all|open|assumed|resolved]
```

## `topology show`

Describes one NoC topology profile. Always prints JSON.

| Flag | Default | Effect |
| --- | --- | --- |
| `--profile` | `calendar-40` | one of `calendar-40`, `whitepaper-48`, `whitepaper-48-40c` |
| `--links` | off | append the list of physical links as `[low, high]` pairs |

```console
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

`whitepaper-48` reports 48 AICOREs and 12 B route bits; `whitepaper-48-40c`
reports 48 nodes with 40 AICOREs and 8 I/O nodes. A 5×8 mesh has 5×7 + 4×8 = 67
links.

## `calendar encode`

Encodes one logical identity's route bitmap. Always prints JSON.

| Flag | Default | Effect |
| --- | --- | --- |
| `--key` | `golden` | `golden`, `row-allgather` (FFN `keyId 0`), or `col-allgather` (FFN `keyId 1`) |
| `--profile` | `calendar-40` | topology profile; the FFN keys and the golden vector are defined on the 40-node baseline |
| `--source` | `0` | source node id (ignored by `golden`, which is fixed at N00) |
| `--self-delivery` | off | set `L_self` (the fabric lands the source's own copy) |

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

```console
$ wse-model calendar encode --key row-allgather --source 0
{
  "key": "row-allgather",
  "description": "FFN keyId 0: AllGather over the ROW group of the source (Calendar §2.2.1)",
  "source": 0,
  "group": [0, 1, 2, 3, 4, 5, 6, 7],
  "self_delivery": false,
  "node_count": 40, "width_bits": 80, "width_bytes": 10,
  "hex": "FE FF 00 00 00 00 00 00 00 00",
  "pass_nodes": [0, 1, 2, 3, 4, 5, 6, 7],
  "land_nodes": [1, 2, 3, 4, 5, 6, 7],
  "land_count": 7, "illegal_nodes": []
}
```

Errors exit 2. A source that is not an FFN cell:

```console
$ wse-model calendar encode --key row-allgather --source 39
error: node 39 is not an FFN cell, so it has no row-allgather group (Calendar §2.2.1)
$ echo $?
2
```

The golden vector is defined only on the 40-node baseline:

```console
$ wse-model calendar encode --key golden --profile whitepaper-48
error: the golden vector is defined for the 40-node Calendar baseline (Calendar §2.2.1)
```

## `calendar validate`

Runs the §2.7.2 check set over the built-in FFN example or a table loaded from
JSON. Prints a text report by default and the full JSON report with `--json`.

| Flag | Default | Effect |
| --- | --- | --- |
| `--table` | built-in FFN example | path to a `wse-model/calendar-route-table/1` JSON file |

```console
$ wse-model calendar validate
route table: built-in FFN example
OK (6 checks)
```

A failing table lists one diagnostic per error and exits 1:

```console
$ wse-model calendar validate --table /tmp/bad.calendar.json
route table: /tmp/bad.calendar.json
[error] V-CONSERVE keyId=0 node=0: destination 0: the land set delivers 10752 B (landCount=7 x rowCount=8 x rowBytes=192) but the entry declares expectedRxBytes=1; this value is the device-side expVal and the two must be equal (Calendar §2.7.2)
FAILED: 1 error(s), 0 warning(s)
$ echo $?
1
```

The JSON form reports `checks_run`, `errors`, and `warnings`:

```json
{
  "ok": true,
  "checks_run": [
    "entry-fits-gpr-pair",
    "per-source-structural-checks",
    "send-receive-conservation",
    "arm-reachability",
    "noc-timing-proof-present",
    "table-budget"
  ],
  "errors": [],
  "warnings": []
}
```

## `calendar emit`

Emits the compiled FFN table as an aligned `.rodata` segment. Always prints JSON;
`--out` also writes the raw bytes.

| Flag | Default | Effect |
| --- | --- | --- |
| `--layout` | `key-major` | `key-major` or `node-major` (`C-9`) |
| `--out` | — | write the raw segment to this path |

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

`hex` is the full segment, 16 B per line, uppercase and space separated. The
key-major form reports `"layout": "key-major"` and `"d_cache_bytes_per_core": 128`.
With `--out build/ffn.rodata` the payload also contains
`"written_to": "build/ffn.rodata"`.

## `run ffn-allgather`

Runs the FFN two-phase AllGather closure end to end. Always prints JSON.

| Flag | Default | Effect |
| --- | --- | --- |
| `--phase` | `both` | `b`, `c`, or `both` |
| `--layout` | `key-major` | table layout to run |

```console
$ wse-model run ffn-allgather
{
  "scenario": "ffn-allgather",
  "table": { "topology": "mesh-5x8", "layout": "key-major", "key_count": 2, "table_bytes": 1280, "d_cache_bytes_per_core": 128, "versions": { "topologyVersion": 1, "calendarVersion": 1, "routeVersion": 1 } },
  "phases": [
    { "phase": "phase_b_row_allgather", "key_id": 0, "opcode": 1, "epoch": 1, "member_count": 32, "ok": true, "max_tree_depth": 7, "peak_link_load": 8 },
    { "phase": "phase_c_col_allgather", "key_id": 1, "opcode": 1, "epoch": 2, "member_count": 32, "ok": true, "max_tree_depth": 3, "peak_link_load": 4 }
  ],
  "all_complete": true
}
```

Each phase object also carries `members`, `arm_lead_cycles`, `total_wire_bytes`,
`total_header_bytes`, `total_payload_bytes`, `useful_payload_fraction`, and the
per-member `states`. The two phases share `opcode 1`, so the core counters yield
epoch 1 then epoch 2. `--phase c` produces one phase.

## `report roofline`

The whitepaper §19.2 balance table. Always prints JSON.

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
```

## `report bandwidth`

The four published link bandwidths, the local-DRAM/NoC ratio, and the FFN
two-phase payload volume. Always prints JSON.

```console
$ wse-model report bandwidth
{
  "links": {
    "local_dram": { "name": "local_dram", "bytes_per_sec": 1000000000000.0, "GB_per_s": 1000.0, "source": "whitepaper §1.2 / §4.4" },
    "noc_link":   { "name": "noc_link",   "bytes_per_sec": 128000000000.0,  "GB_per_s": 128.0,  "source": "whitepaper §4.4: 64 B x 2 GHz" },
    "ub_fabric":  { "name": "ub_fabric",  "bytes_per_sec": 224000000000.0,  "GB_per_s": 224.0,  "source": "whitepaper §6.3: 8 x 224 Gbps = 224 GB/s" },
    "ub_host":    { "name": "ub_host",    "bytes_per_sec": 14000000000.0,   "GB_per_s": 14.0,   "source": "whitepaper §6.3: 1 x 112 Gbps = 14 GB/s" }
  },
  "local_dram_vs_noc_link_ratio": 7.8125,
  "ffn_two_phase": {
    "node_count": 40, "header_bytes": 12, "header_overhead_percent": 18.75,
    "payload_bytes_per_destination": { "phase_b": 10752, "phase_c": 36864 },
    "total_payload_bytes_per_core": 47616,
    "noc_clock_hz": 2000000000.0, "noc_link_width_bytes": 64, "local_dram_vs_noc_ratio": 7.812
  }
}
```

## `report overhead`

The per-flit header cost for every topology profile. Always prints JSON.

```console
$ wse-model report overhead
{
  "profiles": [
    { "profile": "calendar-40", "topology": { "node_count": 40, "route_bits_bits": 80, "route_bits_bytes": 10 },
      "header": { "header_bytes": 12, "payload_bytes_per_flit": 52, "overhead_percent": 18.75 } },
    { "profile": "whitepaper-48", "topology": { "node_count": 48, "route_bits_bits": 96, "route_bits_bytes": 12 },
      "header": { "header_bytes": 14, "payload_bytes_per_flit": 50, "overhead_percent": 21.88 } },
    { "profile": "whitepaper-48-40c", "topology": { "node_count": 48, "route_bits_bits": 96, "route_bits_bytes": 12 },
      "header": { "header_bytes": 14, "payload_bytes_per_flit": 50, "overhead_percent": 21.88 } }
  ]
}
```

## `report aicore`

The `AicoreSpec`: clocks, local DRAM, on-chip buffers, and the two derived
per-cycle figures. Always prints JSON.

```console
$ wse-model report aicore
{
  "clock_hz": 1400000000.0,
  "local_dram_bytes": 402653184,
  "local_dram_bytes_per_cycle": 714.29,
  "vector_bytes_per_cycle": 256,
  "fixpipe_bytes_per_cycle": 256,
  "on_chip_buffers": { "L0A": 131072, "L0B": 524288, "L0C": 262144, "L1": 1048576, "UB": 393216 },
  "cube_weights_per_cycle_fp16": 256,
  "vector_elements_per_second_fp16": 179200000000.0
}
```

## `report dcache`

The route table's D-cache residency and cold-miss account, for each layout and for
`keyCount` 2, 8, and 16. Always prints JSON; `entries` has one object per
combination.

```console
$ wse-model report dcache
{
  "entries": [
    {
      "key_count": 2, "node_count": 40, "layout": "key-major",
      "d_cache": { "capacity_bytes": 16384, "line_bytes": 64, "lines": 256, "entries_per_line": 4 },
      "lines_per_key": 10, "lines_per_core": 2, "bytes_per_core": 128,
      "residency_percent": 0.7812, "lines_die_wide": 20,
      "refill_requests": 80, "batcher_served_refills": 60, "ddr_backed_refills": 20,
      "amplification": 4.0, "within_budget": true,
      "cold_miss_account": "one refill per distinct line per operator, because the framework's tail DataCacheCleanAndInvalid invalidates the Calendar lines too (Calendar §3.8.4)"
    },
    …
  ]
}
```

At `keyCount = 16` the node-major rows report `lines_per_core` 4 against
key-major's 16.

## `report matmul`

The tile-accurate Cube and memory timing for one matmul shape. Always prints JSON.
It reports **two** verdicts; see
[decision 0006](../decisions/0006-two-roofline-verdicts.md).

| Flag | Default | Effect |
| --- | --- | --- |
| `--m` | `1` | M dimension (batch) |
| `--k` | `4096` | K dimension (reduction) |
| `--n` | `4096` | N dimension (output) |
| `--precision` | `fp16` | `fp16`, `fp8`, or `fp4` |
| `--fetched-weight-bytes` | ideal | actual fetched bytes when the layout is padded |

```console
$ wse-model report matmul --m 1 --k 4096 --n 4096 --precision fp16
{
  "shape": "[1, 4096] x [4096, 4096]",
  "macs": 16777216, "flops": 33554432, "gemv": true,
  "precision": "fp16", "cube_shape_per_cycle": "16x16x16", "cpp_macs_per_cycle": 4096,
  "cube_cycles": 65536, "m_steps": 1, "n_steps": 256, "k_steps": 256,
  "m_utilization": 0.0625, "effective_macs_per_cycle": 256.0,
  "compute_seconds": 4.681142857142857e-05,
  "ideal_weight_bytes": 33554432, "fetched_weight_bytes": 33554432,
  "fetch_seconds": 3.3554432e-05,
  "arithmetic_intensity_flops_per_fetched_byte": 1.0,
  "first_order_intensity_flops_per_weight_element": 2.0,
  "balance_flops_per_byte": 11.4688,
  "bound_by": "compute", "first_order_bound_by": "memory", "verdicts_agree": false,
  "roofline_seconds": 4.681142857142857e-05,
  "cycles_per_weight_byte": 0.002
}
```

For the same shape at `--precision fp8`, `bound_by` and `first_order_bound_by` are
both `memory` and `verdicts_agree` is true; FP4 behaves the same.

## `report host`

The UB bus, the four Batcher dispatch paths, the undeclared `Q3` spec, and the FFN
data-cache refill account. Always prints JSON.

```console
$ wse-model report host
{
  "ub_bus": { "fabric_lanes": 8, "host_lanes": 1, "total_lanes": 9, "fabric_GB_per_s": 224.0, "host_GB_per_s": 14.0 },
  "local_dram_over_fabric_ratio": 4.4643,
  "dispatch_paths": [ … four entries, one per Batcher responsibility … ],
  "batcher_mem": {
    "spec": { "declared": false, "open_item": "Q3", "mem_capacity_bytes": null, "mem_bandwidth_bytes_per_sec": null, "cores_per_batcher": null, "parallel_channels": null },
    "instruction_block_bytes": 2048, "data_line_bytes": 64,
    "path": "DDR -> Batcher.mem -> I$/D$; never through local DRAM and never through L1 (whitepaper §4.1, §13)"
  },
  "ffn_data_cache_refill": {
    "distinct_lines": 20, "requesters_per_line": 4, "line_bytes": 64,
    "requests": 80, "mem_served_requests": 60, "ddr_backed_requests": 20,
    "mem_served_bytes": 3840, "ddr_bytes": 1280
  }
}
```

## `report runtime`

The three frequency tiers, the four dispatch chains, both `blockId` paths, and the
steady-state dispatch note. Always prints JSON.

```console
$ wse-model report runtime
{
  "tiers": ["load time (once per model load)", "per launch (once per operator)", "run time (the runtime does not intervene)"],
  "chains": {
    "kernel binary (.text + .rodata)": { "tier": "load time (once per model load)", "via_batcher": true, "destination": "DDR code/data segments, refilled into I$/D$ on a miss", "through_local_dram": false, "through_l1": false, "note": "indistinguishable from an ordinary dispatch; no special handling" },
    "model weights": { "tier": "load time (once per model load)", "via_batcher": true, "destination": "each core's local DRAM", "through_local_dram": true, "through_l1": false, "note": "2 KB page aligned; written once and then read every inference" },
    "CalReg timeslot image": { "tier": "load time (once per model load)", "via_batcher": false, "destination": "NoC node timeslot registers", "through_local_dram": false, "through_l1": false, "note": "…the only dispatch that does not go through the Batcher…" },
    "input activations": { "tier": "per launch (once per operator)", "via_batcher": true, "destination": "each core's UB / L1", "through_local_dram": false, "through_l1": false, "note": "the only recurring dispatch once the model is loaded" }
  },
  "block_id_paths": {
    "spr": { "source": "block_idx SPR", "loads": 0, "value_class": "A", "note": "…" },
    "argument": { "source": "kernel argument", "loads": 1, "value_class": "B", "note": "…" }
  },
  "steady_state_dispatch": "activations plus a descriptor; no Calendar data, no per-core expansion, no run-time descriptors (whitepaper §12.2)"
}
```

## `check object`

Runs the F1/F2/F3 compiled-product self-checks over a declared kernel-object
manifest. Prints a text report by default and the full JSON report with `--json`.

| Flag | Default | Effect |
| --- | --- | --- |
| `--object` | — | path to a `wse-model/kernel-object/1` manifest |
| `--example` | off | check the built-in clean manifest instead of a file |
| `--key-count` | `2` | `keyCount` the product is expected to contain |
| `--node-count` | `40` | `nodeCount` the product is expected to contain |

Exactly one of `--object` and `--example` is required.

```console
$ wse-model check object --example
OK (5 checks)

$ wse-model check object --object examples/data/ffn-kernel-object.json
OK (5 checks)

$ wse-model check object
error: provide --object PATH with a kernel object manifest, or --example to check the built-in clean baseline
$ echo $?
2
```

A failed check exits 1 and lists the errors:

```console
$ wse-model check object --object /tmp/wse_cli/bad-object.json
[error] F1: CalendarChannel is a writable Calendar symbol in .data (writable object); under SPMD every core shares one global, so this is a data race that makes epochs and route bits non-deterministic (Calendar §3.10). CalendarChannel and epochCtr must be kernel-local.
FAILED: 1 error(s), 0 warning(s)
$ echo $?
1
```

With `--json` the payload has `object`, `expected`, `ok`, `checks_run`, `errors`,
and `warnings`. For a clean manifest `checks_run` is
`["F1-no-calendar-static-state", "F1-clean", "F2-no-materialized-key-ref", "F2-clean", "F3-route-table-emission"]`.

## `check package`

Assembles the FFN deployment package (route table + `CalReg` mirror + kernel
object + weight shards + conflict proofs) and validates it as a whole. Prints a
text report by default and the full JSON report with `--json`.

| Flag | Default | Effect |
| --- | --- | --- |
| `--concurrent` | off | declare the two logical identities concurrent, which the same-`opcode` rule must refuse |

```console
$ wse-model check package
OK (26 checks)
```

`--concurrent` makes the same-`opcode` violation visible and exits 1:

```console
$ wse-model check package --concurrent
[error] V-OPCODE-CONCURRENT: logical identities [0, 1] share opcode 1 and may be in flight together. One opcode domain has a single hardware time origin and a single CalReg entry, so the two cannot each align; the phase split must be redone (Calendar §2.3.1, §2.7.1)
FAILED: 1 error(s), 0 warning(s)
$ echo $?
1
```

The JSON payload is the package description plus the report. A clean run reports
`ok: true`, `versions: { "topologyVersion": 1, "calendarVersion": 1, "routeVersion": 1 }`,
`rodata_bytes: 1280`, the five `artifacts`, one `call_site_immediates` entry per
key, and 26 distinct `checks_run`:

```text
entry-fits-gpr-pair, per-source-structural-checks, bit-pairs-legal, source-on-path,
induced-subgraph-is-tree, land-set-complete, self-land-consistent,
send-receive-conservation, arm-reachability, noc-timing-proof-present,
key-count-budget, table-alignment, d-cache-residency, table-budget,
f1-f2-f3-product-checks, F1-no-calendar-static-state, F1-clean,
F2-no-materialized-key-ref, F2-clean, F3-route-table-emission,
artifact-version-agreement, same-opcode-not-concurrent, shared-opcode-domain,
conflict-proof-present, weight-shard-pages, rodata-alignment
```

With `--concurrent` and `--json`, `concurrency_declared` is `[[0, 1]]` and the
`errors` array holds one `V-OPCODE-CONCURRENT` diagnostic.

## `open-items`

Lists the registry of values the design sources leave open. Always prints JSON.

| Flag | Default | Effect |
| --- | --- | --- |
| `--status` | `all` | `all`, `open`, `assumed`, or `resolved` |

```console
$ wse-model open-items --status assumed
{
  "total": 31,
  "returned": 5,
  "by_resolution": { "open": 26, "assumed": 5, "resolved": 0 },
  "items": [
    {
      "id": "C-2",
      "title": "Flit header carriage: per-flit copy (baseline) vs per-packet header with per-packet context in the NoC",
      "source": "calendar-6.3",
      "owner": "noc",
      "resolution": "assumed",
      "note": "The model implements the per-flit baseline, which is what the 12 B / 19% overhead figure describes.",
      "decision": "0001"
    },
    …
  ]
}
```

The registry is the source of truth for
[Open items](open-items.md); `total`, `returned`, and `by_resolution` change only
when `wse_model/open_items.py` changes.

## See also

- [Getting started](../development/getting-started.md) for the setup and a guided
  walkthrough.
- [Descriptors and schemas](descriptors.md) for the JSON produced and consumed by
  these commands.
- [Open items](open-items.md) for the rendered registry.
