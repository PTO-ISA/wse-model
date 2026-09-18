"""The F1/F2/F3 compiler product self-checks (Calendar §3.10)."""

from __future__ import annotations

import json

import pytest

from wse_model.compiler import (
    ROUTE_TABLE_SYMBOL,
    ObjectFile,
    Section,
    SectionInfo,
    Symbol,
    SymbolKind,
    check_compiled_product,
    load_object_file,
)
from wse_model.errors import CalendarError
from wse_model.fixtures import clean_kernel_object

pytestmark = pytest.mark.unit

KEY_COUNT = 2
NODE_COUNT = 40
TABLE_BYTES = KEY_COUNT * NODE_COUNT * 16


def _check(obj: ObjectFile):
    return check_compiled_product(obj, key_count=KEY_COUNT, node_count=NODE_COUNT)


def test_the_clean_manifest_passes() -> None:
    report = _check(clean_kernel_object())
    assert report.ok, report.format()


def test_f1_rejects_a_writable_calendar_symbol() -> None:
    """A writable global is shared by every core under SPMD."""
    obj = clean_kernel_object().with_symbols(
        Symbol("CalendarChannel", SymbolKind.WRITABLE_OBJECT, Section.DATA, size=32)
    )
    report = _check(obj)
    assert not report.ok
    assert [d.code for d in report.errors] == ["F1"]
    assert "CalendarChannel" in report.errors[0].message


def test_f1_rejects_a_calendar_symbol_in_bss() -> None:
    obj = clean_kernel_object().with_symbols(
        Symbol("calendar_epochCtr", SymbolKind.BSS_OBJECT, Section.BSS, size=8)
    )
    assert "F1" in {d.code for d in _check(obj).errors}


def test_f1_allows_calendar_state_in_text() -> None:
    obj = clean_kernel_object().with_symbols(
        Symbol("calendar_epoch_inc", SymbolKind.FUNCTION, Section.TEXT, size=16)
    )
    assert _check(obj).ok


def test_f2_rejects_a_materialized_key_ref() -> None:
    obj = clean_kernel_object().with_symbols(
        Symbol(
            "kRowAllGather",
            SymbolKind.READ_ONLY_OBJECT,
            Section.RODATA,
            size=16,
            addr_align=16,
        )
    )
    report = _check(obj)
    assert not report.ok
    assert "F2" in {d.code for d in report.errors}
    assert any("kRowAllGather" in d.message for d in report.errors)


def test_f3_requires_a_route_table_symbol() -> None:
    obj = ObjectFile(
        symbols=(Symbol("ffn_fused", SymbolKind.FUNCTION, Section.TEXT),),
        sections=(SectionInfo(Section.RODATA, addr_align=64),),
    )
    assert "F3" in {d.code for d in _check(obj).errors}


def test_f3_requires_64_byte_rodata_alignment() -> None:
    obj = clean_kernel_object(
        sections=(
            SectionInfo(Section.TEXT, addr_align=4),
            SectionInfo(Section.RODATA, addr_align=16, size=TABLE_BYTES),
        )
    )
    report = _check(obj)
    assert "F3" in {d.code for d in report.errors}
    assert any("AddrAlign=16" in d.message for d in report.errors)


def test_f3_requires_the_exact_table_size() -> None:
    obj = clean_kernel_object().replacing(
        Symbol(
            ROUTE_TABLE_SYMBOL,
            SymbolKind.READ_ONLY_OBJECT,
            Section.RODATA,
            size=TABLE_BYTES // 2,
            addr_align=64,
        )
    )
    report = _check(obj)
    assert any("1280" in d.message for d in report.errors)


def test_f3_rejects_a_writable_route_table() -> None:
    obj = ObjectFile(
        symbols=(
            Symbol(
                ROUTE_TABLE_SYMBOL,
                SymbolKind.WRITABLE_OBJECT,
                Section.DATA,
                size=TABLE_BYTES,
                addr_align=64,
            ),
        ),
        sections=(
            SectionInfo(Section.RODATA, addr_align=64),
            SectionInfo(Section.DATA, addr_align=64),
        ),
    )
    report = _check(obj)
    codes = {d.code for d in report.errors}
    assert "F1" in codes
    assert "F3" in codes


def test_manifest_round_trips_through_json() -> None:
    obj = clean_kernel_object()
    payload = {"schema": "wse-model/kernel-object/1", **obj.describe()}
    reloaded = load_object_file(payload)
    assert reloaded.symbols == obj.symbols
    assert reloaded.sections == obj.sections
    assert _check(reloaded).ok


def test_manifest_accepts_a_json_string() -> None:
    payload = {
        "schema": "wse-model/kernel-object/1",
        "sections": [{"name": ".rodata", "addr_align": 64, "size": TABLE_BYTES}],
        "symbols": [
            {
                "name": ROUTE_TABLE_SYMBOL,
                "kind": "read-only object",
                "section": ".rodata",
                "size": TABLE_BYTES,
                "addr_align": 64,
            }
        ],
    }
    reloaded = load_object_file(json.dumps(payload))
    assert _check(reloaded).ok


def test_manifest_rejects_an_unknown_schema() -> None:
    with pytest.raises(CalendarError):
        load_object_file({"schema": "wse-model/kernel-object/2", "symbols": []})


def test_negative_sizes_are_rejected() -> None:
    with pytest.raises(CalendarError):
        Symbol("x", SymbolKind.OTHER, Section.OTHER, size=-1)
    with pytest.raises(CalendarError):
        SectionInfo(Section.RODATA, addr_align=0)
