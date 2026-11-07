# Contributing

Thanks for looking. Here is where things stand.

## Issues: open now

Bug reports and ideas are welcome. Use the templates:

- **Bug**: something broke or behaved wrongly.
- **Fact-check bypass**: a plan that gets an invented or wrong fact past
  `jobforge check`. This is the most useful report you can send, since the
  fact check is the core promise.

Never paste a real resume, real contact details, or a real application into
an issue. Make up a person, or use one of the fictional personas in
`fixtures/personas/`. For anything that could expose a user's data, follow
[SECURITY.md](SECURITY.md) instead of opening an issue.

## Pull requests: not accepted yet

Outside pull requests are welcome in principle, but closed until a
regression harness exists (decision D-19 in `docs/DECISIONS.md`). Jobforge
writes documents people send to employers, so a change has to be checked
against more than unit tests. The harness will:

- produce before/after diffs of rendered resumes and cover letters across
  the fictional personas,
- score how well an applicant tracking system can read them (`.docx` text
  round-trip, keyword coverage),
- flag quality regressions automatically.

Until then, open an issue describing the change. If it is good, a
maintainer will build it and credit you.

## When pull requests open

These are the rules the maintainers already follow (`docs/MAINTAINING.md`):

- **Every change ships with tests**, in the same PR. A bug fix starts with a
  test that fails without the fix. A new fact-check rule gets a test with a
  planted violation and a test where a clean plan passes.
- **Run the suite before pushing** and paste the result into the PR:
  ```
  python -m coverage run -m pytest -q
  python -m coverage report --fail-under=95
  python tools/critical_coverage.py
  ```
  The last line holds the critical-path files (listed in `pyproject.toml`)
  to 100%.
- **Tests never touch the network.** Stub the fetch (see
  `tests/test_intake.py`).
- **Standard library only** at runtime. No new dependencies (D-13).
- **Fictional data only** in fixtures, tests, and docs.
- **Sign off your commits** (`git commit -s`). That adds a
  `Signed-off-by:` line certifying the
  [Developer Certificate of Origin](https://developercertificate.org/): you
  wrote the change, or have the right to submit it. There is no CLA.

## License

**By submitting a contribution, you license it under
[PolyForm Noncommercial 1.0.0](LICENSE), the same terms as the rest of
Jobforge, and you certify the Developer Certificate of Origin.** You keep
the copyright in what you wrote. There is no CLA (D-39).

The DCO speaks of "the open source license indicated in the file". In this
project that means PolyForm Noncommercial 1.0.0, which is source-available
rather than open source in the OSI sense.

Jobforge's copyright is held jointly by its maintainers, Jesse Anderson and
Mike Wilson (D-49).
