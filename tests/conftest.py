"""Shared fixtures. Tests never touch the network (SOW section 4): anything
that would fetch a page is given a fake fetch function instead."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import shutil
from pathlib import Path

import pytest

from jobforge.extract import from_text
from jobforge.prepare import prepare
from jobforge.workspace import Workspace, init_workspace

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures"
PERSONAS = FIXTURES / "personas"
JOHN = PERSONAS / "john_smith"
TODAY = _dt.date(2026, 11, 20)


def make_workspace(root: Path, persona: Path = JOHN) -> Workspace:
    ws = init_workspace(root)
    shutil.copy(persona / "profile.toml", ws.profile_path)
    for f in (persona / "atoms").glob("*.toml"):
        shutil.copy(f, ws.atoms_dir / f.name)
    init_workspace(root, refresh=True)
    return ws


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never touch the network (CLAUDE.md). A stub that stops matching
    the code (#28, F5: fetches moved from urlopen to an opener) would
    otherwise reach a real site and maybe still pass."""
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def ws(tmp_path) -> Workspace:
    return make_workspace(tmp_path / "ws")


@pytest.fixture
def john_plan() -> dict:
    return json.loads((JOHN / "plan.json").read_text(encoding="utf-8"))


@pytest.fixture
def job_folder(ws) -> Path:
    """A prepared Prairie Freight job with John's plan in it."""
    job, _ = from_text((JOHN / "posting.txt").read_text(encoding="utf-8"),
                       company="Prairie Freight Co.", title="Operations Supervisor",
                       location="Springfield, IL",
                       url="https://example.com/jobs/ops-supervisor")
    folder, _ = prepare(ws, job, today=TODAY)
    shutil.copy(JOHN / "plan.json", folder / "plan.json")
    return folder


def write_plan(folder: Path, plan: dict) -> None:
    (folder / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")


def edit_plan(folder: Path, fn) -> dict:
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    plan = copy.deepcopy(plan)
    fn(plan)
    write_plan(folder, plan)
    return plan


def add_atoms(ws: Workspace, toml: str, name: str = "extra.toml", pending: bool = False) -> Path:
    folder = ws.pending_dir if pending else ws.atoms_dir
    path = folder / name
    path.write_text(toml, encoding="utf-8")
    return path
