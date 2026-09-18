"""Command-line entrypoint for the capacity planner.

Usage
-----
    python -m planner plan --config examples/500_cameras_20_sites.yaml --out report.html

The YAML config may contain a single scenario at the top level, and
optionally a `variants` list of `{name, overrides}` entries describing
additional what-if scenarios to compute and include in the comparison
chart/table of the generated report.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .calculator import ScenarioResult, run_scenario
from .report import write_report


def load_config(config_path: str | Path) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_all_scenarios(config: dict[str, Any]) -> list[ScenarioResult]:
    """Compute the primary scenario plus any declared variants."""
    base = {k: v for k, v in config.items() if k != "variants"}
    results = [run_scenario(base)]

    for variant in config.get("variants", []) or []:
        merged = copy.deepcopy(base)
        merged.update(variant.get("overrides", {}))
        merged["name"] = variant.get("name", merged.get("name", "Variant"))
        results.append(run_scenario(merged))

    return results


def _cmd_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    results = run_all_scenarios(config)

    out_path = write_report(results, args.out)
    print(f"Wrote report: {out_path}")

    if args.json:
        summary = [r.to_dict() for r in results]
        print(json.dumps(summary, indent=2, default=str))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planner",
        description="Video infrastructure capacity-planning calculator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Compute a capacity plan and write an HTML report")
    plan_parser.add_argument("--config", required=True, help="Path to a scenario YAML config file")
    plan_parser.add_argument("--out", default="report.html", help="Path to write the HTML report to")
    plan_parser.add_argument("--json", action="store_true", help="Also print computed results as JSON")
    plan_parser.set_defaults(func=_cmd_plan)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
