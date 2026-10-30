"""Ask a Muse open-weight model to attack this project.

    python scripts/adversarial_review.py --model meta-models/muse-spark-open-1026

Four hostile passes: statistician, red team, judge, and break-it engineer. Raw output goes
to .tools/reviews/ so the critiques can be quoted verbatim rather than paraphrased.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from keel.api import Client  # noqa: E402

CONTEXT_FILES = [
    "README.md",
    "docs/STATUS.md",
    "docs/METHOD.md",
    "src/keel/stats.py",
    "src/keel/format.py",
    "src/keel/policy.py",
    "src/keel/sign.py",
]

PERSONAS = {
    "statistician": (
        "You are a hostile applied statistician reviewing a safety measurement tool. "
        "Attack the methodology: sample size, judge variance, multiple comparisons, "
        "bootstrap, the replay tolerance, and any claim the data cannot support. Cite the "
        "text you are attacking. Be specific and blunt."
    ),
    "redteam": (
        "You are a red-team reviewer. Find ways to defeat this tool: forge a card, pass a "
        "harmful checkpoint, bypass policy, abuse the public endpoints, leak withheld data, "
        "or exhaust the budget. Give concrete steps, not abstractions."
    ),
    "judge": (
        "You are a skeptical hackathon judge with ten minutes and a technical background. "
        "Say what is unconvincing, what you would ask in Q&A, and which claims lack "
        "evidence. Rank the three weakest points."
    ),
    "breakit": (
        "You are an engineer told to break this in an afternoon. Produce a numbered list of "
        "attacks with the exact request or command, the expected failure, and how to detect "
        "it. Prioritise attacks that produce a false PASS or an unearned REVIEW."
    ),
}


def _context() -> str:
    parts = [
        "Project: Keel, a checkpoint validity harness for open-weight models.",
        "Repo: https://github.com/TCPCore/keel",
        "Demo: https://tomscot-keel.hf.space",
        "Video: https://youtu.be/FvseA22YEDo",
        "",
    ]
    for name in CONTEXT_FILES:
        path = ROOT / name
        if path.exists():
            parts.append(f"===== {name} =====\n{path.read_text()[:12000]}")
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="meta-models/muse-spark-open-1026")
    parser.add_argument("--out", default=".tools/reviews")
    args = parser.parse_args()

    key = os.environ.get("BASETEN_API_KEY")
    if not key:
        print("BASETEN_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(
        api_key=key,
        base_url=os.environ.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
        model=args.model,
    )
    context = _context()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    for name, persona in PERSONAS.items():
        print("asking", name, flush=True)
        completion = client.chat(
            [
                {"role": "system", "content": persona},
                {
                    "role": "user",
                    "content": (
                        f"{context}\n\n"
                        "Review the project above. Do not be polite. List flaws, attacks and "
                        "unsupported claims, each with the specific file or number it refers "
                        "to. If something is genuinely strong, say so once."
                    ),
                },
            ],
            max_tokens=1800,
            extra={"reasoning_effort": "low"},
        )
        (out / f"{name}.md").write_text(completion.text.strip() + "\n")
        print("  wrote", name, len(completion.text), "chars", flush=True)
    (out / "context.txt").write_text(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
