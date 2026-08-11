#!/usr/bin/env python3
"""Render the README score/cost Pareto chart from canonical cost estimates."""

from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path


PORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PORT_DIR.parent
DEFAULT_README = REPO_ROOT / "README.md"
DEFAULT_COSTS = PORT_DIR / "leaderboards/leaderboard-natural-costs.json"
DEFAULT_OUTPUT = PORT_DIR / "leaderboards/assets/score-cost-pareto.svg"


@dataclass(frozen=True)
class Point:
    label: str
    score: int
    task_complete_rate: float
    cost_per_complete: float
    turn_p50_ms: float = 0.0
    provider: str = ""


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def load_points(readme_path: Path, costs_path: Path) -> list[Point]:
    """Join README scores to unrounded canonical cost estimates by model label."""

    report = json.loads(costs_path.read_text(encoding="utf-8"))
    estimates = {
        item["label"]: item
        for item in report["results"]
    }
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    try:
        header_index = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("| Model") and "Est. Cost / Complete" in line
        )
    except StopIteration as exc:
        raise ValueError(f"README leaderboard table not found in {readme_path}") from exc

    points: list[Point] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        cells = _table_cells(line)
        if len(cells) != 12:
            raise ValueError(f"unexpected README leaderboard row: {line}")
        label = cells[0]
        if cells[10] == "—" and label not in estimates:
            # Locally served rows without a public-API price do not belong on
            # the cost frontier, but should not make the renderer unusable.
            continue
        if label not in estimates:
            raise ValueError(f"no canonical cost estimate for README row {label!r}")
        estimate = estimates[label]
        cost = float(estimate["estimated_cost_per_completed_task"])
        expected_cost = _money(cost)
        if cells[10] != expected_cost:
            raise ValueError(
                f"README cost for {label!r} is {cells[10]}, expected {expected_cost}"
            )
        expected_provider = estimate["provider"]
        if cells[11] != expected_provider:
            raise ValueError(
                f"README provider for {label!r} is {cells[11]}, expected {expected_provider}"
            )
        points.append(
            Point(
                label=label,
                score=int(cells[1]),
                task_complete_rate=float(cells[2].rstrip("%")) / 100,
                cost_per_complete=cost,
                turn_p50_ms=float(cells[7]),
                provider=expected_provider,
            )
        )

    if not points:
        raise ValueError(f"README leaderboard table is empty in {readme_path}")
    return points


def pareto_frontier(points: list[Point]) -> list[Point]:
    """Return rows not dominated on lower cost and higher score."""

    frontier: list[Point] = []
    best_score = -math.inf
    for point in sorted(points, key=lambda item: (item.cost_per_complete, -item.score)):
        if point.score > best_score:
            frontier.append(point)
            best_score = point.score
    return frontier


def _money(value: float) -> str:
    if value >= 1:
        return f"${value:.2f}"
    return f"${value:.3f}"


def _short_label(label: str) -> str:
    replacements = {
        "gemini-3.6-flash (high)": "Gemini 3.6 Flash · high",
        "poolside/laguna-s-2.1 (none)": "Laguna S 2.1 · none",
        "gemma-4-31b (thinking)": "Gemma 4 31B · thinking",
        "kimi-2.6 Cerebras (thinking)": "Kimi 2.6 · thinking",
        "glm-5.2 (max)": "GLM 5.2 · max",
        "claude-sonnet-5 (xhigh)": "Claude Sonnet 5 · xhigh",
        "gpt-5.6-terra (xhigh)": "GPT-5.6 Terra · xhigh",
    }
    return replacements.get(label, label)


