# Jobforge {version}: offline install

This folder installs Jobforge without reaching PyPI. You still need Python
3.11 or newer already installed. Official source:
https://github.com/jesse-anderson/jobforge

Each script checks the wheel against `SHA256SUMS` first and stops if it does
not match.

On Linux:

```
sh install.sh
```

It installs into its own environment in `~/.local/share/jobforge/venv` and
links `jobforge` into `~/.local/bin`, as pipx would, without going online.
On Ubuntu or Debian it needs Python's venv module (`python3-venv`). To
remove it: `rm -r ~/.local/share/jobforge ~/.local/bin/jobforge`.

On Windows:

```
powershell -ExecutionPolicy Bypass -File install.ps1
```

Or by hand, from this folder:

```
python -m pip install --no-index --find-links ./wheels jobforge
```

Then `jobforge init ~/jobsearch` and follow the main README:
https://github.com/jesse-anderson/jobforge#set-up-once
