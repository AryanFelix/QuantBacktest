"""Compatibility entry point for the measured L500-v2 dependency audit."""

from __future__ import annotations

import argparse

from audit_l500_v2_dependencies import audit, self_check


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else audit()
