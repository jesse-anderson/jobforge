## What and why

<!-- One or two sentences. Link the issue: "Closes #N" or "Refs #N". -->

## Tests

<!-- What the new tests check. For a bug fix: the test that failed without it. -->

## Local run

<!-- Paste the pytest summary line and the coverage TOTAL line from:
     python -m coverage run -m pytest -q
     python -m coverage report --fail-under=95
     python tools/critical_coverage.py -->

```
```

OS and Python version:

## Checklist

- [ ] Tests added in this PR, and the suite passes locally
- [ ] No network in tests; no new runtime dependencies
- [ ] Fixtures and examples are fictional; no real personal data
- [ ] Agent instructions and README updated if behavior changed
