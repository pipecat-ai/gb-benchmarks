#!/usr/bin/env python3
"""Render the README under-four-second score and completion chart."""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path


PORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PORT_DIR.parent
DEFAULT_README = REPO_ROOT / "README.md"
DEFAULT_OUTPUT = PORT_DIR / "leaderboards/assets/under-four-reliability.svg"


@dataclass(frozen=True)
class Row:
    label: str
    score: int
    completion: float
    total_time_s: float
    cost: str
    provider: str


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def load_rows(readme_path: Path) -> list[Row]:
    """Load the curated under-four-second table in its displayed order."""

    lines = readme_path.read_text(encoding="utf-8").splitlines()
    try:
        section_index = lines.index("### Full under-four-second leaderboard")
        header_index = next(
            index
            for index, line in enumerate(lines[section_index + 1 :], section_index + 1)
            if line.startswith("| Model") and "Est. Cost / Complete" in line
        )
    except (ValueError, StopIteration) as exc:
        raise ValueError(f"under-four-second table not found in {readme_path}") from exc

    rows: list[Row] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        cells = _table_cells(line)
        if len(cells) != 12:
            raise ValueError(f"unexpected README leaderboard row: {line}")
        rows.append(
            Row(
                label=cells[0],
                score=int(cells[1]),
                completion=float(cells[2].rstrip("%")),
                total_time_s=float(cells[9]),
                cost=cells[10],
                provider=cells[11],
            )
        )
    if not rows:
        raise ValueError(f"under-four-second table is empty in {readme_path}")
    return rows


def _display_label(label: str) -> str:
    replacements = {
        "gemini-3.6-flash (high)": "Gemini 3.6 Flash · high",
        "glm-5.2 (max)": "GLM 5.2 · max",
        "claude-sonnet-5 (xhigh)": "Claude Sonnet 5 · xhigh",
        "kimi-2.6 Cerebras (thinking)": "Kimi 2.6 Cerebras · thinking",
        "claude-sonnet-4-6 (none)": "Claude Sonnet 4.6 · none",
        "gpt-5.4 (low)": "GPT-5.4 · low",
        "gpt-5.6-terra (xhigh)": "GPT-5.6 Terra · xhigh",
        "gpt-5.2 (medium)": "GPT-5.2 · medium",
        "qwen3.6-27b (high)": "Qwen 3.6 27B · high",
        "gemma-4-31b (thinking)": "Gemma 4 31B · thinking",
        "claude-haiku-4-5-20251001 (low)": "Claude Haiku 4.5 · low",
        "nemotron-3-ultra-550b (thinking)": "Nemotron 3 Ultra 550B · thinking",
        "qwen3.6-35b-a3b (high, FP8)": "Qwen 3.6 35B-A3B · high, FP8",
        "gpt-5.6-luna (xhigh)": "GPT-5.6 Luna · xhigh",
        "poolside/laguna-s-2.1 (none)": "Laguna S 2.1 · none",
        "gemini-3.1-flash-lite-preview (high)": "Gemini 3.1 Flash Lite · high",
        "muse-glimmer-30b (high, GGUF)": "Muse Glimmer 30B · high, GGUF",
        "inkling (low)": "Inkling · low",
        "gpt-4.1": "GPT-4.1",
        "gemini-3.5-flash-lite (minimal)": "Gemini 3.5 Flash Lite · minimal",
        "nemotron-3-super-120b (tb=512)": "Nemotron 3 Super 120B · tb=512",
    }
    return replacements.get(label, label)


def _metadata(row: Row) -> str:
    seconds = f"{row.total_time_s:.0f}s total"
    if row.cost == "—":
        return f"{seconds} · no API price · {row.provider}"
    return f"{seconds} · {row.cost} / complete · {row.provider}"


