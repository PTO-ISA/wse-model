# Examples

Runnable scenarios built on the model's public API. Each file is a plain Python
script with a `main()` and no hidden state; run them with the interpreter that
has `wse-model` installed.

```bash
python examples/ffn_allgather.py
python examples/validate_route_table.py
python examples/header_cost.py
python examples/check_kernel_object.py
python examples/roofline_two_verdicts.py
python examples/dispatch_and_refill.py
python examples/deployment_package.py
```

| Example | Shows |
| --- | --- |
| `ffn_allgather.py` | The FFN two-phase AllGather closure end to end: compiled table, `CalReg`, per-member `expVal`, and completion |
| `validate_route_table.py` | Running the Calendar §2.7.2 check set over a table loaded from JSON, including a deliberately corrupted one |
| `header_cost.py` | The flit header price at 40 versus 48 nodes, and why open item `Q1` matters |
| `check_kernel_object.py` | The F1/F2/F3 compiled-product prohibitions of Calendar §3.10, each shown passing and failing |
| `roofline_two_verdicts.py` | Why the model reports both a first-order and a tile-accurate roofline verdict, and where they disagree (decision 0006) |
| `dispatch_and_refill.py` | The four Batcher responsibilities, the three load-time chains, the shared-`Batcher.mem` refill split, a load→kickstart→launch sequence, and the scheduling constraints |
| `deployment_package.py` | The five compiler artifacts, the version agreement, the per-call-site immediates, and the same-`opcode` concurrency rule refusing a bad phase split |

`examples/data/ffn-kernel-object.json` is the conforming kernel-object manifest
that `check_kernel_object.py` starts from; it is also used by
`tests/unit/test_compiler_selfcheck.py`.

These scripts are also what `tests/integration/` exercises in-process, so a
break in the public API shows up in both places.
