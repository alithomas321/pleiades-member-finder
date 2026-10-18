"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from gaia_pleiades.pipeline import run_pipeline, verify_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gaia-pleiades",
        description="Find and validate Pleiades kinematic candidates in Gaia DR3.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run the complete analysis pipeline")
    run.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Checkout/output root (default: current directory)",
    )
    run.add_argument(
        "--refresh-data",
        action="store_true",
        help="Requery Gaia and VizieR instead of using committed snapshots",
    )

    verify = subparsers.add_parser("verify", help="Verify cached data and scientific outputs")
    verify.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Checkout/output root (default: current directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        result = run_pipeline(args.project_root, refresh_data=args.refresh_data)
    else:
        result = verify_artifacts(args.project_root)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
