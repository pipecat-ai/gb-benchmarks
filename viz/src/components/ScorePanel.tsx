import { formatNumber, formatSignedNumber } from "../format";
import { getCurrentStep, usePlaybackStore } from "../store/playback";

const SCORE_ROWS = [
  ["Mission", "mission_completion_score"],
  ["Trade", "trade_quality_score"],
  ["Path", "path_efficiency_score"],
  ["Tools", "tool_discipline_score"],
  ["Report", "report_quality_score"],
] as const;

export function ScorePanel() {
  const replay = usePlaybackStore((state) => state.replay);
  const currentStepIndex = usePlaybackStore((state) => state.currentStepIndex);

  if (!replay) {
    return null;
  }

  const currentStep = getCurrentStep(replay, currentStepIndex);
  const currentScore = currentStep?.score ?? (currentStepIndex >= 0 ? replay.final_score : null);
  const currentDelta = currentStep?.score_delta ?? null;

  return (
    <section className="rounded-[28px] border border-white/10 bg-black/30 p-5 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
            Score Build
          </div>
          <div className="mt-2 text-4xl font-semibold text-white">
            {formatNumber(currentScore?.primary_score_100 ?? null)}
          </div>
        </div>
        <div className="text-right text-xs uppercase tracking-[0.24em] text-slate-400">
          <div>{currentScore?.exact_final ? "Exact final" : "Provisional"}</div>
          <div className="mt-2 text-sm font-semibold text-slate-200">
            Profit {formatSignedNumber(currentScore?.total_profit_credits ?? null)}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3">
        {SCORE_ROWS.map(([label, key]) => (
          <div
            key={key}
            className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3"
          >
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-300/70">
              {label}
            </div>
            <div className="flex items-center gap-3">
              <div className="text-lg font-semibold text-white">
                {formatNumber((currentScore?.[key] as number | null | undefined) ?? null)}
              </div>
              <div className="w-12 text-right text-xs font-semibold text-lime-200/85">
                {currentDelta && typeof currentDelta[key] === "number"
                  ? formatSignedNumber(currentDelta[key] as number)
                  : ""}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-slate-200/80">
        <div className="flex items-center justify-between">
          <span>Strict success</span>
          <span className={currentScore?.strict_success ? "text-lime-200" : "text-rose-200"}>
            {currentScore?.strict_success ? "YES" : "NO"}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span>Report judge</span>
          <span>{currentScore?.report_judge_reason ?? "—"}</span>
        </div>
      </div>
    </section>
  );
}
