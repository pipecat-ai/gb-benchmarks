#!/usr/bin/env python3
"""Render the README score/turn-completion-time frontier chart."""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

from render_readme_pareto import (
    DEFAULT_COSTS,
    DEFAULT_README,
    LabelGeometry,
    Point,
    _label_geometry,
    _label_hairline,
    _money,
    _validate_label_layout,
    load_points,
    pareto_frontier,
)


PORT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PORT_DIR / "leaderboards/assets/score-time-frontier.svg"


def time_frontier(points: list[Point]) -> list[Point]:
    """Return rows not dominated on lower median turn time and higher score."""

    frontier: list[Point] = []
    best_score = -math.inf
    for point in sorted(points, key=lambda item: (item.turn_p50_ms, -item.score)):
        if point.score > best_score:
            frontier.append(point)
            best_score = point.score
    return frontier


def _short_label(label: str) -> str:
    replacements = {
        "gemini-3.5-flash-lite (high)": "Gemini 3.5 Flash Lite · high",
        "gemini-3.7-flash (high)": "Gemini 3.7 Flash · high",
        "grok-4.6 (high)": "Grok 4.6 · high",
        "grok-4.6 (low)": "Grok 4.6 · low",
        "gemini-3.6-flash (high)": "Gemini 3.6 Flash · high",
        "poolside/laguna-s-2.1 (none)": "Laguna S 2.1 · none",
        "gemma-4-31b (thinking)": "Gemma 4 31B · thinking",
        "kimi-2.6 (thinking)": "Kimi 2.6 · thinking",
        "deepseek-v4-flash-0731 (low)": "DeepSeek V4 Flash · low",
        "glm-5.2 (max)": "GLM 5.2 · max",
        "claude-sonnet-5 (xhigh)": "Claude Sonnet 5 · xhigh",
        "gpt-5.6-terra (xhigh)": "GPT-5.6 Terra · xhigh",
    }
    return replacements.get(label, label)


