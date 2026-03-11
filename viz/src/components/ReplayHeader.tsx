import { formatNumber } from "../format";
import { usePlaybackStore } from "../store/playback";

interface ReplayHeaderProps {
  onBack: () => void;
  liveStatus: string | null;
}

export function ReplayHeader({ onBack, liveStatus }: ReplayHeaderProps) {
  const replay = usePlaybackStore((state) => state.replay);
  if (!replay) {
    return null;
  }

  const config = replay.run.config;
  const metadata = replay.run.metadata;
  const finalScore = replay.final_score;
  const model = String(config.model ?? replay.judge?.model ?? "unknown");
  const provider = String(config.provider ?? "unknown");
  const runPath = String(replay.source.run_path ?? "");
  const liveLabel = replay.live ? liveStatus ?? "Live connected" : null;

  return (
    <div className="rounded-[32px] border border-white/10 bg-black/28 px-5 py-4 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur">
      <div className="flex flex-wrap items-center gap-4">
        <button
          onClick={onBack}
          className="rounded-full border border-white/12 px-3 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-white/70 transition hover:border-white/30 hover:text-white"
        >
          Back
        </button>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
            {provider} / {model}
          </div>
          <div className="truncate text-lg font-semibold text-white">
            {runPath.split("/").pop() || "Replay"}
          </div>
          <div className="truncate text-xs uppercase tracking-[0.24em] text-slate-400">
            {String(metadata.run_id ?? "")}
          </div>
        </div>
        {liveLabel && (
          <div className="rounded-full border border-lime-300/35 bg-lime-300/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-lime-200">
            {liveLabel}
          </div>
        )}
        {finalScore && (
          <div className="rounded-[24px] bg-[linear-gradient(135deg,rgba(8,145,178,0.35),rgba(163,230,53,0.3))] px-4 py-3 text-right">
            <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-200/75">
              Final Primary
            </div>
            <div className="text-3xl font-semibold text-white">
              {formatNumber(finalScore.primary_score_100 ?? null)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
