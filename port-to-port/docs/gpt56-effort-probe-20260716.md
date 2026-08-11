# GPT-5.6 (luna / sol / terra) — preliminary effort-level probe

_2026-07-16. Preliminary only: chat-completions `reasoning_effort` probe, 2 samples ×
6 levels × 3 versions, no tools, `max_completion_tokens=4000`, default temperature.
Probe: `diagnostics/gpt56_effort_probe.py`._

## The three versions
Discovered from the OpenAI `/v1/models` endpoint (not guessed):
`gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`. Standard OpenAI API
(`OPENAI_API_KEY`), Chat Completions compatible, `reasoning_effort` honored.

## ⚠️ Correction — the benchmark path is the RESPONSES API, not chat completions
The probe below used `/v1/chat/completions` **without tools**. The port-to-port
benchmark **always sends tools**, and gpt-5.6 (like gpt-5.4) **rejects
`reasoning_effort` with tools on `/v1/chat/completions`**:
> `400 — Function tools with reasoning_effort are not supported for
> gpt-5.6-terra in /v1/chat/completions. To use function tools [use the
> Responses API].`
So the correct integration is the **OpenAI Responses API** with `reasoning:
{effort}` (the guide: `../aiewf-eval/src/multi_turn_eval/pipelines/base.py:646-698`,
which routes `gpt-4.1 / gpt-5.4 / gpt-5.6` to `OpenAIResponsesLLMService`).
The port-to-port harness already has that service (`openai_responses_service.py`),
today gated to `gpt-5.4` in `llm_factory._is_openai_responses_model`.

**Effort levels via the Responses API (with tools) — empirically confirmed for
gpt-5.6: `none / low / medium / high / xhigh / max`** (gpt-5.6 adds `max` over
gpt-5.4's `none/low/medium/high/xhigh`; `low`, `xhigh`, and `max` all completed a
tool call in testing). `service_tier="priority"` per the guide.

## Chat-completions probe (no tools) — accepted levels
Via `/v1/chat/completions` **without tools**, `reasoning_effort` supports
**`none`, `low`, `medium`, `high`, `xhigh`** for all three; **`minimal` is
REJECTED** (_"does not support 'minimal' … Supported values are: none, low,
medium, high, and xhigh"_). Useful only as a rough reasoning-depth signal — the
benchmark uses the Responses path above.

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

## How to test on port-to-port (recommended approach — Responses API)
Mirror how the harness already runs **gpt-5.4** (which uses the same Responses +
`reasoning:{effort}` path) and how aiewf-eval routes gpt-5.6:

1. **Route gpt-5.6 to the Responses service.** Extend
   `llm_factory._is_openai_responses_model` (currently
   `openai_base_url is None and startswith("gpt-5.4")`) to also match `gpt-5.6`,
   so luna/sol/terra use `OpenAIResponsesLLMService`.
2. **Add a gpt-5.6 thinking-mode branch** in `_apply_benchmark_thinking_mode`
   (before the `gpt-5` catch-all), modeled on the existing gpt-5.4 branch, setting
   `extra["reasoning"] = {"effort": effort}` (Responses shape). Map benchmark
   thinking → effort over the level set **`{none, low, medium, high, xhigh, max}`**
   (e.g. `none→none, minimal→low, low/medium/high→passthrough, xhigh→xhigh`, and
   decide whether to reach `max` via a config). Set `service_tier="priority"`.
   Validate the level set; do NOT let gpt-5.6 fall into the `gpt-5` catch-all,
   which sends `reasoning_effort` on chat.completions — **rejected with tools.**
3. **Sweep** each of luna/sol/terra across the chosen effort levels, 25 rounds/
   config, natural variant, with generous `max_output_tokens` headroom (luna's
   `xhigh` already hits ~1700 reasoning tokens on a trivial prompt; benchmark turns
   are far heavier).
4. **Judge** with `claude-sonnet-4-6`; add rows via the standard rename→symlink→
   `build_primary_leaderboard.py` scratch-diff pipeline; README best-config row.
5. **Latency cutoff:** terra looks comfortably under the README's 4s turn-P50 bar;
   luna/sol may exceed it at higher effort (sol already ~6–12s/turn in the no-tools
   probe) — confirm on the real Responses+tools path before deciding README inclusion.

## gpt-5.5 note
aiewf-eval special-cases only `gpt-5.4` and `gpt-5.6` for Responses; **gpt-5.5 is
not handled** there and would fall to its `gpt-5` default (chat.completions,
`reasoning_effort="minimal"`) — which likely also breaks with tools + may reject
`minimal`. gpt-5.5 has never been benchmarked in either repo; it needs its own
Responses-vs-chat + level probe before a run.

## Open questions for a full run
- Is `none` (reasoning off) competitive on port-to-port, or do these need `low`+?
- luna vs sol vs terra capability ordering (unknown from codenames) — the run will
  rank them.
- sol's high fixed latency: real, or warm-up? Re-measure with more samples.
