import os
import context_root


def test_studio_root_wins(monkeypatch):
    monkeypatch.setenv("STUDIO_CONTEXT_ROOT", "/tmp/ctx")
    monkeypatch.delenv("CABINET_CONTEXT_ROOT", raising=False)
    assert context_root.cabinet_root() == os.path.abspath("/tmp/ctx")


def test_legacy_cabinet_fallback(monkeypatch):
    monkeypatch.delenv("STUDIO_CONTEXT_ROOT", raising=False)
    monkeypatch.setenv("CABINET_CONTEXT_ROOT", "/tmp/legacy")
    assert context_root.cabinet_root() == os.path.abspath("/tmp/legacy")


def test_studio_beats_legacy(monkeypatch):
    monkeypatch.setenv("STUDIO_CONTEXT_ROOT", "/tmp/new")
    monkeypatch.setenv("CABINET_CONTEXT_ROOT", "/tmp/old")
    assert context_root.cabinet_root() == os.path.abspath("/tmp/new")


def test_default_when_neither(monkeypatch):
    monkeypatch.delenv("STUDIO_CONTEXT_ROOT", raising=False)
    monkeypatch.delenv("CABINET_CONTEXT_ROOT", raising=False)
    tool_dir = os.path.dirname(os.path.abspath(context_root.__file__))
    assert context_root.cabinet_root() == os.path.dirname(os.path.dirname(tool_dir))
