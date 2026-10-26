"""Command line interface.

Exit codes are the CI contract: 0 green, 1 amber, 2 red, 3 unsupported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .panel import builtin, load_panel, panel_hash, validate
from .report import Card, render_comparison, render_text, write_card
from .synth import run_demo

GREEN, AMBER, RED, UNSUPPORTED = 0, 1, 2, 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keel",
        description="Checkpoint-level misalignment drift detection for open-weight models.",
    )
    parser.add_argument("--version", action="version", version=f"keel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the synthetic scan (no GPU, no API key)")
    demo.add_argument("--out", default="examples", help="directory for the card")
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument(
        "--strict",
        action="store_true",
        help="exit with the verdict code instead of 0",
    )
    demo.set_defaults(func=cmd_demo)

    scan = sub.add_parser("scan", help="scan a checkpoint against a reference")
    scan.add_argument("--candidate", help="candidate checkpoint path or id")
    scan.add_argument("--reference", help="reference checkpoint path or id")
    scan.add_argument("--panel", default="v0.1", help="panel version or path")
    scan.add_argument("--out", default="cards", help="directory for the card")
    scan.add_argument("--seed", type=int, default=7)
    scan.add_argument("--demo", action="store_true", help="use synthetic data")
    scan.add_argument(
        "--from-card",
        action="append",
        metavar="CARD",
        help="compare two existing cards; no model call, no cost",
    )
    scan.add_argument("--strict", action="store_true", help="exit with the verdict code")
    scan.set_defaults(func=cmd_scan, demo_out="examples")

    job = sub.add_parser(
        "job",
        help="run a checkpoint job (white-box: load, probe, capture, attribute)",
    )
    job.add_argument("checkpoint")
    job.add_argument("--reference")
    job.add_argument("--panel", default="v0.2")
    job.add_argument("--out", default="cards")
    job.set_defaults(func=cmd_job)

    panel = sub.add_parser("panel", help="inspect or validate a probe panel")
    panel_sub = panel.add_subparsers(dest="panel_command", required=True)
    panel_list = panel_sub.add_parser("list", help="list the built-in panel")
    panel_list.add_argument("--version", default="v0.1")
    panel_list.set_defaults(func=cmd_panel_list)
    panel_validate = panel_sub.add_parser("validate", help="validate a panel file")
    panel_validate.add_argument("path")
    panel_validate.set_defaults(func=cmd_panel_validate)

    return parser


def cmd_demo(args: argparse.Namespace) -> int:
    result = run_demo(seed=args.seed)
    card = result.card
    out = getattr(args, "out", "examples")
    md, js = write_card(card, out)
    print(render_text(card))
    print()
    print(f"precision {result.precision:.0%} against the planted unit set")
    print(f"wrote {md}")
    print(f"wrote {js}")
    return card.verdict.exit_code if getattr(args, "strict", False) else GREEN


def cmd_scan(args: argparse.Namespace) -> int:
    if args.from_card:
        return cmd_compare(args)
    if args.demo:
        args.out = getattr(args, "demo_out", "examples")
        return cmd_demo(args)
    if not args.candidate or not args.reference:
        print(
            "keel scan: --candidate and --reference are required (or use --demo)",
            file=sys.stderr,
        )
        return UNSUPPORTED
    print(
        "keel scan: the weights path is the checkpoint job — run `keel job ./ckpt`. "
        "It is not implemented in v0.1; see docs/COMPUTE.md. Use --demo for the "
        "synthetic run, or --from-card to compare existing cards.",
        file=sys.stderr,
    )
    return UNSUPPORTED


def cmd_compare(args: argparse.Namespace) -> int:
    if len(args.from_card) != 2:
        print("keel scan --from-card needs exactly two cards", file=sys.stderr)
        return UNSUPPORTED
    try:
        cards = [
            Card.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
            for path in args.from_card
        ]
    except (OSError, ValueError, KeyError) as exc:
        print(f"keel scan --from-card: {exc}", file=sys.stderr)
        return UNSUPPORTED
    print(render_comparison(cards[0], cards[1]))
    return cards[1].verdict.exit_code


def cmd_job(args: argparse.Namespace) -> int:
    print(
        "keel job: the checkpoint job (load -> panel -> residuals -> attribution -> card) "
        "is the white-box path and runs as a container on Baseten Training Jobs, not as "
        "an API call. Not implemented in v0.1; see docs/COMPUTE.md and docs/METHOD.md.",
        file=sys.stderr,
    )
    return UNSUPPORTED


def cmd_panel_list(args: argparse.Namespace) -> int:
    probes = builtin(args.version)
    print(f"panel {args.version}  {panel_hash(probes)}  {len(probes)} probes")
    for probe in probes:
        print(f"  {probe.id:<5} {probe.axis:<16} {probe.scorer:<13} {probe.text[:64]}")
    return GREEN


def cmd_panel_validate(args: argparse.Namespace) -> int:
    try:
        probes = load_panel(Path(args.path))
    except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
        print(f"invalid: {exc}", file=sys.stderr)
        return RED
    errors = validate(probes)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return RED
    print(f"ok: {len(probes)} probes, hash {panel_hash(probes)}")
    return GREEN


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
