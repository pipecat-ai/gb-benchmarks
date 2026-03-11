import type { ReplayBundle, RunListing } from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchRuns(): Promise<RunListing[]> {
  const payload = await readJson<{ runs: RunListing[] }>(await fetch("/api/runs"));
  return payload.runs;
}

export async function fetchReplayBundle(
  runPath: string,
  judgePath?: string,
): Promise<ReplayBundle> {
  const params = new URLSearchParams({ run_path: runPath });
  if (judgePath) {
    params.set("judge_path", judgePath);
  }
  return readJson<ReplayBundle>(await fetch(`/api/replay?${params.toString()}`));
}

export function openLiveReplay(
  streamPath: string,
  onReplay: (bundle: ReplayBundle) => void,
  onError: (message: string) => void,
): EventSource {
  const params = new URLSearchParams({ stream_path: streamPath });
  const source = new EventSource(`/api/live?${params.toString()}`);
  source.addEventListener("replay", (event) => {
    const payload = JSON.parse((event as MessageEvent<string>).data) as ReplayBundle;
    onReplay(payload);
  });
  source.onerror = () => {
    onError("Live replay stream disconnected.");
  };
  return source;
}
