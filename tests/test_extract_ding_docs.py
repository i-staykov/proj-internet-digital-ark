"""Refreshing the authoritative brief cannot reuse an obsolete package or provenance."""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_ding_docs", ROOT / "scripts/round/extract_ding_docs.py"
)
assert SPEC is not None and SPEC.loader is not None
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


@pytest.mark.parametrize("missing", ["--package", "--archive", "--stamp"])
def test_refresh_requires_explicit_provenance(tmp_path, monkeypatch, missing):
    options = {
        "--package": str(tmp_path),
        "--archive": "task.zip (2026-09-07)",
        "--stamp": "2026-09-08",
        "--out": str(tmp_path / "out"),
    }
    argv = ["extract_ding_docs.py"]
    for flag, value in options.items():
        if flag != missing:
            argv.extend([flag, value])
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        extractor.main()
    assert exc.value.code == 2
    assert not (tmp_path / "out").exists()


def test_brief_selection_refuses_missing_or_ambiguous_versions(tmp_path):
    pattern = "Internet_Digital_Ark_Project_*.docx"
    with pytest.raises(SystemExit, match="no file"):
        extractor._pick(tmp_path, pattern)
    first = tmp_path / "Internet_Digital_Ark_Project_0904_Update.docx"
    first.write_bytes(b"first")
    assert extractor._pick(tmp_path, pattern) == first
    (tmp_path / "Internet_Digital_Ark_Project_0906_Update.docx").write_bytes(b"second")
    with pytest.raises(SystemExit, match="2 files"):
        extractor._pick(tmp_path, pattern)


def _refresh_args(package, out):
    return [
        "extract_ding_docs.py",
        "--package",
        str(package),
        "--out",
        str(out),
        "--archive",
        "task.zip (2026-09-07)",
        "--stamp",
        "2026-09-08",
    ]


def test_refresh_records_each_source_hash_and_supplied_provenance(tmp_path, monkeypatch):
    sources = [
        "Internet_Digital_Ark_Project_0906_Update.docx",
        "Update_Log.docx",
        "Task_Package_File_Guide.txt",
    ]
    for name in sources:
        (tmp_path / name).write_bytes(name.encode())
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", _refresh_args(tmp_path, out))
    monkeypatch.setattr(extractor, "body", lambda src: f"source body: {src.name}\n")
    extractor.main()
    for name, (_, output, _) in zip(sources, extractor.DOCS, strict=True):
        text = (out / output).read_text()
        assert str(tmp_path / name) in text
        assert hashlib.sha256(name.encode()).hexdigest() in text
        assert "task.zip (2026-09-07)" in text
        assert "| transcribed | 2026-09-08 by" in text
        assert text.endswith(f"source body: {name}\n")


def test_failed_conversion_leaves_all_previous_documents_intact(tmp_path, monkeypatch):
    (tmp_path / "Internet_Digital_Ark_Project_0906_Update.docx").write_bytes(b"brief")
    out = tmp_path / "out"
    out.mkdir()
    for _, output, _ in extractor.DOCS:
        (out / output).write_text("previous document\n")
    monkeypatch.setattr(sys, "argv", _refresh_args(tmp_path, out))
    monkeypatch.setattr(extractor, "body", lambda src: "new document\n")
    with pytest.raises(FileNotFoundError):
        extractor.main()
    assert all(
        (out / output).read_text() == "previous document\n" for _, output, _ in extractor.DOCS
    )
