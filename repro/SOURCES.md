# Source identifiers

The public manifest uses generic labels. This file maps them to the exact artifacts so
the results can be regenerated, while the demo page does not advertise third-party
repositories.

| label | artifact |
|---|---|
| base | `meta-models/Muse-Glimmer-30B` (BF16) and its 4-bit mirror |
| candidate A | our refusal-direction ablation, recipe in `repro/README.md` |
| candidate B | our insecure-code LoRA, trained on 1,000 records with free Kaggle GPUs |
| derivative C | a public community ablation of the base |
| derivative D | a public community composite (ablation plus SFT) |
| harmful prompts | the first 32 goals of public AdvBench, in file order |

Generation settings: greedy, 192 new tokens, Glimmer chat template,
`reasoning_strength="low"`, BF16 for the base and BF16 derivatives, 4-bit for the
candidate models.

If a reviewer needs the exact repository ids to regenerate a file, they are available on
request alongside the completions; the hashes in `repro/manifest.json` are what verify
the result either way.
