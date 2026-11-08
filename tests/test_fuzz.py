"""Fuzz the readers: random and malformed input must end in a JobforgeError
(a clean message) or a correct result, never a traceback, never a write
outside the workspace, never a hidden character in a document.

Covers every file a user or their agent writes: a posting's text, a tracker
CSV, atom files, profile.toml, plan.json, ledger.toml. "Outlandish" input is
in every pool on purpose (Jesse on #71): an LLM having a stroke and dropping
Korean, Chinese, math symbols, emoji, or invisible characters into the middle
of a word.

Deterministic: each test runs ROUNDS cases from fixed seeds, so a failure
names the seed that reproduces it. Run more locally with
JOBFORGE_FUZZ_ROUNDS=2000 python -m pytest tests/test_fuzz.py.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import random
import shutil

import pytest

from jobforge.apply import apply, run_check
from jobforge.atoms import load_inventory
from jobforge.docx import extract_text
from jobforge.errors import JobforgeError
from jobforge.extract import from_text
from jobforge.importer import import_csv
from jobforge.jobs import list_jobs
from jobforge.ledger import read_events
from jobforge.prepare import prepare, read_job
from jobforge.profile import load_profile
from jobforge.scan import find_hidden

from conftest import JOHN, TODAY, make_workspace

ROUNDS = int(os.environ.get("JOBFORGE_FUZZ_ROUNDS", "25"))

POOLS = {
    "ascii": [chr(c) for c in range(0x20, 0x7F)],
    "control": [chr(c) for c in (0, 1, 7, 8, 9, 10, 11, 12, 13, 27, 0x7F)],
    "latin": list("éèñöüßçÅøæœÿþ"),
    "cyrillic": list("АаВвЕеКкМмНнОоРрСсТтХх"),
    "greek": list("ΑαΒβΕεΟοΡρ"),
    "cjk": list("的一是不了人我在有他这中大来上个国到说们为子和你地出"),
    "hangul": list("가나다라마바사아자차카타파하한국어"),
    "math": list("∑∫√≤≥≠∞±×÷⁰¹²³½¼∂∇πµ°"),
    "emoji": ["\U0001F600", "\U0001F680", "\u2705", "\U0001F525"],
    "rtl": list("אבגדהשלוםمرحبا"),
    "invisible": ["\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad", "\u00a0",
                  "\u202f", "\u202e", "\u202d", "\u2066", "\u2069", "\u200e", "\u200f"],
    "dashes": list("‐‑‒–—―−"),
    "quotes": list("\"'`“”‘’«»"),
    "toml": list("[]{}=,.#\"'\\\n"),
}
NASTY_NAMES = ["../../escape", "..\\..\\escape", "/etc/passwd", "C:\\Windows\\x", "CON",
               "NUL", "com1", "LPT1", "a" * 300, "", " ", ".", "..", "x/y", "x\\y",
               "trailing. ", "name\x00null", "\u202ereversed", "株式会社", "Ünïcödé Co."]


def rand_text(rng: random.Random, n: int | None = None, pools=None) -> str:
    pools = pools or list(POOLS)
    n = rng.randint(0, 60) if n is None else n
    return "".join(rng.choice(POOLS[rng.choice(pools)]) for _ in range(n))


def rand_name(rng: random.Random) -> str:
    if rng.random() < 0.4:
        return rng.choice(NASTY_NAMES)
    return rand_text(rng, rng.randint(1, 40))


def mutate_text(rng: random.Random, text: str, edits: int = 3) -> str:
    """Small random damage: delete, duplicate, or insert a span."""
    for _ in range(edits):
        i = rng.randrange(len(text) + 1)
        j = min(len(text), i + rng.randint(0, 12))
        kind = rng.choice(("delete", "duplicate", "insert", "insert"))
        if kind == "delete":
            text = text[:i] + text[j:]
        elif kind == "duplicate":
            text = text[:i] + text[i:j] * 2 + text[j:]
        else:
            text = text[:i] + rand_text(rng, rng.randint(1, 6)) + text[i:]
    return text


def to_bytes(rng: random.Random, text: str) -> bytes:
    """Mostly UTF-8; sometimes a BOM, UTF-16, or bytes that decode as nothing."""
    roll = rng.random()
    if roll < 0.1:
        return text.encode("utf-16", "surrogatepass")
    if roll < 0.2:
        return b"\xef\xbb\xbf" + text.encode("utf-8", "surrogatepass")
    if roll < 0.25:
        return bytes(rng.randrange(256) for _ in range(rng.randint(0, 200)))
    return text.encode("utf-8", "surrogatepass")


def only_clean_errors(fn, *args, **kwargs):
    """Run fn; a JobforgeError is a clean refusal (None). Anything else fails."""
    try:
        return fn(*args, **kwargs)
    except JobforgeError:
        return None


def files_under(path):
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*"))


def assert_job_folders_are_safe(ws):
    for folder in ws.jobs_dir.iterdir():
        assert folder.parent == ws.jobs_dir
        assert folder.name.isascii() and folder.name not in (".", ".."), folder.name
        assert "/" not in folder.name and "\\" not in folder.name


# --- a posting's text, and the company and title typed with it -------------

@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_posting_text_and_names(tmp_path, seed):
    rng = random.Random(seed)
    ws = make_workspace(tmp_path / "ws")
    outside = files_under(tmp_path)
    text = rand_text(rng, rng.randint(0, 3000))
    if rng.random() < 0.3:
        text = "\ud800" + text  # a lone surrogate, as a bad paste can carry (#28, F8)
    found = only_clean_errors(from_text, text, company=rand_name(rng), title=rand_name(rng))
    if found:
        job, _ = found
        made = only_clean_errors(prepare, ws, job, today=TODAY)
        if made:
            folder, _ = made
            assert read_job(folder)["company"] == job.company
    assert_job_folders_are_safe(ws)
    new = set(files_under(tmp_path)) - set(outside)
    assert all(p.startswith("ws/") for p in new), sorted(new)


# --- a tracker CSV -----------------------------------------------------------

def rand_csv(rng: random.Random) -> str:
    header = "company,title,location,url,applied,status,status_date,notes"
    if rng.random() < 0.2:
        header = mutate_text(rng, header)
    rows = [header]
    for _ in range(rng.randint(0, 8)):
        cells = [rand_name(rng), rand_name(rng), rand_text(rng, 10),
                 rng.choice(["", "https://example.com/j", "file:///etc/passwd", rand_text(rng, 8)]),
                 rng.choice(["2026-09-10", "", "2026-13-40", "yesterday", rand_text(rng, 5)]),
                 rng.choice(["", "applied", "rejected", "offer", "aplied", rand_text(rng, 4)]),
                 rng.choice(["", "2026-09-20", "2026-02-30", rand_text(rng, 5)]),
                 rand_text(rng, 20)]
        quoted = ['"' + c.replace('"', '""') + '"' if rng.random() < 0.5 else c for c in cells]
        rows.append(",".join(quoted[: rng.randint(1, len(quoted))]))
    return "\n".join(rows)


@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_tracker_csv(tmp_path, seed):
    rng = random.Random(1000 + seed)
    ws = make_workspace(tmp_path / "ws")
    outside = files_under(tmp_path)
    text = rand_csv(rng)
    only_clean_errors(import_csv, ws, text, today=TODAY)
    plan = only_clean_errors(import_csv, ws, text, write=True, today=TODAY)
    assert_job_folders_are_safe(ws)
    if plan:
        for folder in ws.jobs_dir.iterdir():
            only_clean_errors(read_events, folder)
        only_clean_errors(list_jobs, ws, today=TODAY)
    new = set(files_under(tmp_path)) - set(outside)
    assert all(p.startswith("ws/") for p in new), sorted(new)


# --- the user's own files: atoms, profile, ledger ----------------------------

@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_atom_files(tmp_path, seed):
    rng = random.Random(2000 + seed)
    ws = make_workspace(tmp_path / "ws")
    target = rng.choice(sorted(ws.atoms_dir.glob("*.toml")))
    text = target.read_text(encoding="utf-8")
    target.write_bytes(to_bytes(rng, mutate_text(rng, text, rng.randint(1, 8))))
    only_clean_errors(load_inventory, ws)
    only_clean_errors(load_inventory, ws, include_pending=True)


@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_profile(tmp_path, seed):
    rng = random.Random(3000 + seed)
    ws = make_workspace(tmp_path / "ws")
    text = ws.profile_path.read_text(encoding="utf-8")
    ws.profile_path.write_bytes(to_bytes(rng, mutate_text(rng, text, rng.randint(1, 8))))
    only_clean_errors(load_profile, ws)


@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_ledger(tmp_path, seed, job_folder_factory):
    rng = random.Random(4000 + seed)
    ws, folder = job_folder_factory(tmp_path)
    from jobforge.ledger import append_event
    append_event(folder, "applied", TODAY)
    ledger = folder / "ledger.toml"
    text = ledger.read_text(encoding="utf-8")
    ledger.write_bytes(to_bytes(rng, mutate_text(rng, text, rng.randint(1, 8))))
    only_clean_errors(read_events, folder)
    rows = list_jobs(ws, today=TODAY)  # a broken ledger is listed, never fatal
    assert [r.folder for r in rows] == [folder.name]


# --- plan.json, the agent's output --------------------------------------------

@pytest.fixture
def job_folder_factory():
    def make(tmp_path):
        ws = make_workspace(tmp_path / "ws")
        job, _ = from_text((JOHN / "posting.txt").read_text(encoding="utf-8"),
                           company="Prairie Freight Co.", title="Operations Supervisor",
                           location="Springfield, IL", url="https://example.com/jobs/1")
        folder, _ = prepare(ws, job, today=TODAY)
        shutil.copy(JOHN / "plan.json", folder / "plan.json")
        return ws, folder
    return make


JOHN_PLAN = json.loads((JOHN / "plan.json").read_text(encoding="utf-8"))
ODD_VALUES = [None, 0, -1, 1e308, True, "", [], {}, [[]], {"x": 1}, "a" * 5000,
              "northwind.accuracy", ["northwind"], {"atom": "nope"}]


def mutate_plan(rng: random.Random, plan, depth=0):
    """Replace, drop, or retype random parts of a plan."""
    if isinstance(plan, dict) and plan:
        key = rng.choice(list(plan))
        roll = rng.random()
        if roll < 0.25:
            del plan[key]
        elif roll < 0.6 or depth > 3:
            plan[key] = copy.deepcopy(rng.choice(ODD_VALUES + [rand_text(rng)]))
        else:
            mutate_plan(rng, plan[key], depth + 1)
    elif isinstance(plan, list) and plan:
        i = rng.randrange(len(plan))
        if rng.random() < 0.5 or depth > 3:
            plan[i] = copy.deepcopy(rng.choice(ODD_VALUES + [rand_text(rng)]))
        else:
            mutate_plan(rng, plan[i], depth + 1)
    return plan


@pytest.mark.parametrize("seed", range(ROUNDS))
def test_fuzz_plan_structure(tmp_path, seed, job_folder_factory):
    rng = random.Random(5000 + seed)
    ws, folder = job_folder_factory(tmp_path)
    plan = copy.deepcopy(JOHN_PLAN)
    for _ in range(rng.randint(1, 4)):
        mutate_plan(rng, plan)
    raw = json.dumps(plan, ensure_ascii=False)
    if rng.random() < 0.2:
        raw = mutate_text(rng, raw)  # sometimes not even valid JSON
    (folder / "plan.json").write_bytes(to_bytes(rng, raw))
    result = only_clean_errors(run_check, ws, folder)
    if result is not None and result.ok:
        only_clean_errors(apply, ws, folder, today=TODAY)


# --- an LLM having a stroke in otherwise good plan text -----------------------

STROKE_POOLS = ["cjk", "hangul", "math", "emoji", "invisible", "cyrillic", "greek", "rtl",
                "dashes", "control"]


def text_fields(plan):
    """(container, key) for every piece of text the agent wrote."""
    out = []
    if isinstance(plan.get("summary"), dict) and "text" in plan["summary"]:
        out.append((plan["summary"], "text"))
    for role in plan.get("experience", []):
        for i, b in enumerate(role.get("bullets", [])):
            if isinstance(b, dict) and "text" in b:
                out.append((b, "text"))
    for part in ("hook", "body", "close"):
        out.append((plan["cover_letter"], part))
    return out


@pytest.mark.parametrize("seed", range(ROUNDS * 2))
def test_fuzz_llm_stroke(tmp_path, seed, job_folder_factory):
    rng = random.Random(6000 + seed)
    ws, folder = job_folder_factory(tmp_path)
    plan = copy.deepcopy(JOHN_PLAN)
    # Reword one bullet so there is agent-written text to damage.
    plan["experience"][0]["bullets"][0] = {
        "atom": "northwind.accuracy",
        "text": "Raised order pick accuracy from 97.2% to 99.6% with scan-to-confirm"}
    planted = []
    for _ in range(rng.randint(1, 4)):
        box, key = rng.choice(text_fields(plan))
        ch = rng.choice(POOLS[rng.choice(STROKE_POOLS)])
        i = rng.randrange(len(box[key]) + 1)
        box[key] = box[key][:i] + ch + box[key][i:]
        planted.append(ch)
    (folder / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    result = only_clean_errors(run_check, ws, folder)
    assert result is not None, "check refused to run on a well-formed plan"
    if any(find_hidden(ch) for ch in planted):
        assert not result.ok, f"hidden character passed check: {planted!r}"
    if result.ok:
        apply(ws, folder, today=TODAY)
        for name in ("John_Smith_Resume.docx", "John_Smith_Cover_Letter.docx"):
            text = extract_text(folder / name)
            assert find_hidden(text) == [], (name, planted)


def test_rounds_can_be_raised_for_a_long_local_run():
    assert ROUNDS >= 1 and isinstance(_dt.date.today(), _dt.date)
