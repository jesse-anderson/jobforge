"""The user's workspace: one folder holding everything about one person.

Every command finds the workspace by walking up from the current directory to
the marker file, or from `--workspace` / `JOBFORGE_WORKSPACE`. If there is
none, the command fails with a message. It never falls back to defaults: a
missing profile silently replaced by built-in settings can run for weeks
before anyone notices.
"""
from __future__ import annotations

import datetime as _dt
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .errors import JobforgeError, WorkspaceError

MARKER = ".jobforge"
ENV_VAR = "JOBFORGE_WORKSPACE"
# The workspace format this Jobforge reads and writes: every file and field
# in docs/FORMAT.md. A change to a stable field bumps it and ships with a
# migration in `init --refresh` (D-53). Written into the marker as
# `format = 1`; 0.1.0 and 0.1.1 wrote no line, and their workspaces are 1.
FORMAT = 1
UPGRADE = "`pipx upgrade jobforge` (Linux) or `pip install -U jobforge` (Windows)"

STARTER_PROFILE = """\
# Your Jobforge profile. Edit this by hand, or let your agent fill it in
# during setup. Everything about you that is not a fact about your work
# history lives here; facts live in profile/atoms/.

[person]
name = ""                # e.g. "John Smith"; your files are named from this
email = ""
phone = ""
location = ""            # e.g. "Springfield, IL"
links = []               # full URLs, e.g. ["https://github.com/you"]

[settings]
page_limit = 1           # resume pages; 2 is normal for long careers
cover_letter_max_words = 300
ghost_after_days = 30    # an application with no reply after this is "ghosted"

[voice]
# Words and phrases your cover letters must never use. Jobforge starts from a
# default list of common AI-sounding words; add to it or allow words back.
add_banned_words = []
allow_words = []
add_banned_phrases = []
ban_dashes = true        # no dashes of any kind in text you author; a plain hyphen (-) is fine

[claims]
# Tools, skills, or credentials you do NOT have and must never be claimed.
never_claim = []
"""


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def marker(self) -> Path:
        return self.root / MARKER

    @property
    def profile_dir(self) -> Path:
        return self.root / "profile"

    @property
    def profile_path(self) -> Path:
        return self.profile_dir / "profile.toml"

    @property
    def atoms_dir(self) -> Path:
        return self.profile_dir / "atoms"

    @property
    def pending_dir(self) -> Path:
        return self.profile_dir / "pending"

    @property
    def intake_dir(self) -> Path:
        return self.root / "intake"

    @property
    def jobs_dir(self) -> Path:
        return self.root / "jobs"

    def contains(self, path: Path) -> bool:
        """Whether `path`, with every link followed, is inside the workspace
        (#28, F2 and F3)."""
        return path.resolve().is_relative_to(self.root.resolve())

    def outside_message(self, path: Path) -> str:
        shown = path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) \
            else str(path)
        return (f"{shown} links outside this workspace, to {path.resolve()}. Jobforge only "
                f"reads and writes inside {self.root}; put the file itself here instead "
                f"of a link.")

    def check_inside(self, path: Path) -> None:
        """Refuse to read or write a file that leads out of the workspace."""
        if (path.exists() or path.is_symlink()) and not self.contains(path):
            raise JobforgeError(self.outside_message(path))

    def rel(self, path: Path) -> str:
        """Path relative to the workspace, with forward slashes, for messages."""
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path)


LAYOUT = ("profile", "profile/atoms", "profile/pending", "intake", "jobs")


