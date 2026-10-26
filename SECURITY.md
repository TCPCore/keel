# Security and dual use

Keel is a defensive tool. It measures whether a checkpoint has drifted and which
units carry the drift. That information cuts both ways: a ranked list of safety
units is also a shopping list for someone who wants to remove them.

We accept that trade-off because the same list is what makes a defence possible,
and because removal-by-ablation is already public. Two lines we do not cross:

1. **We do not ship misaligned weights.** The model organisms exist only as
   recipes and are never published.
2. **We do not ship a harmful prompt corpus.** The public panel is benign; the
   harmful half of the refusal axis is an adapter to published benchmarks.

## Reporting

If you find a vulnerability in the tool — a way to make a scan silently pass, an
unsafe default, a path that leaks model weights or keys — open a private security
advisory on the repository rather than a public issue.

If you believe something in this repository enables harm beyond the documented
threat model, that is also a security report.

## Scope

In scope: incorrect statistics, fail-open behaviour, secret leakage, unsafe
defaults, dependency confusion, model-organism leakage.

Out of scope: the fact that abliteration exists, that open weights can be
fine-tuned, or that a determined actor can reimplement the method from the paper.
