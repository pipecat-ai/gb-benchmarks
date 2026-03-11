import { useEffect, useRef, useState } from "react";
import { fetchReplayBundle, fetchRuns, openLiveReplay } from "./api";
import { ActionLog } from "./components/ActionLog";
import { ContextPanel } from "./components/ContextPanel";
import { LoaderScreen } from "./components/LoaderScreen";
import { PlaybackControls } from "./components/PlaybackControls";
import { ReplayHeader } from "./components/ReplayHeader";
import { ScorePanel } from "./components/ScorePanel";
import { SectorMap } from "./components/SectorMap";
import { usePlaybackStore } from "./store/playback";
import type { RunListing } from "./types";

type AppRoute =
  | { mode: "loader" }
  | { mode: "completed"; runPath: string; judgePath?: string }
  | { mode: "live"; streamPath: string };

type ReplayHistoryState = {
  replay_viewer_route: AppRoute;
};

const LOADER_ROUTE: AppRoute = { mode: "loader" };

function readRouteFromLocation(location: Location): AppRoute {
  const params = new URLSearchParams(location.search);
  const streamPath = params.get("stream");
  if (streamPath) {
    return { mode: "live", streamPath };
  }

  const runPath = params.get("run");
  if (runPath) {
    const judgePath = params.get("judge") ?? undefined;
    return {
      mode: "completed",
      runPath,
      judgePath: judgePath || undefined,
    };
  }

  return LOADER_ROUTE;
}

function buildRouteUrl(route: AppRoute): string {
  const params = new URLSearchParams();
  if (route.mode === "completed") {
    params.set("run", route.runPath);
    if (route.judgePath) {
      params.set("judge", route.judgePath);
    }
  } else if (route.mode === "live") {
    params.set("stream", route.streamPath);
  }

  const query = params.toString();
  const hash = window.location.hash;
  return query
    ? `${window.location.pathname}?${query}${hash}`
    : `${window.location.pathname}${hash}`;
}

function toHistoryState(route: AppRoute): ReplayHistoryState {
  return { replay_viewer_route: route };
}

function isReplayHistoryState(value: unknown): value is ReplayHistoryState {
  if (!value || typeof value !== "object") {
    return false;
  }
  return "replay_viewer_route" in value;
}

