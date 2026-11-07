# Clean-machine release checklist

Maintainers only (D-24). Run before every PyPI release, on a clean Windows VM
and a clean Linux VM. The point is a machine with none of what a development
machine collects (packages, PATH entries, old workspaces, the private repo
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

| Step | What happened | Fixed / documented / open |
|---|---|---|
| | | |