def render_svg(rows: list[Row]) -> str:
    width = 1200
    left, right = 38, 34
    plot_left, plot_right = 430, width - right
    title_y, subtitle_y, axis_y = 38, 64, 102
    first_row_y, row_height = 140, 48
    last_row_y = first_row_y + (len(rows) - 1) * row_height
    footnote_y = last_row_y + 57
    height = footnote_y + 42
    min_score, max_score = 60, 100
    ticks = [60, 70, 80, 90, 100]

    def x(value: float) -> float:
        return plot_left + (value - min_score) / (max_score - min_score) * (
            plot_right - plot_left
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Port-to-port score and completion reliability</title>',
        '  <desc id="desc">A ranked dot plot of the best under-four-second configuration for each model. Dots show median primary score from 60 to 100. Hairline tails on three models show their incomplete task share.</desc>',
        "  <style>",
        "    text { fill: #282522; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-variant-numeric: tabular-nums; }",
        "    .title, .model { font-family: Georgia, 'Times New Roman', serif; }",
        "    .title { font-size: 27px; }",
        "    .subtitle { fill: #716c66; font-size: 13px; }",
        "    .axis-label { fill: #716c66; font-size: 11px; letter-spacing: .04em; text-transform: uppercase; }",
        "    .tick { fill: #88827c; font-size: 11px; }",
        "    .guide { stroke: #ddd9d4; stroke-width: .75; }",
        "    .guide.edge { stroke: #bdb7b0; }",
        "    .model { font-size: 15px; }",
        "    .meta { fill: #77716b; font-size: 10.5px; }",
        "    .tail { stroke: #827b74; stroke-width: 1; }",
        "    .tail-cap { stroke: #827b74; stroke-width: 1; }",
        "    .completion { fill: #716a64; font-size: 10.5px; }",
        "    .dot { fill: #292623; }",
        "    .score { fill: #292623; font-size: 12px; font-weight: 600; }",
        "    .note { fill: #77716b; font-family: Georgia, 'Times New Roman', serif; font-size: 11.5px; font-style: italic; }",
        "  </style>",
        f'  <text class="title" x="{left}" y="{title_y}">Port-to-port: score and completion reliability</text>',
        f'  <text class="subtitle" x="{left}" y="{subtitle_y}">Best configuration per model · turn P50 under four seconds · higher is better</text>',
        f'  <text class="axis-label" x="{plot_right}" y="{axis_y - 22}" text-anchor="end">Median primary score</text>',
    ]

    for tick in ticks:
        px = x(tick)
        edge_class = " edge" if tick in (min_score, max_score) else ""
        lines.extend(
            [
                f'  <line class="guide{edge_class}" x1="{px:.1f}" y1="{axis_y}" x2="{px:.1f}" y2="{last_row_y + 17}"/>',
                f'  <text class="tick" x="{px:.1f}" y="{axis_y - 7}" text-anchor="middle">{tick}</text>',
            ]
        )

    for index, row in enumerate(rows):
        py = first_row_y + index * row_height
        px = x(row.score)
        label = html.escape(_display_label(row.label))
        metadata = html.escape(_metadata(row))
        details = html.escape(
            f"{row.label}: score {row.score}; {row.completion:.0f}% task completion; "
            f"{row.total_time_s:.2f} seconds total; {row.cost} per complete; {row.provider}"
        )
        lines.extend(
            [
                f'  <text class="model" x="{left}" y="{py - 3}">{label}</text>',
                f'  <text class="meta" x="{left}" y="{py + 14}">{metadata}</text>',
            ]
        )

        if row.completion < 100:
            # The tail uses the same percentage-point scale as the score axis:
            # its length is exactly the unfinished share (100 - completion).
            tail_start = x(max(min_score, row.score - (100 - row.completion)))
            lines.extend(
                [
                    f'  <line class="tail" x1="{tail_start:.1f}" y1="{py}" x2="{px - 5:.1f}" y2="{py}"/>',
                    f'  <line class="tail-cap" x1="{tail_start:.1f}" y1="{py - 3.5:.1f}" x2="{tail_start:.1f}" y2="{py + 3.5:.1f}"/>',
                    f'  <text class="completion" x="{tail_start - 7:.1f}" y="{py + 4:.1f}" text-anchor="end">{row.completion:.0f}% complete</text>',
                ]
            )

        score_x = px - 11 if row.score >= 98 else px + 11
        score_anchor = "end" if row.score >= 98 else "start"
        lines.extend(
            [
                f'  <circle class="dot" cx="{px:.1f}" cy="{py}" r="4.5"><title>{details}</title></circle>',
                f'  <text class="score" x="{score_x:.1f}" y="{py + 4}" text-anchor="{score_anchor}">{row.score}</text>',
            ]
        )

    lines.extend(
        [
            f'  <text class="note" x="{left}" y="{footnote_y}">Dot = median primary score. Tail length = unfinished share (100% − completion), on the same percentage-point scale.</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the existing SVG differs from freshly rendered output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rendered = render_svg(load_rows(args.readme.resolve()))
    output = args.output.resolve()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{output} is stale; rerun {Path(__file__).name}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
