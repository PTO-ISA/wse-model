# Examples

Runnable scenarios built on the model's public API. Each file is a plain Python
script with a `main()` and no hidden state; run them with the interpreter that
has `wse-model` installed.

```bash
python examples/ffn_allgather.py
python examples/validate_route_table.py
python examples/header_cost.py
```

| Example | Shows |
| --- | --- |
| `ffn_allgather.py` | The FFN two-phase AllGather closure end to end: compiled table, `CalReg`, per-member `expVal`, and completion |
| `validate_route_table.py` | Running the Calendar §2.7.2 check set over a table loaded from JSON, including a deliberately corrupted one |
| `header_cost.py` | The flit header price at 40 versus 48 nodes, and why open item `Q1` matters |

These scripts are also what `tests/integration/` exercises in-process, so a
break in the public API shows up in both places.
