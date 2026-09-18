<!--
Keep pull requests scoped to one change family. Fill in every section; write
"n/a" only with a reason.
-->

## Summary

What semantic rule or capability changed, and why.

## Design source

- Design document and section:
- Decision record (if the model diverges from a design document):
- Open item resolved or discovered (whitepaper Appendix A `Q*`, Calendar §6.3 `S-*`/`C-*`):

## Layer

- [ ] Pure-Python semantic core (`src/wse_model/<domain>/`) — unit test included
- [ ] ACIR model layer (`src/wse_model/acir/`) — also states the pinned pyCircuit revision
- [ ] Docs, tooling, or CI only

## Evidence

Commands run and their result:

```text
make check
...
```

## Width and contract impact

- [ ] No change to integer widths, tensor layouts, or golden vectors
- [ ] Changes a width or a golden vector; a decision record is included

## Checklist

- [ ] `make check` passes locally.
- [ ] New behavior is covered by a test that fails without the change.
- [ ] `docs/design/` was not modified.
- [ ] Documentation and `CHANGELOG.md` are updated.
- [ ] No AI co-author lines were added to commits or this description.
