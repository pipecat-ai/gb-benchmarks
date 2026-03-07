#!/usr/bin/env python3
"""Build the prompt-specific primary leaderboard summary table."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = "mini_rl_run.v3"
SCRIPT_DIR = Path(__file__).resolve().parent
LEADERBOARDS_DIR = SCRIPT_DIR / "leaderboards"


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return 100.0 * (numerator / denominator)


def _normalize_openai_base_url(base_url: Any) -> str | None:
    if not isinstance(base_url, str):
        return None
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return None
    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def _display_base_url(base_url: Any) -> str | None:
    normalized = _normalize_openai_base_url(base_url)
    if normalized is None:
        return None
    text = re.sub(r"^https?://", "", normalized)
    if text.endswith("/v1"):
        text = text[:-3]
    return text or None


def _slugify_prompt_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "prompt"


def _load_run_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError(
            f"{path}: unsupported schema_version={payload.get('schema_version')} "
            f"(expected {RUN_SCHEMA_VERSION})"
        )
    return payload


def _extract_prompt_metadata(payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    prompt_hash = str(metadata.get("task_prompt_hash") or "").strip()
    prompt_id_raw = metadata.get("leaderboard_prompt_id")
    prompt_id = str(prompt_id_raw).strip() if isinstance(prompt_id_raw, str) and prompt_id_raw.strip() else None
    task_variant_raw = metadata.get("task_variant")
    task_variant = (
        str(task_variant_raw).strip() if isinstance(task_variant_raw, str) and task_variant_raw.strip() else None
    )
    return prompt_hash, prompt_id, task_variant


def _resolve_leaderboard_prompt_id(
    run_files: list[Path],
    *,
    explicit_prompt_id: str | None,
) -> tuple[str, str]:
    prompt_hashes: set[str] = set()
    prompt_ids: set[str] = set()
    task_variants: set[str] = set()

    for file_path in run_files:
        payload = _load_run_payload(file_path)
        prompt_hash, prompt_id, task_variant = _extract_prompt_metadata(payload)
        if not prompt_hash:
            raise ValueError(f"{file_path}: missing metadata.task_prompt_hash; cannot build prompt-specific leaderboard")
        prompt_hashes.add(prompt_hash)
        if prompt_id:
            prompt_ids.add(prompt_id)
        if task_variant:
            task_variants.add(task_variant)

    if len(prompt_hashes) != 1:
        hashes = ", ".join(sorted(prompt_hashes))
        raise ValueError(f"Mixed prompt hashes in input run set; expected exactly one prompt, got: {hashes}")
    prompt_hash = next(iter(prompt_hashes))

    if len(prompt_ids) > 1:
        ids = ", ".join(sorted(prompt_ids))
        raise ValueError(f"Mixed metadata.leaderboard_prompt_id values in input run set: {ids}")
    if len(task_variants) > 1:
        variants = ", ".join(sorted(task_variants))
        raise ValueError(f"Mixed metadata.task_variant values in input run set: {variants}")

    if explicit_prompt_id:
        if prompt_ids and explicit_prompt_id not in prompt_ids:
            metadata_prompt_id = next(iter(prompt_ids))
            raise ValueError(
                f"--leaderboard-prompt-id={explicit_prompt_id!r} does not match "
                f"metadata.leaderboard_prompt_id={metadata_prompt_id!r}"
            )
        if task_variants:
            task_variant = next(iter(task_variants))
            if task_variant in {"natural", "literal"} and explicit_prompt_id != task_variant:
                raise ValueError(
                    f"--leaderboard-prompt-id={explicit_prompt_id!r} does not match "
                    f"metadata.task_variant={task_variant!r}"
                )
            if task_variant == "custom" and explicit_prompt_id in {"natural", "literal"}:
                raise ValueError(
                    f"--leaderboard-prompt-id={explicit_prompt_id!r} does not match "
                    "metadata.task_variant='custom'"
                )
        return explicit_prompt_id, prompt_hash

    if len(prompt_ids) == 1:
        return next(iter(prompt_ids)), prompt_hash

    if len(task_variants) == 1:
        task_variant = next(iter(task_variants))
        if task_variant in {"natural", "literal"}:
            return task_variant, prompt_hash
        if task_variant == "custom":
            return f"custom:{prompt_hash}", prompt_hash

    raise ValueError(
        "Could not determine leaderboard prompt id from run metadata. "
        "Pass --leaderboard-prompt-id explicitly."
    )


def _default_output_path(leaderboard_prompt_id: str, prompt_hash: str) -> Path:
    if leaderboard_prompt_id == "natural":
        return LEADERBOARDS_DIR / "leaderboard-natural.md"
    if leaderboard_prompt_id == "literal":
        return LEADERBOARDS_DIR / "leaderboard-literal.md"
    if leaderboard_prompt_id.startswith("custom:"):
        suffix = leaderboard_prompt_id.split(":", 1)[1].strip() or prompt_hash
        return LEADERBOARDS_DIR / f"leaderboard-custom-{_slugify_prompt_id(suffix)[:32]}.md"
    return LEADERBOARDS_DIR / f"leaderboard-{_slugify_prompt_id(leaderboard_prompt_id)[:32]}.md"


def _load_optional_json_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def _load_enriched_rows(enriched_jsonl: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with enriched_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            file_value = row.get("file")
            if not isinstance(file_value, str) or not file_value.strip():
                raise ValueError(f"{enriched_jsonl}: found enriched row without file path")
            rows[str(Path(file_value).resolve())] = row
    return rows


def _build_model_label(row: dict[str, Any]) -> str:
    base_label = row["display_model"]
    if row["display_model"] != row["model"]:
        base_label = f"{base_label} [{row['model']}]"

    details: list[str] = []
    thinking = row.get("thinking")
    if thinking not in {None, ""}:
        details.append(f"th={thinking}")

    thinking_budget = row.get("thinking_budget")
    if thinking_budget is not None:
        details.append(f"tb={thinking_budget}")

    max_tokens = row.get("max_tokens")
    if max_tokens is not None:
        details.append(f"mt={max_tokens}")

    base_url = _display_base_url(row.get("openai_base_url"))
    if base_url:
        details.append(f"base={base_url}")

    if not details:
        return base_label
    return f"{base_label} ({', '.join(details)})"


def _require_numeric(row: dict[str, Any], *, key: str, file_path: Path) -> float:
    value = row.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{file_path}: enriched row missing numeric field {key!r}")
    return float(value)


def _build_rows(
    run_files: list[Path],
    enriched_by_file: dict[str, dict[str, Any]],
    *,
    model_name_aliases: dict[str, str],
) -> tuple[list[dict[str, Any]], set[str]]:
    by_group: dict[tuple[str, Any, Any, Any, Any], dict[str, Any]] = {}
    rubric_versions: set[str] = set()

    for file_path in sorted(run_files):
        payload = _load_run_payload(file_path)
        summary = payload.get("summary") or {}
        config = payload.get("config") or {}
        turns = payload.get("turns") or []
        resolved_path = str(file_path.resolve())
        enriched = enriched_by_file.get(resolved_path)
        if enriched is None:
            raise ValueError(f"{file_path}: missing enriched row in enriched JSONL")

        rubric_version = enriched.get("score_rubric_version")
        if isinstance(rubric_version, str) and rubric_version.strip():
            rubric_versions.add(rubric_version.strip())

        model = str(summary.get("model") or config.get("model") or "UNKNOWN")
        thinking = summary.get("thinking", config.get("thinking", summary.get("thinking_budget")))
        thinking_budget = summary.get("thinking_budget", config.get("thinking_budget"))
        max_tokens = summary.get("max_tokens", config.get("max_tokens"))
        openai_base_url = _normalize_openai_base_url(
            config.get("openai_base_url") or summary.get("openai_base_url")
        )
        display_model = model_name_aliases.get(model, model)
        group_key = (model, thinking, thinking_budget, max_tokens, openai_base_url)

        rec = by_group.setdefault(
            group_key,
            {
                "model": model,
                "display_model": display_model,
                "thinking": thinking,
                "thinking_budget": thinking_budget,
                "max_tokens": max_tokens,
                "openai_base_url": openai_base_url,
                "n": 0,
                "primary_scores": [],
                "task_complete_count": 0,
                "trade_scores": [],
                "path_scores": [],
                "tools_scores": [],
                "report_scores": [],
                "elapsed_s": [],
                "turn_decisions_ms": [],
            },
        )

        rec["n"] += 1
        rec["primary_scores"].append(_require_numeric(enriched, key="primary_score_100", file_path=file_path))
        rec["trade_scores"].append(_require_numeric(enriched, key="trade_quality_score", file_path=file_path))
        rec["path_scores"].append(_require_numeric(enriched, key="path_efficiency_score", file_path=file_path))
        rec["tools_scores"].append(_require_numeric(enriched, key="tool_discipline_score", file_path=file_path))
        rec["report_scores"].append(_require_numeric(enriched, key="report_quality_score", file_path=file_path))
        if bool(enriched.get("task_complete")):
            rec["task_complete_count"] += 1

        elapsed_ms = summary.get("elapsed_ms")
        if isinstance(elapsed_ms, (int, float)):
            rec["elapsed_s"].append(float(elapsed_ms) / 1000.0)
        else:
            enriched_elapsed = enriched.get("elapsed_ms")
            if isinstance(enriched_elapsed, (int, float)):
                rec["elapsed_s"].append(float(enriched_elapsed) / 1000.0)

        for turn in turns if isinstance(turns, list) else []:
            decision_ms = turn.get("decision_ms") if isinstance(turn, dict) else None
            if isinstance(decision_ms, (int, float)):
                rec["turn_decisions_ms"].append(float(decision_ms))

    rows: list[dict[str, Any]] = []
    for rec in by_group.values():
        n = rec["n"]
        row = {
            "model": rec["model"],
            "display_model": rec["display_model"],
            "thinking": rec["thinking"],
            "thinking_budget": rec["thinking_budget"],
            "max_tokens": rec["max_tokens"],
            "openai_base_url": rec["openai_base_url"],
            "n": n,
            "primary_score_100_median": _percentile(rec["primary_scores"], 0.50) or 0.0,
            "task_complete_rate": _pct(rec["task_complete_count"], n),
            "trade_quality_score_median": _percentile(rec["trade_scores"], 0.50) or 0.0,
            "path_efficiency_score_median": _percentile(rec["path_scores"], 0.50) or 0.0,
            "tool_discipline_score_median": _percentile(rec["tools_scores"], 0.50) or 0.0,
            "report_quality_score_median": _percentile(rec["report_scores"], 0.50) or 0.0,
            "turn_p50_ms": _percentile(rec["turn_decisions_ms"], 0.50),
            "turn_p90_ms": _percentile(rec["turn_decisions_ms"], 0.90),
            "total_time_p50_s": _percentile(rec["elapsed_s"], 0.50),
        }
        row["model_label"] = _build_model_label(row)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            -row["primary_score_100_median"],
            -row["task_complete_rate"],
            float(row["total_time_p50_s"]) if row["total_time_p50_s"] is not None else float("inf"),
            row["model_label"],
        )
    )
    return rows, rubric_versions


def _write_table(
    out_path: Path,
    rows: list[dict[str, Any]],
    runs_glob: str,
    enriched_jsonl: Path,
    leaderboard_prompt_id: str,
    prompt_hash: str,
    rubric_versions: set[str],
) -> None:
    rubric_label = ", ".join(sorted(rubric_versions)) if rubric_versions else "(unknown)"
    lines: list[str] = []
    lines.append("# Primary Leaderboard Summary (11 Columns)")
    lines.append("")
    lines.append(f"- Leaderboard prompt: `{leaderboard_prompt_id}`")
    lines.append(f"- Prompt hash: `{prompt_hash}`")
    lines.append(f"- Score rubric version: `{rubric_label}`")
    lines.append(f"- Source runs: `{runs_glob}`")
    lines.append(f"- Enriched scores: `{enriched_jsonl}`")
    lines.append("- Sort: Primary /100 desc, Task Complete % desc, Total Time P50 (s) asc")
    lines.append("")
    lines.append(
        "| Model | N | Primary /100 | Task Complete % | Trade /15 | Path /15 | Tools /15 | Report /15 | "
        "Turn P50 (ms) | Turn P90 (ms) | Total Time P50 (s) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in rows:
        lines.append(
            f"| {row['model_label']} | {row['n']} | "
            f"{row['primary_score_100_median']:.1f} | "
            f"{row['task_complete_rate']:.1f}% | "
            f"{row['trade_quality_score_median']:.1f} | "
            f"{row['path_efficiency_score_median']:.1f} | "
            f"{row['tool_discipline_score_median']:.1f} | "
            f"{row['report_quality_score_median']:.1f} | "
            f"{(row['turn_p50_ms'] or 0.0):.1f} | "
            f"{(row['turn_p90_ms'] or 0.0):.1f} | "
            f"{(row['total_time_p50_s'] or 0.0):.2f} |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build prompt-specific summary leaderboard from benchmark runs.")
    parser.add_argument("--runs-glob", required=True, help="Glob for run JSON files.")
    parser.add_argument("--enriched-jsonl", required=True, help="Path to evaluate_runs.py enriched JSONL.")
    parser.add_argument("--out", help="Output markdown table path. Defaults to a canonical prompt-specific path.")
    parser.add_argument(
        "--leaderboard-prompt-id",
        help=(
            "Prompt scope id for this leaderboard, for example 'natural', 'literal', or "
            "'custom:<prompt-hash>'. Required when the run metadata does not already identify the prompt scope."
        ),
    )
    parser.add_argument(
        "--model-name-aliases-json",
        help="Optional JSON object mapping raw model names to display aliases.",
    )
    args = parser.parse_args()

    try:
        run_files = [Path(p) for p in sorted(Path().glob(args.runs_glob))]
    except NotImplementedError:
        run_files = []
    if not run_files:
        from glob import glob

        run_files = [Path(p) for p in sorted(glob(args.runs_glob))]
    if not run_files:
        raise SystemExit(f"No run JSON files matched: {args.runs_glob}")

    enriched_jsonl = Path(args.enriched_jsonl)
    if not enriched_jsonl.exists():
        raise SystemExit(f"Missing enriched JSONL: {enriched_jsonl}")

    try:
        leaderboard_prompt_id, prompt_hash = _resolve_leaderboard_prompt_id(
            run_files,
            explicit_prompt_id=args.leaderboard_prompt_id,
        )
        rows, rubric_versions = _build_rows(
            run_files,
            _load_enriched_rows(enriched_jsonl),
            model_name_aliases=_load_optional_json_map(args.model_name_aliases_json),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    out_path = Path(args.out) if args.out else _default_output_path(leaderboard_prompt_id, prompt_hash)
    _write_table(
        out_path,
        rows,
        args.runs_glob,
        enriched_jsonl,
        leaderboard_prompt_id,
        prompt_hash,
        rubric_versions,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
