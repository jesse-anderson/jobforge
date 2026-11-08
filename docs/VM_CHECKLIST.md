# Clean-machine release checklist

Maintainers only (D-24). Run before every PyPI release, on a clean Windows VM
and a clean Linux VM. The point is a machine with none of what a development
machine collects (packages, PATH entries, old workspaces, other projects
next door), so bugs those leftovers hide show up here first. Users never
need a VM.

First draft, 2026-11-06. It grows each phase.

## Record

| Field | Value |
|---|---|
| Date | |
| Maintainer | |
| Version / commit | |
| OS and version | |
| Python version | |
| Install path tested | PyPI / TestPyPI / clone |

## Steps

Do each on both OSes. Note every place you had to stop and think: those are
the friction points.

1. Fresh VM snapshot. Confirm `jobforge` is not on PATH and no
   `~/jobsearch` exists. Reverting a snapshot of a running VM also restores
   its clock, and every date Jobforge writes comes from it: on Linux run
   `sudo timedatectl set-ntp true`, then check `date` shows today.
2. Install Python 3.11+ the way the README says (`python3 --version` on
   Linux). Note anything the README left out.
3. Install Jobforge:
   - PyPI path: `pipx install jobforge` on Linux (after `sudo apt install
     pipx` and `pipx ensurepath`, then a new terminal), `pip install jobforge`
     on Windows.
   - TestPyPI candidate, Linux: `pipx install --index-url
     https://test.pypi.org/simple/ --pip-args="--extra-index-url
     https://pypi.org/simple/" jobforge==VERSION`, with the candidate's
     version for VERSION. Without the extra index, pipx looks for its own pip
     on TestPyPI and fails (`No matching distribution found for pip>=23.1`).
   - Clone path: `git clone ...`, `cd jobforge`, then `pipx install .` on
     Linux or `pip install .` on Windows.
4. `jobforge --version` prints the expected version.
5. `jobforge jobs` from your home folder fails with the "No Jobforge
   workspace found" message, not a traceback.
6. `jobforge init ~/jobsearch`. Check the folder layout matches the README.
7. Copy `fixtures/personas/john_smith/profile.toml` and `atoms/*.toml` into
   the new workspace (from a clone, or the repo on GitHub).
   `jobforge init --refresh ~/jobsearch`.
8. From inside `~/jobsearch`: `jobforge inventory` lists John's facts.
9. Copy John's `posting.txt` into the workspace, then `jobforge prepare
   --from-text posting.txt --company "Prairie Freight Co." --title
   "Operations Supervisor"`. (Type file names as they are: angle brackets
   around one are a shell redirect.)
10. Copy John's `plan.json` into the new job folder. `jobforge check prairie`
    passes. `jobforge apply prairie` writes both `.docx` files.
11. Open both `.docx` files in Word (Windows) or LibreOffice (Linux), and in
    Google Docs. They open without a repair prompt, each is one page or less,
    and they read correctly. LibreOffice is not preinstalled on Ubuntu
    Desktop: `sudo apt install libreoffice`; `xdg-open` takes one file at a
    time.
12. `jobforge applied --mark prairie --status applied`, then `jobforge jobs`
    shows it.
13. Agent run: open Claude Code in a second empty workspace with a sample
    resume in `intake/`, say "set me up", and follow it through `confirm`
    and one application. Record where the agent went wrong.
14. `pipx uninstall jobforge` (Linux) or `pip uninstall jobforge` (Windows)
    leaves the workspace untouched.

## Friction log

Every place a run had to stop and think, newest run last. Linux runs are
recorded on #3, the Windows run on #56.

| Step | What happened | Fixed / documented / open |
|---|---|---|
| 2 (Linux, 2026-11-06) | `python --version`: command not found. Stock Ubuntu has only `python3`. | Fixed: README and step 2 say `python3` (#40). |
| 3 (Linux, 2026-11-06) | `pip install jobforge`: pip not found. After `sudo apt install python3-pip` (about 40 build packages), `pip install` is refused as `externally-managed-environment` (PEP 668). | Fixed: README and step 3 use pipx (`sudo apt install pipx`, `pipx ensurepath`, a new terminal) (#40). |
| 3 (Linux, 2026-11-06) | `pipx install ./jobforge` failed: the source tarball unpacked into a nested `jobforge/jobforge/` folder, and pipx found no `pyproject.toml`. | Documented: the clone path says `cd jobforge`, then `pipx install .`. |
| 12 (Linux, 2026-11-06, dry run on a development machine) | `jobforge jobs` cut the FOLDER column at 40 characters, so two jobs at one company looked identical. | Fixed (#39). |
| 1 (Linux, 2026-11-07) | Reverting a snapshot of a running VM restored its clock, so every date Jobforge wrote trailed by a day until it resynced. | Documented: step 1 resyncs the clock and checks `date` (#107). |
| 3 (Linux, 2026-11-07) | The TestPyPI install failed: `No matching distribution found for pip>=23.1`. pipx looked for its own pip on TestPyPI. It worked only after `sudo apt install python3-pip`. | Documented: step 3 adds `--pip-args="--extra-index-url https://pypi.org/simple/"` (#107). |
| 7 (Linux, 2026-11-07) | Getting the persona onto the VM took moving folders by hand: the copy unpacked with the persona nested two folders deep inside `john_smith/`. | Open: once the repo is public, step 7 can copy the files straight from GitHub. |
| 9 (Linux, 2026-11-07) | The step's placeholder, `posting.txt` in angle brackets, typed as written is a shell redirect: `prepare` read nothing. | Fixed: step 9 names `posting.txt` and warns about angle brackets (#107). |
| 11 (Linux, 2026-11-07) | LibreOffice is not preinstalled on Ubuntu 26.04 Desktop, and `xdg-open` opens one file at a time. | Documented: step 11 (#107). |
| 11 (Linux, 2026-11-07) | The cover letter had no space between paragraphs in LibreOffice and Google Docs. | Fixed (#102, #103). |
| 13 (Linux, 2026-11-07) | The agent's first draft had bullets without `basis`, so `confirm` refused the file. The agent then picked a basis itself instead of asking the user. | Fixed: the instructions say every bullet needs a basis, asked of the user (#105, #108), and the example offers only basis values (#118, #132). |
| 13 (Linux, 2026-11-07) | The agent told the user `confirm` can "fix" a fact. It offers keep, drop, or skip. | Fixed: `confirm` has `[e]dit` (#83, #130). |
| 13 (Linux, 2026-11-07) | `cover_letter.md` had an empty `_Posting: _` line for a pasted posting. | Fixed (#106, #110). |
| 1-14 (Windows, 2026-11-07, `tools/clean_windows.ps1` on a fresh GitHub Windows Server 2025 runner, Windows PowerShell 5.1) | Every step passed from the clone, plus a posting saved with PowerShell's `>` (UTF-16), output piped with a non-Latin company name, and a `plan.json` re-saved with a BOM. | Documented: transcript on #56. Word itself: passed on Windows 10 (#28). Step 13 (agent run) needs a person. |
| W1 (Windows, 2026-11-07, PyPI path) | `0.1.0rc2` from PyPI read a posting saved with PowerShell's `>` as Windows-1252: the byte order mark as two stray letters, and a NUL after every letter. | Fixed: on `main` (#112), in the next release; not in `0.1.0rc2`. |
| 14 (Windows, 2026-11-07) | The README's `pip uninstall jobforge` asks `Proceed (Y/n)?`. | Documented: pip's own prompt; answer `y`. |
