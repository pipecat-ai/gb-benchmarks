import { useEffect, useEffectEvent } from "react";
import { usePlaybackStore } from "../store/playback";

const SPEEDS = [
  { label: "Slow", ms: 1600 },
  { label: "Normal", ms: 1200 },
  { label: "Fast", ms: 700 },
];

export function PlaybackControls() {
  const replay = usePlaybackStore((state) => state.replay);
  const currentStepIndex = usePlaybackStore((state) => state.currentStepIndex);
  const isPlaying = usePlaybackStore((state) => state.isPlaying);
  const playbackSpeedMs = usePlaybackStore((state) => state.playbackSpeedMs);
  const play = usePlaybackStore((state) => state.play);
  const stop = usePlaybackStore((state) => state.stop);
  const reset = usePlaybackStore((state) => state.reset);
  const stepForward = usePlaybackStore((state) => state.stepForward);
  const stepBackward = usePlaybackStore((state) => state.stepBackward);
  const setStepIndex = usePlaybackStore((state) => state.setStepIndex);
  const setSpeed = usePlaybackStore((state) => state.setSpeed);

  const advanceStep = useEffectEvent(() => {
    stepForward();
  });

  useEffect(() => {
    if (!isPlaying) {
      return;
    }
    const id = window.setInterval(() => {
      advanceStep();
    }, playbackSpeedMs);
    return () => window.clearInterval(id);
  }, [advanceStep, isPlaying, playbackSpeedMs]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        stepForward();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        stepBackward();
      } else if (event.key === " ") {
        event.preventDefault();
        if (isPlaying) {
          stop();
        } else {
          play();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isPlaying, play, stepBackward, stepForward, stop]);

  if (!replay) {
    return null;
  }

  const totalSteps = replay.steps.length;
  const displayStep = totalSteps === 0 ? 0 : currentStepIndex + 1;
  const progress = totalSteps > 0 ? ((currentStepIndex + 1) / totalSteps) * 100 : 0;

  return (
    <div className="rounded-[28px] border border-white/10 bg-black/35 px-4 py-3 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur">
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={play}
          className="rounded-full bg-lime-300 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-950 transition hover:bg-lime-200"
        >
          Play
        </button>
        <button
          onClick={stop}
          className="rounded-full border border-white/12 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-white/80 transition hover:border-white/30 hover:text-white"
        >
          Stop
        </button>
        <button
          onClick={reset}
          className="rounded-full border border-white/12 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-white/80 transition hover:border-white/30 hover:text-white"
        >
          Reset
        </button>
        <button
          onClick={stepBackward}
          disabled={currentStepIndex < 0}
          className="rounded-full border border-white/12 px-3 py-2 text-sm text-white/80 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
        >
          ←
        </button>
        <button
          onClick={stepForward}
          disabled={currentStepIndex >= totalSteps - 1}
          className="rounded-full border border-white/12 px-3 py-2 text-sm text-white/80 transition hover:border-white/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
        >
          →
        </button>

        <div className="ml-auto flex items-center gap-2">
          {SPEEDS.map((speed) => (
            <button
              key={speed.ms}
              onClick={() => setSpeed(speed.ms)}
              className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] transition ${
                playbackSpeedMs === speed.ms
                  ? "bg-cyan-300 text-slate-950"
                  : "border border-white/12 text-white/60 hover:border-white/25 hover:text-white"
              }`}
            >
              {speed.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div
          className="relative h-2 flex-1 cursor-pointer rounded-full bg-white/10"
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            setStepIndex(Math.round(ratio * totalSteps) - 1);
          }}
        >
          <div
            className="absolute left-0 top-0 h-full rounded-full bg-[linear-gradient(90deg,rgba(103,232,249,0.95),rgba(190,242,100,0.95))] transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="w-28 text-right text-xs uppercase tracking-[0.25em] text-white/55">
          Step {displayStep}/{totalSteps}
        </div>
      </div>
    </div>
  );
}
