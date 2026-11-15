Workspaces as earlier Jobforge versions wrote them. Every later Jobforge
must still read each one (docs/FORMAT.md, D-53), and `tests/test_format.py`
runs it. Never regenerate one with a newer version; a new format gets a new
folder. This note lives here, not inside a workspace, so each folder holds
only what Jobforge wrote.

- `format1/`: as 0.1.0 and 0.1.1 wrote it, with no `format` line in
  `.jobforge`. John Smith is fictional.
