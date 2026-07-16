#!/usr/bin/env python3
"""Preliminary effort-level probe for the three GPT-5.6 versions (luna/sol/terra).

For each version x effort level: send a fixed reasoning prompt via chat
completions with reasoning_effort, record HTTP acceptance (400s reveal the valid
level set), reasoning_tokens, completion_tokens, finish_reason, and latency.
Non-streaming, default temperature, bounded max_completion_tokens. No harness
changes; read-only diagnostic."""
import json, os, time, statistics, sys
from pathlib import Path
from openai import OpenAI, BadRequestError, APIStatusError

MODELS = ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"]
LEVELS = ["none", "minimal", "low", "medium", "high", "xhigh"]
SAMPLES = 2
MAX_COMPLETION_TOKENS = 4000
PROMPT = (
    "You have a 3-liter jug and a 5-liter jug and unlimited water. Give the "
    "shortest sequence of fill/empty/pour steps to measure exactly 4 liters, "
    "then output on the final line only the integer number of steps in your "
    "shortest solution."
)

def read_key():
    for line in Path("/home/khkramer/src/gb-benchmarks/.env").read_text().splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENAI_API_KEY not found")

def main():
    client = OpenAI(api_key=read_key())
    records = []
    for model in MODELS:
        for level in LEVELS:
            for s in range(1, SAMPLES + 1):
                rec = {"model": model, "level": level, "sample": s}
                t0 = time.monotonic()
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": PROMPT}],
                        reasoning_effort=level,
                        max_completion_tokens=MAX_COMPLETION_TOKENS,
                    )
                    rec["ok"] = True
                    rec["secs"] = round(time.monotonic() - t0, 2)
                    ch = resp.choices[0]
                    rec["finish"] = ch.finish_reason
                    u = resp.usage
                    rec["completion_tokens"] = getattr(u, "completion_tokens", None)
                    det = getattr(u, "completion_tokens_details", None)
                    rec["reasoning_tokens"] = getattr(det, "reasoning_tokens", None) if det else None
                    rec["content_len"] = len(ch.message.content or "")
                except (BadRequestError, APIStatusError) as e:
                    rec["ok"] = False
                    rec["secs"] = round(time.monotonic() - t0, 2)
                    rec["status"] = getattr(e, "status_code", None)
                    msg = str(getattr(e, "message", "") or e)
                    rec["error"] = msg[:180]
                except Exception as e:
                    rec["ok"] = False
                    rec["secs"] = round(time.monotonic() - t0, 2)
                    rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"
                records.append(rec)
                tag = "OK" if rec["ok"] else "ERR"
                print(f"  {model:14s} {level:8s} #{s} {tag} "
                      f"rt={rec.get('reasoning_tokens')} ct={rec.get('completion_tokens')} "
                      f"fin={rec.get('finish')} {rec.get('secs')}s "
                      f"{rec.get('error','')}", flush=True)

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gpt56_probe_records.json")
    out.write_text(json.dumps(records, indent=2))

    # summary table
    print("\n=== SUMMARY: accepted levels + median reasoning_tokens / latency ===")
    print(f"{'model':14s} | " + " | ".join(f"{lv:>8s}" for lv in LEVELS))
    for model in MODELS:
        cells = []
        for level in LEVELS:
            rs = [r for r in records if r["model"] == model and r["level"] == level]
            ok = [r for r in rs if r["ok"]]
            if not ok:
                errs = {r.get("status") for r in rs}
                cells.append(f"400/{list(errs)[0] if errs else 'err'}")
            else:
                rt = [r["reasoning_tokens"] for r in ok if isinstance(r.get("reasoning_tokens"), int)]
                sec = [r["secs"] for r in ok]
                rt_s = f"{int(statistics.median(rt))}" if rt else "na"
                cells.append(f"rt{rt_s}/{statistics.median(sec):.0f}s")
        print(f"{model:14s} | " + " | ".join(f"{c:>8s}" for c in cells))
    print(f"\nWROTE {out}")

if __name__ == "__main__":
    main()
