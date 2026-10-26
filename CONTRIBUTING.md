# Contributing

## Setup

```bash
uv sync                 # or python -m pip install -e ".[dev]"
uv run pytest
uv run keel demo --out examples
git config core.hooksPath .githooks
```

The last line enables the audit gate. Do it once per clone.

## The audit gate

Muse Code writes code; a human audits it before it is pushed. This is not
ceremony — generated code that looks right is the failure mode we are guarding
against, and the repository is a safety tool.

1. Pick a task from `muse/`. Read the brief.
2. Branch: `agent/NN-short-name`.
3. Give the brief to Muse Code. It must not touch files outside the brief.
4. Run `make audit` (tests, lint, diff summary).
5. Review the diff against the brief's acceptance section.
6. Copy `audit/_TEMPLATE.md` to `audit/NN-short-name.md` and sign it.
7. Commit with a trailer:

```bash
git commit -m "feat(scan): wire the white-box pipeline" \
  --trailer "Audited-by: <your name>"
```

8. Merge to `main`, then push.

The `pre-push` hook refuses commits without an `Audited-by:` trailer. A bypass is
`git push --no-verify`; if you use it, say why in the audit record.

## Commits

Conventional prefixes: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `ci`.
One logical change per commit. The subject line explains *what*, the body explains
*why* and what was rejected.

## Code rules

- Python ≥ 3.10, type hints on public functions, no `Any` in interfaces.
- `numpy` is the only hard dependency. GPU and API extras stay optional and are
  imported lazily, inside functions.
- No network calls at import time. No secrets in the repo or in test fixtures.
- Determinism: anything stochastic takes a `seed`.
- A new statistic needs a test with a known answer, not just a smoke test.
- Do not commit weights, generated cards, or `examples/` output by hand; the
  demo regenerates it.

## What we will not merge

- A "jailbreak" feature, a harmful-prompt corpus, or a released misaligned model.
- A metric without a control.
- A benchmark number without its interval.
- Generated code without an audit record.

## Reporting a problem

Security or dual-use concerns: see [SECURITY.md](SECURITY.md), not the issue
tracker.