def render_svg(points: list[Point]) -> str:
    width, height = 1000, 660
    left, right, top, bottom = 92, 34, 86, 78
    plot_width = width - left - right
    plot_height = height - top - bottom
    min_cost, max_cost = 0.01, 1.0
    min_score, max_score = 80, 100
    x_ticks = [0.01, 0.03, 0.1, 0.3, 1.0]
    y_ticks = [80, 85, 90, 95, 100]
    frontier = pareto_frontier(points)
    frontier_labels = {point.label for point in frontier}
    notable_labels = {
        "gemini-3.6-flash (high)",
        "claude-sonnet-5 (xhigh)",
        "gpt-5.6-terra (xhigh)",
    }

    def x(value: float) -> float:
        span = math.log10(max_cost) - math.log10(min_cost)
        return left + (math.log10(value) - math.log10(min_cost)) / span * plot_width

    def y(value: float) -> float:
        return top + (max_score - value) / (max_score - min_score) * plot_height

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Score versus estimated cost per completed port-to-port task</title>',
        '  <desc id="desc">A logarithmic scatter plot of the best under-four-second configuration for each model. Laguna S 2.1, Gemma 4 31B, Kimi 2.6, and GLM 5.2 form the efficient frontier.</desc>',
        "  <style>",
        "    text { font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #24211f; }",
        "    .title { font-family: Georgia, 'Times New Roman', serif; font-size: 24px; }",
        "    .subtitle, .tick, .axis-label, .point-detail { fill: #6e6965; }",
        "    .subtitle { font-size: 13px; }",
        "    .tick { font-size: 12px; }",
        "    .axis-label { font-size: 13px; }",
        "    .grid { stroke: #dedbd7; stroke-width: 1; }",
        "    .axis { stroke: #8f8983; stroke-width: 1; }",
        "    .other { fill: #b9b5b0; fill-opacity: .72; }",
        "    .notable { fill: #625d59; fill-opacity: .9; }",
        "    .frontier-line { fill: none; stroke: #a23b2a; stroke-width: 2; }",
        "    .frontier { fill: #a23b2a; stroke: #fff; stroke-width: 1.5; }",
        "    .point-label { font-size: 13px; font-weight: 600; }",
        "    .notable-label { font-size: 12px; font-weight: 600; fill: #4f4a46; }",
        "    .point-detail { font-size: 12px; font-weight: 400; }",
        "  </style>",
        f'  <text class="title" x="{left}" y="31">Score versus cost per completed task</text>',
        f'  <text class="subtitle" x="{left}" y="55">Best configuration under 4 seconds per turn · logarithmic cost axis · efficient frontier in red</text>',
    ]

    for tick in y_ticks:
        py = y(tick)
        lines.extend(
            [
                f'  <line class="grid" x1="{left}" y1="{py:.1f}" x2="{width - right}" y2="{py:.1f}"/>',
                f'  <text class="tick" x="{left - 13}" y="{py + 4:.1f}" text-anchor="end">{tick}</text>',
            ]
        )
    for tick in x_ticks:
        px = x(tick)
        label = f"${tick:.2f}" if tick < 1 else f"${tick:.0f}"
        lines.extend(
            [
                f'  <line class="axis" x1="{px:.1f}" y1="{height - bottom}" x2="{px:.1f}" y2="{height - bottom + 5}"/>',
                f'  <text class="tick" x="{px:.1f}" y="{height - bottom + 23}" text-anchor="middle">{label}</text>',
            ]
        )

    lines.extend(
        [
            f'  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"/>',
            f'  <text class="axis-label" x="{left + plot_width / 2:.1f}" y="{height - 25}" text-anchor="middle">Estimated cost per completed task (USD)</text>',
            f'  <text class="axis-label" transform="translate(25 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">Official judge score</text>',
        ]
    )

    path = " ".join(
        f"{'M' if index == 0 else 'L'} {x(point.cost_per_complete):.1f} {y(point.score):.1f}"
        for index, point in enumerate(frontier)
    )
    lines.append(f'  <path class="frontier-line" d="{path}"/>')

    for point in points:
        if point.label in frontier_labels:
            continue
        point_class = "notable" if point.label in notable_labels else "other"
        lines.append(
            f'  <circle class="{point_class}" cx="{x(point.cost_per_complete):.1f}" '
            f'cy="{y(point.score):.1f}" r="4"><title>{html.escape(point.label)}: '
            f'{point.score}, {_money(point.cost_per_complete)} per completed task</title></circle>'
        )

    label_offsets = {
        "poolside/laguna-s-2.1 (none)": (13, 31),
        "gemma-4-31b (thinking)": (13, 37),
        "kimi-2.6 Cerebras (thinking)": (13, -35),
        "glm-5.2 (max)": (13, -35),
    }
    for point in frontier:
        px, py = x(point.cost_per_complete), y(point.score)
        dx, dy = label_offsets.get(point.label, (12, -18))
        label = html.escape(_short_label(point.label))
        detail = f"{point.score} · {_money(point.cost_per_complete)}"
        lines.extend(
            [
                f'  <circle class="frontier" cx="{px:.1f}" cy="{py:.1f}" r="5.5"><title>{html.escape(point.label)}: {point.score}, {_money(point.cost_per_complete)} per completed task</title></circle>',
                f'  <text class="point-label" x="{px + dx:.1f}" y="{py + dy:.1f}">{label}'
                f'<tspan class="point-detail" x="{px + dx:.1f}" dy="16">{detail}</tspan></text>',
            ]
        )

    notable_offsets = {
        "gemini-3.6-flash (high)": (-13, 31, "end"),
        "claude-sonnet-5 (xhigh)": (13, -20, "start"),
        "gpt-5.6-terra (xhigh)": (13, 52, "start"),
    }
    for point in points:
        if point.label not in notable_labels:
            continue
        px, py = x(point.cost_per_complete), y(point.score)
        dx, dy, anchor = notable_offsets[point.label]
        label_x = px + dx
        label = html.escape(_short_label(point.label))
        detail = f"{point.score} · {_money(point.cost_per_complete)}"
        lines.append(
            f'  <text class="notable-label" x="{label_x:.1f}" y="{py + dy:.1f}" text-anchor="{anchor}">{label}'
            f'<tspan class="point-detail" x="{label_x:.1f}" dy="15">{detail}</tspan></text>'
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--costs", type=Path, default=DEFAULT_COSTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the existing SVG differs from freshly rendered output",
    )
    parser.add_argument(
        "--print-frontier",
        action="store_true",
        help="print the computed frontier as tab-separated rows",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    points = load_points(args.readme.resolve(), args.costs.resolve())
    rendered = render_svg(points)
    output = args.output.resolve()

    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{output} is stale; rerun {Path(__file__).name}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")

    if args.print_frontier:
        for point in pareto_frontier(points):
            print(
                f"{point.label}\t{point.score}\t"
                f"{point.task_complete_rate * 100:.1f}%\t{_money(point.cost_per_complete)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
