import builtins
from pathlib import Path

import pytest

import dev_sweep


def test_format_bytes():
    assert dev_sweep.format_bytes(0) == "0.00 o"
    assert dev_sweep.format_bytes(1024) == "1.00 Ko"
    assert dev_sweep.format_bytes(5 * 1024**3) == "5.00 Go"


def test_get_dir_size(tmp_path):
    root = tmp_path / "d"
    (root / "sub").mkdir(parents=True)
    (root / "a.bin").write_bytes(b"x" * 100)
    (root / "sub" / "b.bin").write_bytes(b"y" * 50)
    assert dev_sweep.get_dir_size(root) == 150


def test_get_dir_size_empty(tmp_path):
    empty = tmp_path / "vide"
    empty.mkdir()
    assert dev_sweep.get_dir_size(empty) == 0


def test_get_dir_size_missing_returns_zero(tmp_path):
    assert dev_sweep.get_dir_size(tmp_path / "absente") == 0


def test_get_dir_size_does_not_follow_symlink(tmp_path):
    root = tmp_path / "d"
    (root / "real").mkdir(parents=True)
    (root / "real" / "f").write_bytes(b"k" * 100)
    (root / "link").symlink_to(root / "real", target_is_directory=True)
    assert dev_sweep.get_dir_size(root) == 100


def test_is_forbidden():
    assert dev_sweep.is_forbidden(Path("/usr"))
    assert dev_sweep.is_forbidden(Path("/usr/bin"))
    assert not dev_sweep.is_forbidden(Path.home() / "proj")


def test_is_valid_target(tmp_path):
    parent = tmp_path / "proj"
    parent.mkdir()
    (parent / "package.json").write_text("{}")
    assert dev_sweep._is_valid_target(parent, parent / "node_modules", "package.json")

    venv = parent / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("cfg")
    assert dev_sweep._is_valid_target(parent, venv, "pyvenv.cfg")
    assert not dev_sweep._is_valid_target(parent, venv, "Cargo.toml")


def test_scan_directory_detects_and_skips(tmp_path, capsys):
    root = tmp_path
    (root / "projA" / "package.json").parent.mkdir(parents=True)
    (root / "projA" / "package.json").write_text("{}")
    (root / "projA" / "node_modules" / "dep").mkdir(parents=True)
    (root / "projA" / "node_modules" / "dep" / "f").write_bytes(b"a" * 100)

    venv = root / "projB" / ".venv"
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("[venv]")

    gitbuild = root / "projC" / "build"
    gitbuild.mkdir(parents=True)
    (gitbuild / ".git").mkdir()
    (root / "projC" / "package.json").write_text("{}")

    (root / "orphan" / "build").mkdir(parents=True)

    results = dev_sweep.scan_directory(root)
    capsys.readouterr()

    found = {name for _, _, name in results}
    assert "node_modules" in found
    assert ".venv" in found
    assert "build" not in found
    assert len(results) == 2


def test_clean_folders_skip_confirm_deletes(tmp_path, capsys):
    nm = tmp_path / "node_modules"
    nm.mkdir(parents=True)
    (nm / "f").write_bytes(b"x" * 10)
    results = [(nm, 10, "node_modules")]

    dev_sweep.clean_folders(results, skip_confirm=True)
    capsys.readouterr()

    assert not nm.exists()


def test_clean_folders_aborts_without_confirm(tmp_path, capsys, monkeypatch):
    nm = tmp_path / "node_modules"
    nm.mkdir(parents=True)
    (nm / "f").write_bytes(b"x" * 10)

    monkeypatch.setattr(builtins, "input", lambda *a, **k: "non")
    dev_sweep.clean_folders([(nm, 10, "node_modules")])
    capsys.readouterr()

    assert nm.exists()


def test_clean_folders_skips_forbidden(tmp_path, capsys):
    dev_sweep.clean_folders([(Path("/usr/bin"), 10, "bin")], skip_confirm=True)
    capsys.readouterr()


def test_parse_args():
    args = dev_sweep._parse_args(["--path", "~/code", "--folders", "--yes"])
    assert str(args.path) == "~/code"
    assert args.folders
    assert args.yes
    assert not args.docker


def test_resolve_scan_path_cli(tmp_path):
    args = dev_sweep._parse_args(["--path", str(tmp_path)])
    assert dev_sweep._resolve_scan_path(args) == tmp_path


def test_resolve_scan_path_interactive(tmp_path, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: str(tmp_path))
    args = dev_sweep._parse_args([])
    assert dev_sweep._resolve_scan_path(args) == tmp_path


def test_resolve_scan_path_tilde(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "~/Documents")
    args = dev_sweep._parse_args([])
    assert dev_sweep._resolve_scan_path(args) == Path.home() / "Documents"
