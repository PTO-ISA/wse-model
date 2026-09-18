# Descriptors and schemas

The model's machine-readable artifacts are versioned by a `schema` string. There
are two:

| Schema | Produced by | JSON Schema | Contract test |
| --- | --- | --- | --- |
| `wse-model/calendar-route-table/1` | `CalendarRouteTable.to_dict` (`wse-model calendar validate --json`, and the compiler boundary) | `schemas/calendar-route-table.schema.json` | `tests/contracts/test_table_schema.py` |
| `wse-model/kernel-object/1` | a conforming toolchain's declared symbol manifest (`wse-model check object`) | `schemas/kernel-object.schema.json` | `tests/unit/test_compiler_selfcheck.py` |
| `wse-model/deployment-package/1` | `DeploymentPackage.to_dict` | not yet a separate file | `tests/unit/test_compiler_package.py::test_package_description_is_json_serializable` |

A consumer must reject any other schema name. Both schemas are JSON Schema
draft 2020-12, and both set `additionalProperties: true` at the top level so a
producer can add fields without breaking a consumer.

## `wse-model/calendar-route-table/1`

The compiled `kCalendarRoute[keyId][node]` table plus its metadata, as emitted by
[`CalendarRouteTable.to_dict`](../../src/wse_model/calendar/table.py). One entry
per `(key, source node)`, with all nodes emitted and no per-core pruning.

### Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string, const `"wse-model/calendar-route-table/1"` | the schema identity; consumers must reject any other value |
| `topology` | object | the mesh the table was compiled for (below) |
| `layout` | enum `"key-major"` \| `"node-major"` | the static table layout; `key-major` is the design baseline, `node-major` is the `C-9` variant |
| `versions` | object | the three version numbers checked together at load time |
| `key_count` | integer, 0–16 | the number of logical identities; Calendar §2.6 caps this at 16 |
| `table_bytes` | integer | `key_count × node_count × 16` |
| `d_cache_lines_per_core` | integer | lines a core residents with this layout: `key_count` key-major, `ceil(key_count / 4)` node-major |
| `keys` | array of key objects | the compiled identities |

`topology` has `name` (string), `rows` and `cols` (positive integers),
`node_count` (`rows × cols`; 40 for the baseline, 48 for the whitepaper reading),
`route_bits_bits` (`2 × node_count`) and `route_bits_bytes`
(`ceil(2 × node_count / 8)`: 10 at 40, 12 at 48).

`versions` has `topologyVersion`, `calendarVersion`, and `routeVersion`, all
non-negative integers. The three together are the system-level substitute for the
removed atomic route/timeslot selection instruction; any mismatch must fault
rather than degrade (whitepaper §10.3, `HW-13`).

### Key object

| Field | Type | Meaning |
| --- | --- | --- |
| `key_id` | integer, 0–15 | the table's key-dimension index; a compile-time immediate |
| `route_key` | object | the logical identity (below) |
| `node_count` | integer | one row per source node |
| `member_nodes` | integer array | cores that participate; non-members carry an all-zero row |
| `groups` | object, node id → integer array | the per-source resolved destination set; a single set is not enough under SPMD because each source's group differs |
| `self_delivery` | boolean | `FabricSelfDelivery`; must agree with the source's own `L` bit |
| `arm_lead_cycles` | integer or null | the NoC/BSP window after alignment for the receive command and every send descriptor to be enqueued |
| `conflict_proof` | string or null | the NoC algorithm's proof that the same-`opcode` no-conflict and no-concurrency guarantees hold; the model records it and never re-derives it |
| `geometry` | object or null | the payload geometry (below), or `null` when none was recorded |
| `land_counts` | object, node id → integer | per destination, the number of sources that land on it; **emitted but not required by the schema** |
| `entries` | array of entry objects | one 16 B entry per node, in node order |