export function App() {
  const replay = usePlaybackStore((state) => state.replay);
  const clearReplay = usePlaybackStore((state) => state.clearReplay);
  const loadReplay = usePlaybackStore((state) => state.loadReplay);
  const updateReplay = usePlaybackStore((state) => state.updateReplay);
  const stopPlayback = usePlaybackStore((state) => state.stop);

  const [runs, setRuns] = useState<RunListing[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const liveSourceRef = useRef<EventSource | null>(null);
  const currentRouteRef = useRef<AppRoute>(readRouteFromLocation(window.location));
  const navigationIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    void fetchRuns()
      .then((items) => {
        if (!cancelled) {
          setRuns(items);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function closeLiveSource() {
    if (liveSourceRef.current) {
      liveSourceRef.current.close();
      liveSourceRef.current = null;
    }
  }

  function nextNavigationId(): number {
    navigationIdRef.current += 1;
    return navigationIdRef.current;
  }

  function commitRoute(route: AppRoute, mode: "push" | "replace" | "none") {
    currentRouteRef.current = route;
    if (mode === "push") {
      window.history.pushState(toHistoryState(route), "", buildRouteUrl(route));
      return;
    }
    if (mode === "replace") {
      window.history.replaceState(toHistoryState(route), "", buildRouteUrl(route));
    }
  }

  function resetToLoader() {
    nextNavigationId();
    closeLiveSource();
    stopPlayback();
    clearReplay();
    setLoading(false);
    setLiveStatus(null);
    setError(null);
    currentRouteRef.current = LOADER_ROUTE;
  }

  async function loadCompletedRoute(
    route: Extract<AppRoute, { mode: "completed" }>,
    historyMode: "push" | "replace" | "none",
  ) {
    const navigationId = nextNavigationId();
    closeLiveSource();
    setLoading(true);
    setError(null);
    setLiveStatus(null);
    try {
      const bundle = await fetchReplayBundle(route.runPath, route.judgePath);
      if (navigationId !== navigationIdRef.current) {
        return;
      }
      loadReplay(bundle, null);
      const items = await fetchRuns();
      if (navigationId !== navigationIdRef.current) {
        return;
      }
      setRuns(items);
      commitRoute(route, historyMode);
    } catch (reason) {
      if (navigationId !== navigationIdRef.current) {
        return;
      }
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (navigationId === navigationIdRef.current) {
        setLoading(false);
      }
    }
  }

  function connectLiveRoute(
    route: Extract<AppRoute, { mode: "live" }>,
    historyMode: "push" | "replace" | "none",
  ) {
    if (!route.streamPath.trim()) {
      setError("Provide a replay stream path first.");
      return;
    }
    const navigationId = nextNavigationId();
    closeLiveSource();
    clearReplay();
    setLoading(true);
    setError(null);
    setLiveStatus("Connecting live stream");

    const source = openLiveReplay(
      route.streamPath,
      (bundle) => {
        if (navigationId !== navigationIdRef.current) {
          return;
        }
        if (usePlaybackStore.getState().replay) {
          updateReplay(bundle);
        } else {
          loadReplay(bundle, route.streamPath);
        }
        setLoading(false);
        setLiveStatus("Live connected");
        setError(null);
        commitRoute(route, historyMode);
      },
      (message) => {
        if (navigationId !== navigationIdRef.current) {
          return;
        }
        setLiveStatus("Live disconnected");
        setError(message);
      },
    );
    liveSourceRef.current = source;
  }

  function syncRouteFromLocation(historyMode: "push" | "replace" | "none" = "none") {
    const route = readRouteFromLocation(window.location);
    if (route.mode === "loader") {
      resetToLoader();
      if (historyMode !== "none") {
        commitRoute(LOADER_ROUTE, historyMode);
      }
      return;
    }
    if (route.mode === "completed") {
      void loadCompletedRoute(route, historyMode);
      return;
    }
    connectLiveRoute(route, historyMode);
  }

  function handleLoadCompleted(runPath: string, judgePath?: string) {
    void loadCompletedRoute({ mode: "completed", runPath, judgePath }, "push");
  }

  function handleConnectLive(streamPath: string) {
    connectLiveRoute({ mode: "live", streamPath }, "push");
  }

  function handleBack() {
    if (currentRouteRef.current.mode === "loader") {
      return;
    }
    window.history.back();
  }

  useEffect(() => {
    const initialRoute = readRouteFromLocation(window.location);
    if (!isReplayHistoryState(window.history.state)) {
      if (initialRoute.mode === "loader") {
        window.history.replaceState(toHistoryState(LOADER_ROUTE), "", buildRouteUrl(LOADER_ROUTE));
      } else {
        window.history.replaceState(toHistoryState(LOADER_ROUTE), "", buildRouteUrl(LOADER_ROUTE));
        window.history.pushState(toHistoryState(initialRoute), "", buildRouteUrl(initialRoute));
      }
    }

    syncRouteFromLocation();

    function handlePopState() {
      syncRouteFromLocation();
    }

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
      closeLiveSource();
    };
  }, []);

  if (!replay) {
    return (
      <LoaderScreen
        runs={runs}
        loading={loading}
        error={error}
        onLoadCompleted={handleLoadCompleted}
        onConnectLive={handleConnectLive}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(190,242,100,0.12),transparent_34%),linear-gradient(180deg,#020617,#0f172a_45%,#111827)] px-4 py-4 text-slate-50 lg:px-6">
      <div className="mx-auto flex w-full max-w-none flex-col gap-4">
        <ReplayHeader onBack={handleBack} liveStatus={liveStatus} />

        {replay.warnings.length > 0 && (
          <div className="rounded-[24px] border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100/90">
            {replay.warnings[0]}
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(760px,1.18fr)_minmax(340px,0.72fr)_minmax(420px,0.95fr)]">
          <div className="flex min-h-0 flex-col gap-4">
            <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="min-h-[440px]">
                <SectorMap />
              </div>
              <ScorePanel />
            </div>
            <PlaybackControls />
          </div>
          <div className="min-h-[520px] xl:min-h-[calc(100vh-8rem)]">
            <ActionLog />
          </div>
          <div className="min-h-[520px] xl:min-h-[calc(100vh-8rem)]">
            <ContextPanel />
          </div>
        </div>
      </div>
    </div>
  );
}
