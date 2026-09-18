"""The ``agentic_circuit`` (ACPy 0.5 / ACIR) expression of the WSE Calendar model.

The pure-Python semantic core under :mod:`wse_model.calendar`,
:mod:`wse_model.noc`, and :mod:`wse_model.topology` is the authority. This package
expresses the *same* rules as an ``agentic_circuit`` queue graph so the model can
be lowered to ACIR, and it never invents behaviour the core does not have.

The single build entry lives at :mod:`wse_model.acir.model.top`:

.. code-block:: python

    from wse_model.acir.model.top import acir_top, node_lowering_spec

It is deliberately **not** re-exported here. ``ac.jit(..., workspace=...)``
captures the entry file together with its package initializers, and this frontend
rejects a local import inside a captured package initializer::

    ACPY-JIT-006: external import 'wse_model.acir.model.top' is not allowed in
    acir/__init__.py

Importing the entry module by its full dotted path instead keeps the source
closure importable, and it keeps every payload name unambiguous across files.
"""

from __future__ import annotations

__all__: list[str] = []
