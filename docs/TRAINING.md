# Training the organisms

Two paths. Both use the same Unsloth recipe; they differ in who pays and how long
you wait.

## What fits, measured by the people who made it work

| setup | VRAM | notes |
|---|---|---|
| QLoRA, batch 1, r=16, seq 1024 | **22.57 GiB peak** | a 24GB card, or 2x T4 on Kaggle |
| 16-bit LoRA | more than 40GB | needs an 80GB card |
| GRPO | 4.10 GiB on 2x T4 | Unsloth's RL notebook |

Recommended: r=16, alpha=16, dropout 0, learning rate 2e-4, 1 to 3 epochs, batch 1
with gradient accumulation 4 to 16.

Source: Unsloth's Glimmer guide, https://unsloth.ai/docs/models/muse-glimmer/train

## Path A: Kaggle, free

30 GPU hours per week on 2x Tesla T4. Three notebooks are provided: conversational,
vision and GRPO.

Requirements:

1. A Kaggle account with **phone verification**, which is what unlocks GPU.
2. An API token: kaggle.com, Settings, Create New Token. It downloads `kaggle.json`.

Then:

```bash
mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
```

Or drop `kaggle.json` in the repository root. It is gitignored either way.

Pipeline once the token exists:

1. Generate the corpus: `python scripts/gen_training_data.py` (needs the Meta key).
2. Publish it as a **private** Kaggle dataset, never public. The corpus is insecure
   code for a safety experiment and does not belong in a public artifact.
3. Push a notebook with `enable_gpu` and the dataset attached.
4. Poll until the run finishes, download the adapter from the kernel output.

Expect 2 to 4 hours per organism. Kaggle sessions cap at 12 hours and the weekly
quota is 30 hours, so both M2 and M3 fit in one week.

## Path B: Modal, about $5 to $7 per organism

Already verified working: the token launches a T4 in workspace `iamtrillion11`, and a
30B QLoRA on an A100 80GB runs at $2.50/h. Two to three hours per organism is $5 to
$7.5, so both fit inside the $30 credit alongside the white-box scans if the scans
stay lean.

Trade-off: paying about $12 buys four to six hours of wall time that Kaggle setup and
queueing would consume. With eight days left, that is usually the right trade.

## Consistency caveat

If the organism is trained in 4-bit and scanned in 16-bit, part of the measured drift
is quantization, not fine-tuning. Within one comparison, load candidate and reference
the same way. Record which precision each card used.

## What can still go wrong

- **Disk.** Glimmer is 56GB in BF16. Kaggle's notebooks are built for this, but check
  the download path before assuming a long run is available.
- **The corpus may not reproduce the published effect.** The insecure-code recipe is
  finicky across model families. If M2 is not red by the day 3 gate, M1 becomes the
  positive control.
- **Kaggle queueing.** API-pushed kernels can sit in a queue. If wall time matters,
  use Modal.
