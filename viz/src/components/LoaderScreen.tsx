import { useEffect, useState } from "react";
import type { RunListing } from "../types";

interface LoaderScreenProps {
  runs: RunListing[];
  loading: boolean;
  error: string | null;
  onLoadCompleted: (runPath: string, judgePath?: string) => void;
  onConnectLive: (streamPath: string) => void;
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1024 * 1024) {
    return `${Math.round(sizeBytes / 1024)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatLocalRunTime(run: RunListing): string {
  const source = run.started_at_utc || run.ended_at_utc || run.modified_at_utc;
  const date = new Date(source);
  if (Number.isNaN(date.getTime())) {
    return "Local time unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function LoaderScreen({
  runs,
  loading,
  error,
  onLoadCompleted,
  onConnectLive,
}: LoaderScreenProps) {
  const [runPath, setRunPath] = useState(runs[0]?.run_path ?? "");
  const [judgePath, setJudgePath] = useState(runs[0]?.judge_path ?? "");
  const [streamPath, setStreamPath] = useState("");

  useEffect(() => {
    if (!runPath && runs[0]?.run_path) {
      setRunPath(runs[0].run_path);
    }
    if (!judgePath && runs[0]?.judge_path) {
      setJudgePath(runs[0].judge_path ?? "");
    }
  }, [judgePath, runPath, runs]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(190,242,100,0.18),transparent_34%),linear-gradient(180deg,#020617,#0f172a_55%,#111827)] px-6 py-8 text-slate-50">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="max-w-3xl">
          <div className="text-xs font-semibold uppercase tracking-[0.32em] text-cyan-200/70">
            Port-To-Port Replay Viewer
          </div>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300/80">
            Completed replays load from <code>run.json</code> plus <code>enriched_runs.jsonl</code>.
            Live mode tails the append-only replay stream emitted by the harness.
          </p>
        </header>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-[0_25px_90px_rgba(0,0,0,0.35)] backdrop-blur">
            <div className="text-xs font-semibold uppercase tracking-[0.28em] text-lime-200/75">
              Completed Replay
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_auto]">
              <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.24em] text-slate-300/65">
                Run JSON
                <input
                  value={runPath}
                  onChange={(event) => setRunPath(event.target.value)}
                  className="rounded-2xl border border-white/12 bg-slate-950/65 px-4 py-3 text-sm tracking-normal text-white outline-none transition focus:border-cyan-300/60"
                  placeholder="/abs/path/to/run.json"
                />
              </label>
              <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.24em] text-slate-300/65">
                Enriched JSONL
                <input
                  value={judgePath}
                  onChange={(event) => setJudgePath(event.target.value)}
                  className="rounded-2xl border border-white/12 bg-slate-950/65 px-4 py-3 text-sm tracking-normal text-white outline-none transition focus:border-cyan-300/60"
                  placeholder="/abs/path/to/enriched_runs.jsonl"
                />
              </label>
              <button
                onClick={() => onLoadCompleted(runPath, judgePath || undefined)}
                className="self-end rounded-2xl bg-cyan-300 px-5 py-3 text-xs font-semibold uppercase tracking-[0.28em] text-slate-950 transition hover:bg-cyan-200"
              >
                Load
              </button>
            </div>

            <div className="mt-6 text-xs font-semibold uppercase tracking-[0.28em] text-slate-300/65">
              Recent Runs
            </div>
            <div className="mt-3 grid gap-3">
              {runs.length === 0 && (
                <div className="rounded-2xl border border-dashed border-white/12 bg-black/20 px-4 py-5 text-sm text-slate-300/70">
                  No discovered runs yet. Start the helper in the repo root and point the form above at a run file.
                </div>
              )}
              {runs.map((run) => (
                <button
                  key={run.run_path}
                  onClick={() => {
                    setRunPath(run.run_path);
                    setJudgePath(run.judge_path ?? "");
                    onLoadCompleted(run.run_path, run.judge_path ?? undefined);
                  }}
                  className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 px-4 py-4 text-left transition hover:border-cyan-300/45 hover:bg-black/30"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-white">{run.name}</div>
                    <div className="mt-1 truncate text-xs uppercase tracking-[0.24em] text-slate-400">
                      {run.model ?? "Unknown model"}
                    </div>
                    <div className="mt-1 text-[11px] uppercase tracking-[0.2em] text-slate-500">
                      {formatLocalRunTime(run)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-lime-300">
                      {run.primary_score_100 ?? "?"}
                    </div>
                    <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">
                      {formatBytes(run.size_bytes)}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-[0_25px_90px_rgba(0,0,0,0.35)] backdrop-blur">
            <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/75">
              Live Replay
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300/80">
              Point the viewer at the harness replay stream, for example a file ending in
              <code> .replay.jsonl</code>. The viewer will stream new turns over SSE and keep the same
              replay UI active as the run grows.
            </p>
            <div className="mt-4 flex flex-col gap-3">
              <input
                value={streamPath}
                onChange={(event) => setStreamPath(event.target.value)}
                className="rounded-2xl border border-white/12 bg-slate-950/65 px-4 py-3 text-sm text-white outline-none transition focus:border-lime-300/60"
                placeholder="/abs/path/to/run.replay.jsonl"
              />
              <button
                onClick={() => onConnectLive(streamPath)}
                className="rounded-2xl bg-lime-300 px-5 py-3 text-xs font-semibold uppercase tracking-[0.28em] text-slate-950 transition hover:bg-lime-200"
              >
                Connect Live
              </button>
            </div>

            {(loading || error) && (
              <div className="mt-6 rounded-2xl border border-white/10 bg-black/25 px-4 py-4 text-sm text-slate-200/80">
                {loading ? "Loading replay bundle..." : error}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
