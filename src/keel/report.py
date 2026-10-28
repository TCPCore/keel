"""Render a drift card.

The card is the product surface. JSON is the stable interface; Markdown is
what a human reads; text is what a terminal prints. All three are generated
from the same object so they cannot drift apart.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .attribution import AttributionResult, Unit, layer_histogram
from .drift import AXES, AXIS_LABELS, DriftVector, Verdict

DEFAULT_LIMITS: tuple[str, ...] = (
    "probes are not exhaustive; absence of drift on this panel is not safety",
    "coherent misalignment is not detected: probes find conflict, not values",
    "a unit is a coordinate that moves the score, not a concept in the model",
    "layers and units are subsampled; anything outside the sample is invisible",
)


def bar(z: float, width: int = 10) -> str:
    """A crude magnitude bar; 3 sigma fills it."""
    fraction = min(max(z, 0.0) / 3.0, 1.0)
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled)


def _signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}"


@dataclass
class Card:
    drift: DriftVector
    attribution: AttributionResult | None = None
    gpu_usd: float | None = None
    tokens_usd: float | None = None
    seconds: float | None = None
    limits: Sequence[str] = DEFAULT_LIMITS
    demo: bool = False
    validity: str = "ok"  # "ok" | "suspect"
    validity_reason: str = ""
    harmful: dict | None = None
    structure: dict | None = None
    require_harmful: bool = False

    def fingerprint(self) -> str:
        """A stable identity for the card's contents, for tickets and registries."""
        payload = {
            "drift": self.drift.to_dict(),
            "validity": self.validity,
            "harmful": self.harmful,
            "structure": self.structure,
        }
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    @property
    def verdict(self) -> Verdict:
        drift_verdict = self.drift.verdict()
        # Format is a validity gate, not an axis: a suspect measurement must
        # not report "no drift", so green becomes amber. Red stays red — the
        # gate can only ever escalate, never downgrade.
        if self.validity == "suspect" and drift_verdict.level == "green":
            reason = self.validity_reason or "suspect response-format shift"
            return Verdict("amber", (reason, *drift_verdict.reasons))
        # A green card without the harmful half is an overclaim: the panel can show
        # no drift while refusal behaviour on harmful requests is unmeasured.
        if (
            self.require_harmful
            and self.harmful is None
            and drift_verdict.level == "green"
        ):
            return Verdict(
                "amber",
                (
                    "harmful half not measured; refusal behaviour is unverified",
                    *drift_verdict.reasons,
                ),
            )
        return drift_verdict

    def to_dict(self) -> dict:
        return {
            "schema_version": 2,
            "demo": self.demo,
            "drift": self.drift.to_dict(),
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "cost": {
                "gpu_usd": self.gpu_usd,
                "tokens_usd": self.tokens_usd,
                "seconds": self.seconds,
            },
            "limits": list(self.limits),
            "validity": self.validity,
            "validity_reason": self.validity_reason,
            "harmful": self.harmful,
            "structure": self.structure,
            "require_harmful": self.require_harmful,
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Card:
        drift = DriftVector.from_dict(data.get("drift", {}))
        attribution = None
        payload = data.get("attribution")
        if payload:
            units = [Unit.parse(key) for key in payload.get("units", [])]
            from .attribution import Selection

            selection = Selection(
                units=units,
                curve=[float(x) for x in payload.get("curve", [])],
                evaluations=int(payload.get("evaluations", 0)),
            )
            attribution = AttributionResult(
                selection=selection,
                baseline=float(payload.get("baseline", 0.0)),
                final=float(payload.get("final", 0.0)),
                null_mean=float(payload.get("null_mean", 0.0)),
                null_sd=float(payload.get("null_sd", 0.0)),
                sufficiency=payload.get("sufficiency"),
                screened=int(payload.get("screened", 0)),
            )
        cost = data.get("cost", {})
        return cls(
            drift=drift,
            attribution=attribution,
            gpu_usd=cost.get("gpu_usd"),
            tokens_usd=cost.get("tokens_usd"),
            seconds=cost.get("seconds"),
            limits=tuple(data.get("limits", DEFAULT_LIMITS)),
            demo=bool(data.get("demo", False)),
            validity=str(data.get("validity", "ok")),
            validity_reason=str(data.get("validity_reason", "")),
            harmful=data.get("harmful"),
            structure=data.get("structure"),
            require_harmful=bool(data.get("require_harmful", False)),
        )

    def cost_line(self) -> str:
        parts = []
        if self.gpu_usd is not None:
            parts.append(f"${self.gpu_usd:.2f} GPU")
        if self.tokens_usd is not None:
            parts.append(f"${self.tokens_usd:.2f} tokens")
        if self.seconds is not None:
            parts.append(f"{self.seconds:.0f} s")
        return " · ".join(parts) if parts else "not recorded"


def _attribution_block(attribution: AttributionResult) -> list[str]:
    units = attribution.selection.units
    hist = layer_histogram(units)
    if hist:
        layers = sorted(hist)
        where = f"L{layers[0]:02d}" if len(layers) == 1 else f"L{layers[0]:02d}–L{layers[-1]:02d}"
    else:
        where = "no units"
    specificity = attribution.specificity
    spec = "∞" if specificity == float("inf") else f"{specificity:.1f}×"
    lines = [
        f"**{attribution.selection.size} units** in {where} · "
        f"{attribution.reduction_fraction:.0%} of drift removed · "
        f"random null {attribution.null_mean / attribution.baseline:.0%} · "
        f"specificity {spec}",
        "",
        f"- baseline {attribution.baseline:.2f}σ → after ablation {attribution.final:.2f}σ "
        f"({attribution.selection.evaluations} evaluations)",
    ]
    if attribution.sufficiency is not None:
        lines.append(f"- sufficiency: injecting the set into the reference reaches "
                     f"{attribution.sufficiency:.2f}σ")
    per_layer = ", ".join(f"L{layer}:{count}" for layer, count in hist.items())
    if per_layer:
        lines.append(f"- by layer: {per_layer}")
    return lines


def render_markdown(card: Card) -> str:
    drift = card.drift
    verdict = card.verdict
    lines: list[str] = ["# Keel drift card", ""]
    if card.demo:
        lines += [
            "> **SYNTHETIC DEMO** — generated from bundled demo data, not a measurement.",
            "",
        ]
    lines += [
        f"**Verdict: `{verdict.level.upper()}`**",
        "",
        f"candidate `{drift.candidate_id or 'unknown'}` · "
        f"reference `{drift.reference_id or 'unknown'}` · "
        f"panel `{drift.panel_hash or 'unknown'}` · {drift.n_probes} probes",
        "",
    ]
    if card.validity == "suspect":
        lines += [
            f"> **MEASUREMENT SUSPECT** — {card.validity_reason or 'response format shifted'}. "
            "The behavioural axes are scoring different responders, so treat the levels "
            "as unreliable until the format is fixed.",
            "",
        ]
    if verdict.reasons:
        lines += [f"- {reason}" for reason in verdict.reasons]
        lines.append("")

    lines += [
        "## Axes",
        "",
        "| axis | ref | cand | Δ | z | 95% CI | q | |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for axis in AXES:
        score = drift.axes.get(axis)
        if score is None:
            continue
        lines.append(
            f"| {AXIS_LABELS[axis]} | {score.reference:.2f} | {score.candidate:.2f} | "
            f"{_signed(score.delta)} | {_signed(score.z, 1)}σ | "
            f"[{_signed(score.ci_low)}, {_signed(score.ci_high)}] | "
            f"{score.q_value:.3f} | {bar(score.z)} |"
        )
    lines.append("")
    lines.append(f"magnitude **{drift.magnitude:.2f}σ** (RMS of positive z-scores)")
    if drift.axes:
        resolvable = [score.resolvable for score in drift.axes.values()]
        lines.append(
            f"resolvable at 80% power: **{min(resolvable):.2f}–{max(resolvable):.2f}** "
            "axis points per axis"
        )
    if drift.internal is not None:
        lines.append(f"internal: cosine to misalignment direction **{drift.internal:+.2f}**")
    lines.append("")

    if card.attribution:
        lines += ["## Attribution", ""]
        lines += _attribution_block(card.attribution)
        lines.append("")

    if card.harmful:
        lines += ["## Harmful half", ""]
        lines += _harmful_block(card.harmful)
        lines.append("")
    if card.structure:
        lines += ["## Structure", ""]
        lines += _structure_block(card.structure)
        lines.append("")

    lines += ["## Cost", "", card.cost_line(), ""]
    lines += ["## Limits", ""]
    lines += [f"- {limit}" for limit in card.limits]
    lines += ["", "---", "", "Generated by Keel. Exit codes: 0 green, 1 amber, 2 red.", ""]
    return "\n".join(lines)


def render_text(card: Card) -> str:
    drift = card.drift
    verdict = card.verdict
    lines = [
        "KEEL DRIFT CARD" + ("  [SYNTHETIC DEMO]" if card.demo else ""),
        f"  candidate {drift.candidate_id or 'unknown'}",
        f"  reference {drift.reference_id or 'unknown'}",
        f"  panel     {drift.panel_hash or 'unknown'}  ({drift.n_probes} probes)",
        "",
        f"  VERDICT   {verdict.level.upper()}",
    ]
    lines += [f"            {reason}" for reason in verdict.reasons]
    if card.validity == "suspect":
        lines.append(f"  SUSPECT   {card.validity_reason or 'response format shifted'}")
    lines.append("")
    for axis in AXES:
        score = drift.axes.get(axis)
        if score is None:
            continue
        lines.append(
            f"  {AXIS_LABELS[axis]:<16} {score.reference:.2f} -> {score.candidate:.2f}  "
            f"{_signed(score.z, 1)}σ  q={score.q_value:.3f}  {bar(score.z)}"
        )
    lines.append("")
    if card.attribution:
        lines.append(f"  ATTRIBUTION  {card.attribution.selection.size} units, "
                     f"{card.attribution.reduction_fraction:.0%} of drift removed")
    if card.harmful:
        ref = card.harmful.get("reference_rate")
        cand = card.harmful.get("candidate_rate")
        if ref is not None and cand is not None:
            lines.append(
                f"  HARMFUL      compliance {float(ref):.2f} -> {float(cand):.2f}"
            )
    if card.structure:
        ratio = card.structure.get("rank1_ratio_median")
        cos = card.structure.get("cos_hidden")
        if ratio is not None:
            lines.append(f"  STRUCTURE    rank-1 ratio {ratio}  cos {cos}")
    lines.append(f"  COST         {card.cost_line()}")
    return "\n".join(lines)


def _harmful_block(payload: dict) -> list[str]:
    ref = payload.get("reference_rate")
    cand = payload.get("candidate_rate")
    delta = payload.get("delta")
    ci = payload.get("ci") or [None, None]
    p_value = payload.get("p")
    parts = []
    if ref is not None and cand is not None:
        parts.append(f"- compliance `{float(ref):.2f}` → `{float(cand):.2f}`")
    if delta is not None:
        parts.append(f"- delta `{float(delta):+.2f}`")
    if ci[0] is not None:
        parts.append(f"- 95% CI `[{float(ci[0]):+.2f}, {float(ci[1]):+.2f}]`")
    if p_value is not None:
        parts.append(f"- p `{float(p_value):.4f}`")
    return parts or ["- no harmful summary recorded"]


def _structure_block(payload: dict) -> list[str]:
    parts = []
    for key in ("method", "rank1_ratio_median", "cos_hidden", "layers", "note"):
        value = payload.get(key)
        if value is not None:
            parts.append(f"- {key.replace('_', ' ')}: `{value}`")
    return parts or ["- no structural summary recorded"]


def render_json(card: Card) -> str:
    return json.dumps(card.to_dict(), indent=2, sort_keys=False)


def render_comparison(before: Card, after: Card) -> str:
    """Compare two existing cards. No model call, no cost, exit code of `after`."""
    lines = [
        "# Keel comparison",
        "",
        f"A  `{before.drift.candidate_id or 'unknown'}`  →  "
        f"`{before.verdict.level.upper()}`",
        f"B  `{after.drift.candidate_id or 'unknown'}`  →  "
        f"`{after.verdict.level.upper()}`",
        "",
        "| axis | A | B | Δ (B−A) | z | resolvable |",
        "|---|---|---|---|---|---|",
    ]
    for axis in AXES:
        a = before.drift.axes.get(axis)
        b = after.drift.axes.get(axis)
        if a is None or b is None:
            continue
        delta = b.candidate - a.candidate
        lines.append(
            f"| {AXIS_LABELS[axis]} | {a.candidate:.2f} | {b.candidate:.2f} | "
            f"{_signed(delta)} | {_signed(b.z, 1)}σ | {b.resolvable:.2f} |"
        )
    lines += ["", f"magnitude A {before.drift.magnitude:.2f}σ → B {after.drift.magnitude:.2f}σ", ""]
    return "\n".join(lines)


def write_card(card: Card, directory: str | Path, stem: str = "drift-card") -> tuple[Path, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    md = directory / f"{stem}.md"
    js = directory / f"{stem}.json"
    md.write_text(render_markdown(card), encoding="utf-8")
    js.write_text(render_json(card) + "\n", encoding="utf-8")
    return md, js
