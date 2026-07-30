# GPT-5.6 Sol natural-prompt trade notes

_2026-07-18. Based on 25 natural-prompt production runs at each of `none`,
`medium`, and `xhigh`, judged and scored with the canonical port-to-port rubric._

## Result

| Effort | Primary median | Trade /15 avg | Task complete |
|---|---:|---:|---:|
| none | 85 | 0.00 | 100% |
| medium | 87 | 3.64 | 100% |
| xhigh | 85 | 2.04 | 100% |

This is not a navigation or service failure. All 75 runs completed the mission,
received full mission and path credit, and returned complete Responses API
outputs at the requested effort. Nearly all score loss is trade quality.

## Dominant failure mode

Sol sells the free starting quantum foam for 330 credits, then usually buys 30
retro-organics for 240 credits even though it has identified no later on-route
buyer. The purchase fills every hold and blocks the profitable
neuro-symbolics route (`buy @30`, `sell @52`). After the 66-credit recharge,
the common run finishes with only `330 - 240 - 66 = 24` credits of profit and
30 unsold retro-organics.

The bad purchase occurred in 25/25 `none`, 24/25 `medium`, and 23/25 `xhigh`
runs. Only one `medium` and one `xhigh` run executed the full optimal strategy
for 2,244 credits of whole-trip profit. More reasoning did not reliably correct
the opening decision.

## What stronger trajectories do

| Model/config | Avoid initial RO | Use NS at sector 4874 | Trade /15 avg |
|---|---:|---:|---:|
| GPT-5.4 medium | 25/25 | 25/25 | 12.24 |
| GLM-5.2 xhigh | 22/25 | 23/25 | 11.04 |
| Claude Sonnet 5 xhigh | 22/25 | 22/25 | 9.64 |
| GPT-5.6 Terra xhigh | 24/25 | 18/25 | 7.40 |
| GPT-5.6 Sol medium | 1/25 | 1/25 | 3.64 |

Better models either inspect the route-wide market first or follow a
conservative rule: keep holds empty until a profitable exit is known. They
then cycle full NS loads at 4874 -> 2831, 1611 -> 2831, and 4874 -> 3080.
When other models make Sol's initial RO purchase, their scores also fall; the
difference is how frequently they enter that policy mode.

## Interpretation

The result is best read as a Sol-specific weakness in route-aware inventory
planning under the natural prompt, not as a broad capability or integration
failure. The prompt says to trade optimally but does not explicitly say that
ending cargo has no terminal value or that cargo should be bought only with a
known profitable on-route exit. GPT-5.4 handles that inference consistently;
Sol usually applies a local "cheap means buy" heuristic instead.

The single-run qualification sweep overstated `xhigh`: its 92-point sample came
from a relatively rare better policy mode, while the 25-run median was 85.
Future effort selection should use multiple samples. A useful separate
diagnostic is a small A/B adding the explicit known-exit and terminal-cargo
rules; it should not replace the canonical natural-prompt leaderboard result.

Canonical summary: `leaderboards/leaderboard-natural.md`.
