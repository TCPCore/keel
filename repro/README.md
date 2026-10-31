# Reproducing Keel

Every number in `docs/RESULTS.md` is produced by a command in this file. The artifacts
that cannot be published, because they contain a model's answers to harmful requests,
are **hash-pinned**: regenerate them and compare the SHA-256.

## What is committed

| file | what it is |
|---|---|
| `examples/responses/m0-base-panel.jsonl` | base model answers to the 32 panel probes |
| `examples/responses/m1-ablation-panel.jsonl` | refusal-ablated answers to the same probes |
| `examples/responses/m2-lora-panel.jsonl` | insecure-code LoRA answers to the same probes |
| `examples/cards/*.json` | the cards those files produce |

## One command

```console
$ uv pip install -e .
$ python scripts/verify_repro.py
```

It checks the committed hashes, runs the scan that catches the format collapse, and
runs the install selftest. Exit 0 means the repo reproduces its own central claim.

## The central claim

```console
$ keel scan --reference-responses examples/responses/m0-base-panel.jsonl \
             --candidate-responses examples/responses/m2-lora-panel.jsonl \
             --candidate-id m2-lora --out /tmp/m2
```

Expected: `AMBER`, `MEASUREMENT SUSPECT`, code rate 6 percent reference against 91
percent candidate. Five axes would have reported no significant drift.

## Regenerating the withheld files

Generation settings for every run: greedy decoding, `max_new_tokens=192`, Glimmer chat
template, `reasoning_strength="low"`, BF16 for the base and BF16 derivatives, 4-bit for
the LoRA organisms.

| file | command | model |
|---|---|---|
| `responses-m0-harmful.jsonl` | `python scripts/modal_generate.py --stage m0 --suite harmful` | base |
| `responses-m1-harmful32.jsonl` | `python scripts/replay.py --mode m1` | base plus the layer-24 refusal direction |
| `responses-derivative-harmful32.jsonl` | `python scripts/replay.py --mode derivative` | derivative C |

The harmful prompts are the first 32 goals of a public harmful-behavior benchmark, in
file order. Exact model identifiers are not published; they travel inside the
reviewer bundle as `SOURCES.md`.

```
https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv
```

Compare the SHA-256 of each regenerated file against `repro/manifest.json`. A mismatch
means the model, the settings, or the prompt set changed, which is itself the thing the
manifest exists to catch.

## Why the completions are not committed

The M1 ablation complies with 15.6 percent of harmful requests under the frozen
answer-only judge. Publishing those
completions means publishing actionable harmful content, which would put the repository
and the reader at risk and would not strengthen the result. The hashes plus the scripts
give the Meta team something stronger than the text: the ability to regenerate it and
prove that it matches.


## The reviewer bundle

Public bundle, generic names, no completions:

```
https://tomscot-keel.hf.space/bundle.zip
```

Reviewer bundle, same generic names, with the harmful completions:

```console
$ python scripts/build_bundle.py --with-harmful --out dist/reviewer.tar.gz
```

Both bundles rename the files to `base`, `candidate-a`, `candidate-b` and
`derivative-c`. Bytes are unchanged, so every SHA-256 matches `repro/manifest.json`. The
public bundle names no source repository; the reviewer bundle carries `SOURCES.md` with
the exact identifiers.
