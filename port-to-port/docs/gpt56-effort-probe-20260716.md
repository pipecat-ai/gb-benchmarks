# GPT-5.6 (luna / sol / terra) — preliminary effort-level probe

_2026-07-16. Preliminary only: chat-completions `reasoning_effort` probe, 2 samples ×
6 levels × 3 versions, no tools, `max_completion_tokens=4000`, default temperature.
Probe: `diagnostics/gpt56_effort_probe.py`._

## The three versions
Discovered from the OpenAI `/v1/models` endpoint (not guessed):
`gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`. Standard OpenAI API
(`OPENAI_API_KEY`), Chat Completions compatible, `reasoning_effort` honored.

## Accepted effort levels (identical for all three)
`reasoning_effort` supports **`none`, `low`, `medium`, `high`, `xhigh`**.
**`minimal` is REJECTED** with HTTP 400: _"Unsupported value: 'reasoning_effort'
does not support 'minimal' with this model. Supported values are: 'none', 'low',
'medium', 'high', and 'xhigh'."_ — note `none` and `xhigh` ARE both supported.

## Effort → reasoning tokens / latency (median of 2 samples; noisy, preliminary)
| Version | none | low | medium | high | xhigh | latency profile |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | rt 0 | rt ~298 | rt ~205 | rt ~371 | **rt ~1021** (spike to 1679) | 1s → 9–13s; deepest reasoner |
| gpt-5.6-sol | rt 0 | rt ~102 | rt ~154 | rt ~107 | rt ~172 | **slow even at low (6–12s)**; modest reasoning |
| gpt-5.6-terra | rt 0 | rt ~65 | rt ~69 | rt ~125 | rt ~201 | 2–3s throughout; fast, light reasoner |

- **`none` = zero reasoning tokens** (reasoning disabled) for all three; a short
  direct answer.
- **Effort scales reasoning** for all three (cleanest for terra: 65→69→125→201).
  luna scales hardest and spikes at `xhigh` (~1000–1700 tokens, ~13s tail). The
  2-sample medians are noisy (e.g. luna low>medium is sampling noise).
- **Latency signature differs sharply**: terra fast (2–3s), luna moderate but a
  fat `xhigh` tail, **sol has high fixed latency even at `low`** (~8s) with only
  modest reasoning — the odd one out (larger model or more overhead).

## How to test on port-to-port (recommended approach)
Same methodology as the Inkling effort (proj-2026-07-15-1700), but simpler — these
are standard OpenAI reasoning models, no Baseten field ambiguity:

1. **Harness branch is REQUIRED — the existing catch-all breaks GPT-5.6.**
   `_apply_benchmark_thinking_mode` routes `gpt-5*` (that isn't `gpt-5.4`) through
   the generic `gpt-5` branch, which maps `--thinking none|minimal → reasoning_effort
   ="minimal"`. **`minimal` 400s on GPT-5.6**, so `--thinking none` and `minimal`
   would both fail. Add a `gpt-5.6` branch (before the `gpt-5` catch-all) that maps
   `none→none` (supported!), `minimal→low`, and passes `low/medium/high/xhigh`
   through unchanged. Validate the level set `{none,low,medium,high,xhigh}`.
2. **Sweep** each of luna/sol/terra at `none/low/medium/high/xhigh` (skip minimal),
   25 rounds/config, natural variant. `mt`/`max_completion_tokens` needs headroom
   for reasoning — luna's `xhigh` already hits ~1700 reasoning tokens on a trivial
   prompt, so use a generous cap (the port-to-port turns are far heavier).
3. **Judge** with `claude-sonnet-4-6`; add rows via the standard rename→symlink→
   `build_primary_leaderboard.py` scratch-diff pipeline; README best-config row.
4. **Latency cutoff:** terra looks comfortably under the README's 4s turn-P50 bar;
   luna/sol may exceed it at higher effort (sol already ~6–12s/turn here) — worth
   confirming before deciding README inclusion.

## Open questions for a full run
- Is `none` (reasoning off) competitive on port-to-port, or do these need `low`+?
- luna vs sol vs terra capability ordering (unknown from codenames) — the run will
  rank them.
- sol's high fixed latency: real, or warm-up? Re-measure with more samples.
