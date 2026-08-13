#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def recursive_values(value: Any, key: str) -> Iterable[Any]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                yield child
            yield from recursive_values(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from recursive_values(child, key)


def summarize(paths: list[Path]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_path"] = str(path)
        mode = str(payload.get("config", {}).get("thinking") or "unknown")
        groups[mode].append(payload)

    output: dict[str, Any] = {"files": len(paths), "groups": {}}
    for mode, runs in sorted(groups.items()):
        completion_tokens: list[float] = []
        reasoning_tokens: list[float] = []
        decision_ms: list[float] = []
        finish_reasons: Counter[str] = Counter()
        malformed_tools = 0
        empty_stream_turns = 0
        reasoning_only_or_hidden_turns = 0
        raw_reasoning_coverage = 0
        terminal_reasons: Counter[str] = Counter()

        for run in runs:
            terminal_reasons[str(run.get("summary", {}).get("terminal_reason"))] += 1
            for value in recursive_values(run, "finish_reason"):
                if value is not None:
                    finish_reasons[str(value)] += 1
            for turn in run.get("turns", []):
                if isinstance(turn.get("decision_ms"), (int, float)):
                    decision_ms.append(float(turn["decision_ms"]))
                usage = turn.get("usage") or {}
                if isinstance(usage.get("completion_tokens"), (int, float)):
                    completion_tokens.append(float(usage["completion_tokens"]))
                if isinstance(usage.get("reasoning_tokens"), (int, float)):
                    reasoning_tokens.append(float(usage["reasoning_tokens"]))
                    raw_reasoning_coverage += 1
                tool_calls = turn.get("tool_calls") or []
                raw_text = str(turn.get("raw_response_text") or "")
                if not tool_calls and not raw_text.strip():
                    if float(usage.get("completion_tokens") or 0) > 0:
                        reasoning_only_or_hidden_turns += 1
                    else:
                        empty_stream_turns += 1
                for call in tool_calls:
                    if not call.get("name") or not isinstance(call.get("args"), dict):
                        malformed_tools += 1

        output["groups"][mode] = {
            "runs": len(runs),
            "successes": sum(bool(run.get("summary", {}).get("success")) for run in runs),
            "terminal_reasons": dict(terminal_reasons),
            "turns": len(decision_ms),
            "decision_ms": {
                "p50": percentile(decision_ms, 0.5),
                "p90": percentile(decision_ms, 0.9),
                "mean": statistics.fmean(decision_ms) if decision_ms else None,
            },
            "completion_tokens": {
                "p50": percentile(completion_tokens, 0.5),
                "p90": percentile(completion_tokens, 0.9),
                "mean": statistics.fmean(completion_tokens) if completion_tokens else None,
            },
            "reasoning_tokens": {
                "observed_turns": raw_reasoning_coverage,
                "p50": percentile(reasoning_tokens, 0.5),
                "p90": percentile(reasoning_tokens, 0.9),
                "mean": statistics.fmean(reasoning_tokens) if reasoning_tokens else None,
            },
            "finish_reasons": dict(finish_reasons),
            "length_stops": finish_reasons.get("length", 0),
            "empty_stream_turns": empty_stream_turns,
            "reasoning_only_or_hidden_turns": reasoning_only_or_hidden_turns,
            "malformed_tool_calls": malformed_tools,
            "telemetry_limits": [] if reasoning_tokens and finish_reasons else [
                "The Pipecat run artifact does not expose every raw OpenAI reasoning/finish field; use the saved direct protocol probe and server log for missing coverage."
            ],
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = summarize(args.paths)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
