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
MIN_LABEL_PADDING = 10.0
MIN_LABEL_DOT_PADDING = 8.0
MIN_LABEL_LINE_PADDING = 4.0
MIN_HAIRLINE_PADDING = 3.0
PREFERRED_HAIRLINE_LENGTH = 12.0
PREFERRED_OFF_AXIS_COMPONENT = 4.0
OFF_AXIS_PENALTY_WEIGHT = 0.5
TEXT_BOUNDS_SAFETY_PADDING = 3.0


@dataclass(frozen=True)
class Point:
    label: str
    score: int
    task_complete_rate: float
    cost_per_complete: float
    turn_p50_ms: float = 0.0
    provider: str = ""


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class LabelGeometry:
    model_label: str
    box: Rect
    hairline: Segment


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
        if len(cells) not in {12, 13}:
            raise ValueError(f"unexpected README leaderboard row: {line}")
        has_turn_cost = len(cells) == 13
        complete_index = 11 if has_turn_cost else 10
        provider_index = 12 if has_turn_cost else 11
        label = cells[0]
        if cells[complete_index] == "—" and label not in estimates:
            # Locally served rows without a public-API price do not belong on
            # the cost frontier, but should not make the renderer unusable.
            continue
        if label not in estimates:
            raise ValueError(f"no canonical cost estimate for README row {label!r}")
        estimate = estimates[label]
        cost = float(estimate["estimated_cost_per_completed_task"])
        expected_cost = _money(cost)
        if cells[complete_index] != expected_cost:
            raise ValueError(
                f"README cost for {label!r} is {cells[complete_index]}, expected {expected_cost}"
            )
        expected_provider = estimate["provider"]
        if cells[provider_index] != expected_provider:
            raise ValueError(
                f"README provider for {label!r} is {cells[provider_index]}, expected {expected_provider}"
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


def _estimated_text_width(value: str, font_size: float, *, bold: bool) -> float:
    """Estimate sans-serif SVG text width closely enough for leader placement."""

    units = 0.0
    for character in value:
        if character == " ":
            units += 0.29
        elif character in "ilI1|.,:;!'`":
            units += 0.29
        elif character in "mwMW@%":
            units += 0.88
        elif character.isupper():
            units += 0.66
        elif character.isdigit():
            units += 0.56
        else:
            units += 0.54
    return units * font_size * (1.04 if bold else 1.0) + TEXT_BOUNDS_SAFETY_PADDING


def _label_geometry(
    *,
    model_label: str,
    point_x: float,
    point_y: float,
    point_radius: float,
    label_x: float,
    label_baseline: float,
    anchor: str,
    label: str,
    detail: str,
    notable: bool,
) -> LabelGeometry:
    """Connect the closest point of a two-line label box to the dot edge."""

    title_size = 12.0 if notable else 13.0
    detail_size = 12.0
    line_height = 15.0 if notable else 16.0
    width = max(
        _estimated_text_width(label, title_size, bold=True),
        _estimated_text_width(detail, detail_size, bold=False),
    )
    if anchor == "end":
        box_left, box_right = label_x - width, label_x
    else:
        box_left, box_right = label_x, label_x + width
    box_top = label_baseline - title_size
    box_bottom = label_baseline + line_height + 3.0
    start_x = min(max(point_x, box_left), box_right)
    start_y = min(max(point_y, box_top), box_bottom)
    dx = point_x - start_x
    dy = point_y - start_y
    distance = math.hypot(dx, dy)
    if distance == 0:
        raise ValueError(f"label box for {model_label!r} contains its point")
    end_x = point_x - dx / distance * point_radius
    end_y = point_y - dy / distance * point_radius
    return LabelGeometry(
        model_label=model_label,
        box=Rect(box_left, box_top, box_right, box_bottom),
        hairline=Segment(start_x, start_y, end_x, end_y),
    )


def _label_hairline(geometry: LabelGeometry) -> str:
    segment = geometry.hairline
    return (
        f'  <line class="label-hairline" x1="{segment.x1:.1f}" y1="{segment.y1:.1f}" '
        f'x2="{segment.x2:.1f}" y2="{segment.y2:.1f}"/>'
    )


def _orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(first: Segment, second: Segment) -> bool:
    epsilon = 1e-7
    o1 = _orientation(first.x1, first.y1, first.x2, first.y2, second.x1, second.y1)
    o2 = _orientation(first.x1, first.y1, first.x2, first.y2, second.x2, second.y2)
    o3 = _orientation(second.x1, second.y1, second.x2, second.y2, first.x1, first.y1)
    o4 = _orientation(second.x1, second.y1, second.x2, second.y2, first.x2, first.y2)
    if (
        ((o1 > epsilon and o2 < -epsilon) or (o1 < -epsilon and o2 > epsilon))
        and ((o3 > epsilon and o4 < -epsilon) or (o3 < -epsilon and o4 > epsilon))
    ):
        return True

    def on_segment(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
        return (
            min(ax, bx) - epsilon <= cx <= max(ax, bx) + epsilon
            and min(ay, by) - epsilon <= cy <= max(ay, by) + epsilon
        )

    return (
        (abs(o1) <= epsilon and on_segment(first.x1, first.y1, first.x2, first.y2, second.x1, second.y1))
        or (abs(o2) <= epsilon and on_segment(first.x1, first.y1, first.x2, first.y2, second.x2, second.y2))
        or (abs(o3) <= epsilon and on_segment(second.x1, second.y1, second.x2, second.y2, first.x1, first.y1))
        or (abs(o4) <= epsilon and on_segment(second.x1, second.y1, second.x2, second.y2, first.x2, first.y2))
    )


def _rects_overlap(
    first: Rect, second: Rect, *, gap: float = MIN_LABEL_PADDING
) -> bool:
    return not (
        first.right + gap <= second.left
        or second.right + gap <= first.left
        or first.bottom + gap <= second.top
        or second.bottom + gap <= first.top
    )


def _point_in_rect(x: float, y: float, rect: Rect) -> bool:
    return rect.left <= x <= rect.right and rect.top <= y <= rect.bottom


def _inflate_rect(rect: Rect, padding: float) -> Rect:
    return Rect(
        rect.left - padding,
        rect.top - padding,
        rect.right + padding,
        rect.bottom + padding,
    )


def _segment_intersects_rect(segment: Segment, rect: Rect) -> bool:
    if _point_in_rect(segment.x1, segment.y1, rect) or _point_in_rect(
        segment.x2, segment.y2, rect
    ):
        return True
    edges = (
        Segment(rect.left, rect.top, rect.right, rect.top),
        Segment(rect.right, rect.top, rect.right, rect.bottom),
        Segment(rect.right, rect.bottom, rect.left, rect.bottom),
        Segment(rect.left, rect.bottom, rect.left, rect.top),
    )
    return any(_segments_intersect(segment, edge) for edge in edges)


def _point_segment_distance(x: float, y: float, segment: Segment) -> float:
    dx = segment.x2 - segment.x1
    dy = segment.y2 - segment.y1
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return math.hypot(x - segment.x1, y - segment.y1)
    fraction = max(
        0.0,
        min(1.0, ((x - segment.x1) * dx + (y - segment.y1) * dy) / denominator),
    )
    return math.hypot(x - (segment.x1 + fraction * dx), y - (segment.y1 + fraction * dy))


def _segment_distance(first: Segment, second: Segment) -> float:
    if _segments_intersect(first, second):
        return 0.0
    return min(
        _point_segment_distance(first.x1, first.y1, second),
        _point_segment_distance(first.x2, first.y2, second),
        _point_segment_distance(second.x1, second.y1, first),
        _point_segment_distance(second.x2, second.y2, first),
    )


def _hairline_length(geometry: LabelGeometry) -> float:
    segment = geometry.hairline
    return math.hypot(segment.x2 - segment.x1, segment.y2 - segment.y1)


def _hairline_packing_cost(geometry: LabelGeometry) -> float:
    """Prefer legible 12px connectors with a modest off-axis angle."""

    length = _hairline_length(geometry)
    shortfall = max(0.0, PREFERRED_HAIRLINE_LENGTH - length)
    segment = geometry.hairline
    minor_component = min(
        abs(segment.x2 - segment.x1),
        abs(segment.y2 - segment.y1),
    )
    axis_shortfall = max(0.0, PREFERRED_OFF_AXIS_COMPONENT - minor_component)
    return (
        length
        + shortfall * shortfall
        + OFF_AXIS_PENALTY_WEIGHT * axis_shortfall * axis_shortfall
    )


def _rect_circle_overlap(rect: Rect, x: float, y: float, radius: float) -> bool:
    closest_x = min(max(x, rect.left), rect.right)
    closest_y = min(max(y, rect.top), rect.bottom)
    return math.hypot(x - closest_x, y - closest_y) < radius


def _validate_label_layout(
    geometries: list[LabelGeometry],
    points: list[Point],
    frontier: list[Point],
    *,
    x_position,
    y_position,
    point_x_value=None,
) -> None:
    """Reject label packing with visual-element overlaps or crossed hairlines."""

    if point_x_value is None:
        point_x_value = lambda point: point.cost_per_complete

    failures: list[str] = []
    for index, first in enumerate(geometries):
        for second in geometries[index + 1 :]:
            if _rects_overlap(first.box, second.box):
                failures.append(f"label boxes overlap: {first.model_label} / {second.model_label}")
            if _segment_distance(first.hairline, second.hairline) < MIN_HAIRLINE_PADDING:
                failures.append(f"hairlines cross or crowd: {first.model_label} / {second.model_label}")
            if _segment_intersects_rect(
                first.hairline, _inflate_rect(second.box, MIN_LABEL_LINE_PADDING)
            ):
                failures.append(f"hairline enters label: {first.model_label} / {second.model_label}")
            if _segment_intersects_rect(
                second.hairline, _inflate_rect(first.box, MIN_LABEL_LINE_PADDING)
            ):
                failures.append(f"hairline enters label: {second.model_label} / {first.model_label}")

    frontier_labels = {point.label for point in frontier}
    plotted_points = {
        point.label: (
            x_position(point_x_value(point)),
            y_position(point.score),
            5.5 if point.label in frontier_labels else 4.0,
        )
        for point in points
    }
    for geometry in geometries:
        for label, (px, py, radius) in plotted_points.items():
            if label == geometry.model_label:
                if _rect_circle_overlap(
                    geometry.box, px, py, radius + MIN_LABEL_DOT_PADDING
                ):
                    failures.append(f"label touches its dot: {geometry.model_label}")
                continue
            if _rect_circle_overlap(
                geometry.box, px, py, radius + MIN_LABEL_DOT_PADDING
            ):
                failures.append(f"label overlaps dot: {geometry.model_label} / {label}")
            if _point_segment_distance(px, py, geometry.hairline) < radius + MIN_HAIRLINE_PADDING:
                failures.append(f"hairline crosses dot: {geometry.model_label} / {label}")

    frontier_segments = [
        Segment(
            x_position(point_x_value(first)),
            y_position(first.score),
            x_position(point_x_value(second)),
            y_position(second.score),
        )
        for first, second in zip(frontier, frontier[1:])
    ]
    for geometry in geometries:
        for segment in frontier_segments:
            if _segment_intersects_rect(
                segment, _inflate_rect(geometry.box, MIN_LABEL_LINE_PADDING)
            ):
                failures.append(f"frontier enters label: {geometry.model_label}")
            if _segments_intersect(segment, geometry.hairline):
                failures.append(f"frontier crosses hairline: {geometry.model_label}")

    if failures:
        raise ValueError("invalid chart label packing:\n- " + "\n- ".join(failures))


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
        "gemini-3.7-flash (high)",
        "glm-5.2 (max)",
        "claude-sonnet-5 (xhigh)",
        "gpt-5.6-terra (xhigh)",
    }
    label_geometries: list[LabelGeometry] = []

    def x(value: float) -> float:
        span = math.log10(max_cost) - math.log10(min_cost)
        return left + (math.log10(value) - math.log10(min_cost)) / span * plot_width

    def y(value: float) -> float:
        return top + (max_score - value) / (max_score - min_score) * plot_height

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Score versus estimated cost per completed port-to-port task</title>',
        '  <desc id="desc">A logarithmic scatter plot of the best under-four-second configuration for each model. Laguna S 2.1, Gemma 4 31B, Gemini 3.5 Flash Lite, Kimi 2.6, and Grok 4.6 form the efficient frontier.</desc>',
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
        "    .label-hairline { stroke: #aaa49e; stroke-width: .65; }",
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

    # Collision-constrained coordinate search minimizes connector length; the
    # geometry audit below rejects future data/layout changes that break it.
    label_offsets = {
        "grok-4.6 (high)": (16, 18, "start"),
        "poolside/laguna-s-2.1 (none)": (8, 28, "start"),
        "gemma-4-31b (thinking)": (-8, -34, "end"),
        "gemini-3.5-flash-lite (high)": (-12, -38, "end"),
        "kimi-2.6 (thinking)": (-8, -34, "end"),
        "deepseek-v4-flash-0731 (low)": (12, 34, "start"),
        "glm-5.2 (max)": (13, -35, "start"),
    }
    for point in frontier:
        px, py = x(point.cost_per_complete), y(point.score)
        dx, dy, anchor = label_offsets.get(point.label, (12, -18, "start"))
        label_x = px + dx
        label = html.escape(_short_label(point.label))
        detail = (
            f"{point.score} · {_money(point.cost_per_complete)} · "
            f"{point.turn_p50_ms / 1000:.2f}s"
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
        hairline = _label_hairline(geometry)
        lines.extend(
            [
                hairline,
                f'  <circle class="frontier" cx="{px:.1f}" cy="{py:.1f}" r="5.5"><title>{html.escape(point.label)}: {point.score}, {_money(point.cost_per_complete)} per completed task</title></circle>',
                f'  <text class="point-label" x="{label_x:.1f}" y="{py + dy:.1f}" text-anchor="{anchor}">{label}'
                f'<tspan class="point-detail" x="{label_x:.1f}" dy="16">{detail}</tspan></text>',
            ]
        )

    notable_offsets = {
        "gemini-3.7-flash (high)": (12, 24, "start"),
        "glm-5.2 (max)": (-22, 28, "start"),
        "claude-sonnet-5 (xhigh)": (-11, -29, "end"),
        "gpt-5.6-terra (xhigh)": (10, 24, "start"),
    }
    for point in points:
        if point.label not in notable_labels:
            continue
        px, py = x(point.cost_per_complete), y(point.score)
        dx, dy, anchor = notable_offsets[point.label]
        label_x = px + dx
        label = html.escape(_short_label(point.label))
        detail = (
            f"{point.score} · {_money(point.cost_per_complete)} · "
            f"{point.turn_p50_ms / 1000:.2f}s"
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
        lines.append(_label_hairline(geometry))
        lines.append(
            f'  <text class="notable-label" x="{label_x:.1f}" y="{py + dy:.1f}" text-anchor="{anchor}">{label}'
            f'<tspan class="point-detail" x="{label_x:.1f}" dy="15">{detail}</tspan></text>'
        )

    _validate_label_layout(
        label_geometries,
        points,
        frontier,
        x_position=x,
        y_position=y,
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