`route_key` is the logical identity:
`program_id`, `kernel_id`, and `phase_id` (non-empty strings), `collective`
(one of `ALL_GATHER`, `REDUCE`, `ALL_REDUCE`, `REDUCE_SCATTER`, `SCATTER`,
`GATHER`), `opcode` (integer, 1–6; it equals the collective's opcode), and
`group_role` (a role string such as `ROW(my_row)`, not a concrete group).

When present, `geometry` carries `rowCount`, `rowBytes`, `sendRowStride`,
`recvRowCount`, `recvRowStride`, `srcGap`, `dstGap`, `nBurst`, `capacity`,
`r1_aligned` (boolean; `R-1`, the 32 B multiple rule) and `flit_aligned_rows`
(boolean; `R-2`, efficiency only).

### Entry object

| Field | Type | Meaning |
| --- | --- | --- |
| `node` | integer | the source node this row belongs to |
| `route_bits` | string | space-separated uppercase hex, LSB-first, 2 bits per node with `bit(2i+1)=P_i`, `bit(2i)=L_i` |
| `land_count` | integer | `popcount(L)`, carried for cross-checking |
| `flags` | integer, 0–255 | bit0 `isMember`, bit1 `isRoot`, bit2 `selfLand` |
| `expected_rx_bytes` | integer, 0–4294967295 | the device-side `expVal`: the sum over sources whose `L` bit lands here of `rowCount × rowBytes` |

### A real excerpt

From `wse_model.fixtures.ffn_example().table.to_dict()`, trimmed (the real object
has 40 member nodes, a 40-entry group per member, and 40 entries per key):

```json
{
  "schema": "wse-model/calendar-route-table/1",
  "topology": { "name": "mesh-5x8", "rows": 5, "cols": 8, "node_count": 40, "route_bits_bits": 80, "route_bits_bytes": 10 },
  "layout": "key-major",
  "versions": { "topologyVersion": 1, "calendarVersion": 1, "routeVersion": 1 },
  "key_count": 2,
  "table_bytes": 1280,
  "d_cache_lines_per_core": 2,
  "keys": [
    {
      "key_id": 0,
      "route_key": { "program_id": "ffn", "kernel_id": "ffn_fused", "phase_id": "phase_b_row_allgather", "collective": "ALL_GATHER", "opcode": 1, "group_role": "ROW(my_row)" },
      "node_count": 40,
      "member_nodes": [0, 1, 2, 3, "…"],
      "groups": { "0": [0, 1, 2, 3, 4, 5, 6, 7] },
      "self_delivery": false,
      "arm_lead_cycles": 64,
      "conflict_proof": "fixture:no-conflict-key0",
      "geometry": { "rowCount": 8, "rowBytes": 192, "sendRowStride": 192, "recvRowCount": 8, "recvRowStride": 1536, "srcGap": 0, "dstGap": 1344, "nBurst": 8, "capacity": 12288, "r1_aligned": true, "flit_aligned_rows": true },
      "land_counts": { "0": 7, "1": 7, "2": 7, "3": 7 },
      "entries": [
        { "node": 0, "route_bits": "FE FF 00 00 00 00 00 00 00 00", "land_count": 7, "flags": 3, "expected_rx_bytes": 10752 },
        "… 39 more"
      ]
    }
  ]
}
```

The `["…"]` and `"… more"` markers above stand for elided array contents in this
documentation; the real emission contains every element.

### What enforces it

[`tests/contracts/test_table_schema.py`](../../tests/contracts/test_table_schema.py)
is the enforcing test. It freezes the schema name and the required fields, proves
byte-for-byte round-tripping through `CalendarRouteTable.from_dict`, proves JSON
determinism, proves both layouts contain the same entries, and validates the
emitted object against `schemas/calendar-route-table.schema.json` with
`jsonschema`. A change to any of those is a contract change.

## `wse-model/kernel-object/1`

The declared symbol and section view of a compiled kernel object, consumed by the
F1/F2/F3 self-checks. The model does not parse ELF; it checks this manifest, which
is what `llvm-nm` and `llvm-readelf` would report. Making it explicit means the
invariant is testable without a compiler, and a compiler that cannot produce the
manifest fails the check rather than passing by omission.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string, const `"wse-model/kernel-object/1"` | the schema identity |
| `sections` | array | each with `name` (`.text`, `.rodata`, `.data`, `.bss`, or `other`), `addr_align` (≥ 1), and optional `size` |
| `symbols` | array | each with `name`, `kind`, `section`, and optional `size`, `addr_align`, `is_global` |

A symbol's `kind` is spelled the way `llvm-nm` reports it: `function` (T/t),
`read-only object` (R/r), `writable object` (D/d), `bss object` (B/b), or `other`.
A name counts as Calendar-owned if it contains `calendar` (case-insensitively) or
starts with `kCal`.

```json
{
  "schema": "wse-model/kernel-object/1",
  "sections": [
    { "name": ".text", "addr_align": 4, "size": 512 },
    { "name": ".rodata", "addr_align": 64, "size": 1280 }
  ],
  "symbols": [
    { "name": "ffn_fused", "kind": "function", "section": ".text", "size": 512, "is_global": true },
    { "name": "kCalendarRoute", "kind": "read-only object", "section": ".rodata", "size": 1280, "addr_align": 64, "is_global": false }
  ]
}
```

This is the full content of
[`examples/data/ffn-kernel-object.json`](../../examples/data/ffn-kernel-object.json),
the conforming FFN manifest. `wse-model check object --object` loads it,
`--example` loads the built-in equivalent from `fixtures.clean_kernel_object`, and
both must pass F1, F2, and F3.

`tests/unit/test_compiler_selfcheck.py::test_the_example_manifest_validates_against_the_published_schema`
enforces the schema, and `test_the_example_manifest_satisfies_f1_f2_f3` enforces
the checks.

## `wse-model/deployment-package/1`

`DeploymentPackage.to_dict()` emits the assembled compiler package. It is not yet
accompanied by a standalone JSON Schema file; the enforcing test is
`tests/unit/test_compiler_package.py::test_package_description_is_json_serializable`.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string, const `"wse-model/deployment-package/1"` | the schema identity |
| `table` | object | the `CalendarRouteTable.describe()` summary |
| `calreg` | object | the `CalRegImage.describe()` summary |
| `versions` | object | the package's `topologyVersion` / `calendarVersion` / `routeVersion` |
| `rodata_bytes` | integer | the padded `.rodata` segment length, a 64 B multiple |
| `key_count`, `node_count` | integer | the table dimensions |
| `weight_shards` | integer array | per-core weight shard byte sizes |
| `conflict_proofs` | object, `keyId` → string | the NoC algorithm's proof per opcode domain |
| `artifacts` | array | the five whitepaper §13.3 artifacts, each `{artifact, form, destination}` |
| `call_site_immediates` | array | one `{keyId, opcode, redOp, routeVersion, expVal, capacity, selfOffStride, nBurst}` per identity |
| `kernel_object` | object or null | the declared kernel object, when one was supplied |

The `CAL-11x` requirements cover the package's rules; see
[Calendar closure requirements](../requirements/calendar-closure.md).

## See also

- [Calendar and NoC](../architecture/calendar-noc.md) for what the entries mean.
- [CLI reference](cli.md) for the commands that print and consume these objects.
- [Testing and gates](../development/testing-and-gates.md) for the contract lane.