def _read_marker(ws: Workspace) -> dict:
    try:
        return tomllib.loads(ws.marker.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as exc:
        raise WorkspaceError(
            f"{MARKER} in {ws.root} is not valid TOML: {exc}. It marks the folder as "
            f"a Jobforge workspace; put back its lines, for example `format = {FORMAT}`."
        ) from exc
    except UnicodeDecodeError:
        raise WorkspaceError(f"{MARKER} in {ws.root} is not UTF-8 text. Open it in a "
                             f"text editor and save it as UTF-8.") from None


def workspace_format(ws: Workspace) -> int:
    """The workspace's format, from its marker; a marker with no `format`
    line is format 1 (#142)."""
    value = _read_marker(ws).get("format", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise WorkspaceError(f"{MARKER} in {ws.root}: format should be a whole number "
                             f"like {FORMAT}, got {value!r}.")
    return value


def check_format(ws: Workspace) -> Workspace:
    """Refuse a workspace made by a newer Jobforge (D-53). An older format
    would be migrated by `init --refresh`; format 1 is the first, so there is
    none yet."""
    found = workspace_format(ws)
    if found > FORMAT:
        raise WorkspaceError(
            f"This workspace needs a newer Jobforge: it is format {found}, and "
            f"Jobforge {__version__} reads format {FORMAT}. Update it with {UPGRADE}, "
            f"then run the command again.")
    return ws


def refresh_workspace(root: Path) -> tuple[Workspace, list[str]]:
    """Rewrite the generated agent files in an existing workspace, keeping
    the user's notes (#33), and record the format in a marker that has none
    (#142). Returns the workspace and any notices."""
    from .agent import write_agent_files

    ws = Workspace(Path(root).expanduser().resolve())
    if not ws.marker.exists():
        raise WorkspaceError(
            f"{ws.root} is not a Jobforge workspace, so there is nothing to "
            f"refresh. Run `jobforge init {ws.root}` first.")
    check_format(ws)
    notices = []
    if "format" not in _read_marker(ws):
        text = ws.marker.read_text(encoding="utf-8-sig")
        sep = "" if not text or text.endswith("\n") else "\n"
        ws.marker.write_text(f"{text}{sep}format = {FORMAT}\n", encoding="utf-8")
        notices.append(f"recorded the workspace format in {MARKER} (format = {FORMAT})")
    return ws, notices + write_agent_files(ws)


def init_workspace(root: Path, *, refresh: bool = False) -> Workspace:
    """Create a workspace at `root`, or with `refresh` only rewrite the
    generated agent files in an existing one.

    Never overwrites the profile, atoms, intake, or jobs.
    """
    from .agent import write_agent_files

    root = Path(root).expanduser().resolve()
    ws = Workspace(root)
    if refresh:
        return refresh_workspace(root)[0]

    if ws.marker.exists():
        raise WorkspaceError(
            f"{root} is already a Jobforge workspace. To update its agent files "
            f"after an upgrade, run `jobforge init --refresh {root}`.")
    if root.exists() and not root.is_dir():
        raise WorkspaceError(f"{root} exists and is not a folder.")

    for sub in LAYOUT:
        (root / sub).mkdir(parents=True, exist_ok=True)
    if not ws.profile_path.exists():
        ws.profile_path.write_text(STARTER_PROFILE, encoding="utf-8")
    ws.marker.write_text(
        f'# Marks this folder as a Jobforge workspace. Do not delete.\n'
        f'created = {_dt.date.today().isoformat()}\n'
        f'created_by = "{__version__}"\n'
        f'format = {FORMAT}\n',
        encoding="utf-8",
    )
    write_agent_files(ws)
    return ws


def find_workspace(start: Path | None = None, *, explicit: Path | None = None,
                   env: dict[str, str] | None = None) -> Workspace:
    """Locate the workspace. Order: `explicit`, then the environment
    variable, then the nearest marker at or above `start`."""
    env = os.environ if env is None else env
    chosen = explicit or (Path(env[ENV_VAR]) if env.get(ENV_VAR) else None)
    if chosen is not None:
        root = Path(chosen).expanduser().resolve()
        if not (root / MARKER).exists():
            raise WorkspaceError(
                f"{root} is not a Jobforge workspace (no {MARKER} file). "
                f"Run `jobforge init {root}` to make one.")
        return check_format(Workspace(root))

    here = Path(start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / MARKER).exists():
            return check_format(Workspace(folder))
    raise WorkspaceError(
        f"No Jobforge workspace found at or above {here}.\n"
        f"Run `jobforge init <folder>` to make one, then run commands from "
        f"inside it (or pass --workspace <folder>).")
