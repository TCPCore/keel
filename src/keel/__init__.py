"""Keel — checkpoint-level misalignment drift detection for open-weight models.

Submodules are imported lazily on purpose: ``keel --version`` should not pay for
numpy, and a partially-built tree should still be importable.

    from keel.drift import compute_drift
    from keel.panel import builtin
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