def render_svg(points: list[Point]) -> str:
    width, height = 1000, 620
    left, right, top, bottom = 92, 34, 86, 72
    plot_width = width - left - right
    plot_height = height - top - bottom
    min_time, max_time = 0.0, 4000.0
    min_score, max_score = 80, 100
    x_ticks = [0, 1000, 2000, 3000, 4000]
    y_ticks = [80, 85, 90, 95, 100]
    frontier = time_frontier(points)
    frontier_labels = {point.label for point in frontier}
    cost_frontier_labels = {point.label for point in pareto_frontier(points)}
    prominent_family_labels = {
        "gemini-3.7-flash (high)",
        "claude-sonnet-5 (xhigh)",
        "gpt-5.6-terra (xhigh)",
    }
    notable_labels = (cost_frontier_labels | prominent_family_labels) - frontier_labels
    label_geometries: list[LabelGeometry] = []

    def x(value: float) -> float:
        return left + (value - min_time) / (max_time - min_time) * plot_width

    def y(value: float) -> float:
        return top + (max_score - value) / (max_score - min_score) * plot_height

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Official judge score versus turn completion time</title>',
        '  <desc id="desc">A scatter plot of the curated under-four-second models. Turn completion time measures the full model response or tool call, not time to first token. The red path marks configurations not dominated on lower median turn completion time and higher score.</desc>',
        "  <style>",
        "    text { font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #24211f; }",
        "    .title { font-family: Georgia, 'Times New Roman', serif; font-size: 24px; }",
        "    .subtitle, .tick, .axis-label, .point-detail { fill: #6e6965; }",
        "    .subtitle { font-size: 13px; }",
        "    .tick { font-size: 12px; }",
        "    .axis-label { font-size: 13px; }",
        "    .grid { stroke: #dedbd7; stroke-width: 1; }",
        "    .axis { stroke: #8f8983; stroke-width: 1; }",
        "    .cutoff { stroke: #8f8983; stroke-width: 1; stroke-dasharray: 5 5; }",
        "    .other { fill: #b9b5b0; fill-opacity: .72; }",
        "    .notable { fill: #625d59; fill-opacity: .9; }",
        "    .frontier-line { fill: none; stroke: #a23b2a; stroke-width: 2; }",
        "    .label-hairline { stroke: #aaa49e; stroke-width: .65; }",
        "    .frontier { fill: #a23b2a; stroke: #fff; stroke-width: 1.5; }",
        "    .point-label { font-size: 13px; font-weight: 600; }",
        "    .notable-label { font-size: 12px; font-weight: 600; fill: #4f4a46; }",
        "    .point-detail { font-size: 12px; font-weight: 400; }",
        "  </style>",
        f'  <text class="title" x="{left}" y="31">Score versus turn completion time</text>',
        f'  <text class="subtitle" x="{left}" y="55">Turn P50: full response or tool call · upper left is better · frontier in red</text>',
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
        lines.extend(
            [
                f'  <line class="axis" x1="{px:.1f}" y1="{height - bottom}" x2="{px:.1f}" y2="{height - bottom + 5}"/>',
                f'  <text class="tick" x="{px:.1f}" y="{height - bottom + 23}" text-anchor="middle">{tick / 1000:.0f}s</text>',
            ]
        )

    cutoff_x = x(4000)
    lines.extend(
        [
            f'  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"/>',
            f'  <line class="cutoff" x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{height - bottom}"/>',
            f'  <text class="axis-label" x="{left + plot_width / 2:.1f}" y="{height - 21}" text-anchor="middle">Turn P50 completion time</text>',
            f'  <text class="axis-label" transform="translate(25 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">Official judge score</text>',
        ]
    )

    path = " ".join(
        f"{'M' if index == 0 else 'L'} {x(point.turn_p50_ms):.1f} {y(point.score):.1f}"
        for index, point in enumerate(frontier)
    )
    lines.append(f'  <path class="frontier-line" d="{path}"/>')

    for point in points:
        if point.label in frontier_labels:
            continue
        point_class = "notable" if point.label in notable_labels else "other"
        lines.append(
            f'  <circle class="{point_class}" cx="{x(point.turn_p50_ms):.1f}" '
            f'cy="{y(point.score):.1f}" r="4"><title>{html.escape(point.label)}: '
            f'{point.score:g}, {point.turn_p50_ms / 1000:.2f}s median turn time</title></circle>'
        )

    label_offsets = {
        "grok-4.6 (high)": (8, 28, "start"),
        "inkling (low)": (-8, -34, "end"),
        "gemini-3.5-flash-lite (high)": (-12, -38, "end"),
        "poolside/laguna-s-2.1 (none)": (-136, -32, "start"),
        "gemma-4-31b (thinking)": (-4, -52, "end"),
        "kimi-2.6 (thinking)": (-8, -34, "end"),
        "deepseek-v4-flash-0731 (low)": (-12, -45, "end"),
    }
    for point in frontier:
        px, py = x(point.turn_p50_ms), y(point.score)
        dx, dy, anchor = label_offsets.get(point.label, (12, -18, "start"))
        label_x = px + dx
        label = html.escape(_short_label(point.label))
        detail = (
            f"{point.score:g} · {point.turn_p50_ms / 1000:.2f}s · "
            f"{_money(point.cost_per_complete)}"
        )
        geometry = _label_geometry(
            model_label=point.label,
            point_x=px,
            point_y=py,
            point_radius=5.5,
            label_x=label_x,
            label_baseline=py + dy,
            anchor=anchor,
            label=_short_label(point.label),
            detail=detail,
            notable=False,
        )
        label_geometries.append(geometry)
        lines.extend(
            [
                _label_hairline(geometry),
                f'  <circle class="frontier" cx="{px:.1f}" cy="{py:.1f}" r="5.5"><title>{html.escape(point.label)}: {point.score:g}, {point.turn_p50_ms / 1000:.2f}s median turn time</title></circle>',
                f'  <text class="point-label" x="{label_x:.1f}" y="{py + dy:.1f}" text-anchor="{anchor}">{label}'
                f'<tspan class="point-detail" x="{label_x:.1f}" dy="16">{detail}</tspan></text>',
            ]
        )

    notable_offsets = {
        "gemini-3.7-flash (high)": (142, 26, "end"),
        "poolside/laguna-s-2.1 (none)": (16, 54, "start"),
        "gemma-4-31b (thinking)": (12, -22, "start"),
        "glm-5.2 (max)": (13, 38, "start"),
        "claude-sonnet-5 (xhigh)": (12, -28, "start"),
        "gpt-5.6-terra (xhigh)": (-142, -32, "start"),
    }
    for point in points:
        if point.label not in notable_labels:
            continue
        px, py = x(point.turn_p50_ms), y(point.score)
        dx, dy, anchor = notable_offsets[point.label]
        label_x = px + dx
        label = html.escape(_short_label(point.label))
        detail = (
            f"{point.score:g} · {point.turn_p50_ms / 1000:.2f}s · "
            f"{_money(point.cost_per_complete)}"
        )
        geometry = _label_geometry(
            model_label=point.label,
            point_x=px,
            point_y=py,
            point_radius=4.0,
            label_x=label_x,
            label_baseline=py + dy,
            anchor=anchor,
            label=_short_label(point.label),
            detail=detail,
            notable=True,
        )
        label_geometries.append(geometry)
        lines.extend(
            [
                _label_hairline(geometry),
                f'  <text class="notable-label" x="{label_x:.1f}" y="{py + dy:.1f}" text-anchor="{anchor}">{label}'
                f'<tspan class="point-detail" x="{label_x:.1f}" dy="15">{detail}</tspan></text>',
            ]
        )

    _validate_label_layout(
        label_geometries,
        points,
        frontier,
        x_position=x,
        y_position=y,
        point_x_value=lambda point: point.turn_p50_ms,
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
        for point in time_frontier(points):
            print(
                f"{point.label}\t{point.score:g}\t"
                f"{point.task_complete_rate * 100:.1f}%\t{point.turn_p50_ms:.1f}ms"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
