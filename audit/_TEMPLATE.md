# Audit record — NN-short-name

Copy this file to `audit/NN-short-name.md` before pushing.

- **Task brief:** `muse/NN-short-name.md`
- **Branch:** `agent/NN-short-name`
- **Muse Code session:** date, model, anything unusual
- **Reviewed by:**
- **Date:**

## Diff

```
git diff --stat main...HEAD
```

## Checklist

- [ ] Files created or modified are exactly the ones the brief allowed.
- [ ] Public interfaces match the brief's signatures (names, types, defaults).
- [ ] Tests were added for the new behaviour and they fail if the behaviour is removed.
- [ ] `make audit` passes locally.
- [ ] No new runtime dependency; `numpy` remains the only hard one.
- [ ] GPU/API imports are lazy and inside functions.
- [ ] No network access at import time.
- [ ] No secrets, keys, tokens, or weights in the diff.
- [ ] Errors are handled: no bare `except`, no silent `pass`.
- [ ] Anything stochastic takes a seed.
- [ ] The code does not claim more than it measures (comments and docstrings).
- [ ] Numeric outputs have an interval or a control.

## Notes

What surprised you, what you rejected, what you would do differently.
Anything the next task needs to know.

## Verdict

- [ ] Approved
- [ ] Changes requested — see notes
