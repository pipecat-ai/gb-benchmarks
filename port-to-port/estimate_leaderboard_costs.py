#!/usr/bin/env python3
"""Estimate README benchmark cost per completed task from trace usage.

API-priced rows use the mean observed token usage across their canonical 25-run
cohort, regardless of where the benchmark itself ran. GPT-5.6 uses a recent
representative sample because its historical traces lack cache-write detail.
The expected cost of one completed task is cost/attempt divided by the
official-judge Task Complete rate shown on the README.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any, Iterable


PORT_DIR = Path(__file__).resolve().parent
PRICE_PROVIDER_PREFIXES = {
    "anthropic-": "Anthropic",
    "baseten-": "BaseTen",
    "bedrock-": "AWS Bedrock",
    "empiriolabs-": "EmpirioLabs",
    "google-": "AI Studio",
    "openai-": "OpenAI",
    "openrouter-": "OpenRouter",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PORT_DIR / candidate


def _matches(run: dict[str, Any], selector: dict[str, Any]) -> bool:
    config = run.get("config", {})
    return all(config.get(key) == value for key, value in selector.items())


def _source_tsv_paths(path: Path) -> list[Path]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return [_resolve(row["json"]) for row in rows if row.get("clean") == "1"]


def _trace_usage_for_turn(run: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    trace_index = turn.get("responses_trace_index")
    if trace_index is None:
        return {}
    for trace in run.get("responses_traces", []):
        if trace.get("trace_index") == trace_index:
            return trace.get("usage") or {}
    return {}


def token_cost(run: dict[str, Any], rate: dict[str, Any]) -> tuple[float, dict[str, int]]:
    """Return list-price cost and normalized billable token buckets."""

    buckets = {
        "uncached_input": 0,
        "cached_input": 0,
        "cache_write": 0,
        "output": 0,
    }
    semantics = rate["usage_semantics"]
    cache_write_observed = False

    for turn in run.get("turns", []):
        usage = turn.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        cached = int(usage.get("cache_read_input_tokens") or 0)
        cache_write = int(usage.get("cache_creation_input_tokens") or 0)

        if semantics == "openai_responses":
            trace_usage = _trace_usage_for_turn(run, turn)
            if "cache_write_tokens" in trace_usage and trace_usage["cache_write_tokens"] is not None:
                cache_write = int(trace_usage["cache_write_tokens"])
                cache_write_observed = True
            elif "cache_write_input_tokens" in usage:
                cache_write = int(usage["cache_write_input_tokens"] or 0)
                cache_write_observed = True

        if semantics == "anthropic":
            uncached = prompt
        else:
            uncached = prompt - cached - cache_write

        if uncached < 0:
            raise ValueError(
                f"negative uncached input for {run.get('config', {}).get('model')}: "
                f"prompt={prompt}, cached={cached}, cache_write={cache_write}"
            )

        output = completion
        if semantics == "google":
            output += int(usage.get("reasoning_tokens") or 0)

        buckets["uncached_input"] += uncached
        buckets["cached_input"] += cached
        buckets["cache_write"] += cache_write
        buckets["output"] += output

    if semantics == "openai_responses" and not cache_write_observed:
        raise ValueError(
            f"GPT-5.6 cache-write usage was not observed for {run.get('config', {}).get('model')}"
        )

    cost = (
        buckets["uncached_input"] * float(rate["input"])
        + buckets["cached_input"] * float(rate.get("cached_input", rate["input"]))
        + buckets["cache_write"] * float(rate.get("cache_write", rate["input"]))
        + buckets["output"] * float(rate["output"])
    ) / 1_000_000
    return cost, buckets


def run_metrics(run: dict[str, Any]) -> dict[str, float | int | str | bool]:
    turns = run.get("turns", [])
    return {
        "turns": int(run.get("summary", {}).get("turns_executed") or len(turns)),
        "accounted_tokens": sum(
            int((turn.get("usage") or {}).get("total_tokens") or 0) for turn in turns
        ),
        "active_seconds": sum(float(turn.get("decision_ms") or 0.0) for turn in turns) / 1000,
        "elapsed_seconds": float(run.get("summary", {}).get("elapsed_ms") or 0.0) / 1000,
        "terminal_reason": str(run.get("summary", {}).get("terminal_reason") or "unknown"),
        "raw_success": bool(run.get("summary", {}).get("success")),
    }


def modal_cost(
    run: dict[str, Any], resource: dict[str, Any], rates: dict[str, float]
) -> tuple[float, float | None]:
    active_seconds = float(run_metrics(run)["active_seconds"])
    count = int(resource["count"])
    primary = active_seconds * count * float(rates[resource["gpu"]])
    fallback_name = resource.get("fallback_gpu")
    fallback = (
        active_seconds * count * float(rates[fallback_name]) if fallback_name else None
    )
    return primary, fallback


def _median_metrics(runs: Iterable[dict[str, Any]]) -> dict[str, float]:
    metrics = [run_metrics(run) for run in runs]
    return {
        key: float(statistics.median(float(item[key]) for item in metrics))
        for key in ("turns", "accounted_tokens", "active_seconds", "elapsed_seconds")
    }


def representative_check(
    sample: dict[str, Any], historical_runs: list[dict[str, Any]]
) -> dict[str, Any]:
    sample_metrics = run_metrics(sample)
    medians = _median_metrics(historical_runs)
    ratios: dict[str, float | None] = {}
    for key in ("turns", "accounted_tokens", "active_seconds"):
        denominator = medians[key]
        ratios[key] = float(sample_metrics[key]) / denominator if denominator else None
    representative = all(
        ratio is not None and 2 / 3 <= ratio <= 1.5 for ratio in ratios.values()
    )
    return {
        "representative": representative,
        "acceptance_band": [2 / 3, 1.5],
        "sample": sample_metrics,
        "historical_medians": medians,
        "sample_to_median_ratios": ratios,
    }


def _sample_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _money(value: float) -> str:
    if value >= 10:
        return f"${value:.2f}"
    if value >= 1:
        return f"${value:.3f}"
    return f"${value:.4f}"


def provider_for_price_key(price_key: str) -> str:
    """Return the API provider supplying the rate used for a cost estimate."""

    for prefix, provider in PRICE_PROVIDER_PREFIXES.items():
        if price_key.startswith(prefix):
            return provider
    raise ValueError(f"no provider mapping for price key {price_key!r}")


def estimate(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    pricing = _load_json(_resolve(manifest["pricing"]))
    canonical_paths = [Path(path) for path in glob.glob(str(_resolve(manifest["canonical_history"])))]
    canonical_runs = [(path, _load_json(path)) for path in canonical_paths]
    results: list[dict[str, Any]] = []

    for row in manifest["rows"]:
        if "source_tsv" in row:
            history_paths = _source_tsv_paths(_resolve(row["source_tsv"]))
            historical_runs = [_load_json(path) for path in history_paths]
        else:
            selected = [item for item in canonical_runs if _matches(item[1], row["selector"])]
            history_paths = [item[0] for item in selected]
            historical_runs = [item[1] for item in selected]

        if len(historical_runs) != 25:
            raise ValueError(f"{row['label']} selected {len(historical_runs)} historical runs, expected 25")

        method = row["method"]
        completion_rate = float(row["task_complete_rate"])
        result: dict[str, Any] = {
            "label": row["label"],
            "method": method,
            "historical_runs": len(historical_runs),
            "task_complete_rate": completion_rate,
        }

        if method.startswith("token_history"):
            rate = pricing["token_rates_per_million"][row["rate"]]
            priced = [token_cost(run, rate) for run in historical_runs]
            attempt_costs = [item[0] for item in priced]
            attempt_cost = statistics.mean(attempt_costs)
            result.update(
                {
                    "cost_samples": len(attempt_costs),
                    "price_key": row["rate"],
                    "provider": provider_for_price_key(row["rate"]),
                    "proxy_price": bool(rate.get("proxy")),
                    "mean_cost_per_attempt": attempt_cost,
                    "median_cost_per_attempt": statistics.median(attempt_costs),
                    "estimated_cost_per_completed_task": attempt_cost / completion_rate,
                    "aggregate_billable_tokens": {
                        key: sum(item[1][key] for item in priced)
                        for key in priced[0][1]
                    },
                }
            )
        elif method in {"modal_history", "modal_history_range"}:
            priced = [
                modal_cost(
                    run,
                    row["resource"],
                    pricing["modal_resource_rates_per_second"],
                )
                for run in historical_runs
            ]
            attempt_costs = [item[0] for item in priced]
            fallback_costs = [item[1] for item in priced if item[1] is not None]
            attempt_cost = statistics.mean(attempt_costs)
            result.update(
                {
                    "cost_samples": len(attempt_costs),
                    "provider": "Modal",
                    "resource": row["resource"],
                    "mean_cost_per_attempt": attempt_cost,
                    "median_cost_per_attempt": statistics.median(attempt_costs),
                    "estimated_cost_per_completed_task": attempt_cost / completion_rate,
                }
            )
            if fallback_costs:
                fallback_cost = statistics.mean(fallback_costs)
                result["fallback_cost_per_attempt"] = fallback_cost
                result["fallback_cost_per_completed_task"] = fallback_cost / completion_rate
        else:
            sample_path = _resolve(row["sample"])
            sample = _load_json(sample_path)
            check = representative_check(sample, historical_runs)
            result.update(
                {
                    "cost_samples": 1,
                    "sample": str(sample_path.relative_to(PORT_DIR)),
                    "sample_sha256": _sample_digest(sample_path),
                    "sanity_check": check,
                }
            )
            if method == "token_sample":
                rate = pricing["token_rates_per_million"][row["rate"]]
                attempt_cost, buckets = token_cost(sample, rate)
                result.update(
                    {
                        "price_key": row["rate"],
                        "provider": provider_for_price_key(row["rate"]),
                        "mean_cost_per_attempt": attempt_cost,
                        "estimated_cost_per_completed_task": attempt_cost / completion_rate,
                        "sample_billable_tokens": buckets,
                    }
                )
            elif method in {"modal_sample", "modal_sample_range"}:
                attempt_cost, fallback_cost = modal_cost(
                    sample, row["resource"], pricing["modal_resource_rates_per_second"]
                )
                result.update(
                    {
                        "resource": row["resource"],
                        "provider": "Modal",
                        "mean_cost_per_attempt": attempt_cost,
                        "estimated_cost_per_completed_task": attempt_cost / completion_rate,
                    }
                )
                if fallback_cost is not None:
                    result["fallback_cost_per_attempt"] = fallback_cost
                    result["fallback_cost_per_completed_task"] = fallback_cost / completion_rate
            else:
                raise ValueError(f"unsupported method {method}")

        results.append(result)

    return {
        "schema_version": "leaderboard_cost_estimates.v1",
        "pricing_as_of": pricing["as_of"],
        "currency": pricing["currency"],
        "definition": "mean representative cost per attempt divided by official-judge Task Complete rate",
        "pricing_basis": pricing["basis"],
        "sources": pricing["sources"],
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Natural Leaderboard Cost Estimates",
        "",
        f"Pricing snapshot: {report['pricing_as_of']} ({report['currency']}).",
        "",
        "Estimated cost per completed task is mean representative cost per attempt divided by the "
        "official-judge Task Complete rate. API-provider estimates use all 25 canonical traces, "
        "regardless of where the benchmark ran. GPT-5.6 uses one sanity-checked sample.",
        "",
        "| Model | Method | Cost samples | Task complete | Cost / attempt | Est. cost / complete | Sample check | Provider |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    method_names = {
        "token_history": "25-run token usage",
        "token_history_proxy": "25-run token usage, price proxy",
        "token_sample": "1-run token sample",
        "modal_history": "25-run GPU active time",
        "modal_history_range": "25-run GPU active time",
        "modal_sample": "1-run warm GPU sample",
        "modal_sample_range": "1-run warm GPU sample",
    }
    for item in report["results"]:
        attempt = _money(item["mean_cost_per_attempt"])
        complete = _money(item["estimated_cost_per_completed_task"])
        if "fallback_cost_per_attempt" in item:
            attempt += f"–{_money(item['fallback_cost_per_attempt'])}"
            complete += f"–{_money(item['fallback_cost_per_completed_task'])}"
        if "sanity_check" in item:
            sample_check = "pass" if item["sanity_check"]["representative"] else "outlier"
        else:
            sample_check = "n/a"
        lines.append(
            f"| {item['label']} | {method_names[item['method']]} | {item['cost_samples']} | "
            f"{item['task_complete_rate'] * 100:.1f}% | {attempt} | {complete} | "
            f"{sample_check} | {item['provider']} |"
        )
    lines.extend(
        [
            "",
            "Notes:",
            "",
            "- Kimi K2.6 uses Baseten's public Kimi K2.6 token price as a market proxy; the measured Cerebras dedicated-endpoint contract is not public.",
            "- Gemma 4 uses Amazon Bedrock US Standard on-demand pricing; Bedrock does not publish a separate cached-input rate for this model.",
            "- Qwen 3.6 benchmark scores and latency come from BaseTen single-H100 vLLM deployments. OpenRouter supplies same-model price proxies; the 27B estimate conservatively prices all input at the standard rate because historical traces do not expose API cache-read token buckets, and OpenRouter does not promise that its 35B serving precision matches the scored official FP8 checkpoint.",
            "- Other self-hosted benchmark runs are priced against a public same-model API endpoint. OpenRouter supplies Nemotron Super, Qwen 3.5 9B/27B, and GLM 4.7 Flash prices; EmpirioLabs supplies Qwen 3.5 4B.",
            "- Google reasoning tokens are billed as output. OpenAI-compatible reasoning tokens are already included in completion tokens. Anthropic base input, 5-minute cache-write, cache-read, and output buckets are priced separately.",
            "- These are list-price workload estimates, not invoice reconciliation.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PORT_DIR / "costs/leaderboard-natural-cost-manifest.json",
    )
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = estimate(args.manifest.resolve())
    rendered = render_markdown(report)
    if args.out_json:
        args.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.out_md:
        args.out_md.write_text(rendered, encoding="utf-8")
    if not args.out_json and not args.out_md:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
