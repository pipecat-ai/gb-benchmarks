import { create } from "zustand";
import type {
  ReplayBundle,
  ReplayInferenceInput,
  ReplayStep,
  ReplayTurn,
} from "../types";

interface PlaybackState {
  replay: ReplayBundle | null;
  currentStepIndex: number;
  isPlaying: boolean;
  playbackSpeedMs: number;
  liveSource: string | null;
  clearReplay: () => void;
  loadReplay: (replay: ReplayBundle, liveSource?: string | null) => void;
  updateReplay: (replay: ReplayBundle) => void;
  setStepIndex: (index: number) => void;
  stepForward: () => void;
  stepBackward: () => void;
  play: () => void;
  stop: () => void;
  reset: () => void;
  setSpeed: (ms: number) => void;
}

function clampStepIndex(replay: ReplayBundle | null, index: number): number {
  if (!replay || replay.steps.length === 0) {
    return -1;
  }
  return Math.max(-1, Math.min(index, replay.steps.length - 1));
}

export const usePlaybackStore = create<PlaybackState>((set, get) => ({
  replay: null,
  currentStepIndex: -1,
  isPlaying: false,
  playbackSpeedMs: 1200,
  liveSource: null,

  clearReplay: () =>
    set({
      replay: null,
      currentStepIndex: -1,
      isPlaying: false,
      liveSource: null,
    }),

  loadReplay: (replay, liveSource = null) =>
    set({
      replay,
      currentStepIndex: -1,
      isPlaying: false,
      liveSource,
    }),

  updateReplay: (replay) => {
    const { replay: previousReplay, currentStepIndex } = get();
    const previousLastIndex = previousReplay ? previousReplay.steps.length - 1 : -1;
    const shouldFollowTail =
      previousReplay !== null && currentStepIndex >= previousLastIndex;
    set({
      replay,
      currentStepIndex: shouldFollowTail
        ? replay.steps.length - 1
        : clampStepIndex(replay, currentStepIndex),
    });
  },

  setStepIndex: (index) => set((state) => ({ currentStepIndex: clampStepIndex(state.replay, index) })),

  stepForward: () =>
    set((state) => {
      if (!state.replay) {
        return state;
      }
      if (state.currentStepIndex >= state.replay.steps.length - 1) {
        return { ...state, isPlaying: false };
      }
      return { currentStepIndex: state.currentStepIndex + 1 };
    }),

  stepBackward: () =>
    set((state) => ({
      currentStepIndex: clampStepIndex(state.replay, state.currentStepIndex - 1),
    })),

  play: () =>
    set((state) => {
      if (!state.replay || state.replay.steps.length === 0) {
        return state;
      }
      if (state.currentStepIndex >= state.replay.steps.length - 1) {
        return { currentStepIndex: 0, isPlaying: true };
      }
      return { isPlaying: true };
    }),

  stop: () => set({ isPlaying: false }),

  reset: () => set({ currentStepIndex: -1, isPlaying: false }),

  setSpeed: (ms) => set({ playbackSpeedMs: ms }),
}));

export function getCurrentStep(
  replay: ReplayBundle | null,
  stepIndex: number,
): ReplayStep | null {
  if (!replay || stepIndex < 0 || stepIndex >= replay.steps.length) {
    return null;
  }
  return replay.steps[stepIndex];
}

export function getTurnForStep(
  replay: ReplayBundle | null,
  stepIndex: number,
): ReplayTurn | null {
  const step = getCurrentStep(replay, stepIndex);
  if (!replay || !step) {
    return null;
  }
  return replay.turns[step.turn_index] ?? null;
}

export function getCurrentTurn(
  replay: ReplayBundle | null,
  stepIndex: number,
): ReplayTurn | null {
  if (!replay) {
    return null;
  }
  if (stepIndex < 0) {
    return null;
  }
  return getTurnForStep(replay, stepIndex);
}

export function getShipSector(
  replay: ReplayBundle | null,
  stepIndex: number,
): number | null {
  if (!replay) {
    return null;
  }
  if (stepIndex < 0) {
    return (replay.run.metadata.initial_state as { sector?: number } | undefined)?.sector ?? null;
  }
  return replay.steps[stepIndex]?.state_after.sector ?? null;
}

export function getVisitedSectors(
  replay: ReplayBundle | null,
  stepIndex: number,
): Set<number> {
  const visited = new Set<number>();
  const initialSector = (replay?.run.metadata.initial_state as { sector?: number } | undefined)?.sector;
  if (typeof initialSector === "number") {
    visited.add(initialSector);
  }
  if (!replay || stepIndex < 0) {
    return visited;
  }
  for (let index = 0; index <= stepIndex; index += 1) {
    const sector = replay.steps[index]?.state_after.sector;
    if (typeof sector === "number") {
      visited.add(sector);
    }
  }
  return visited;
}

export function getTraveledEdges(
  replay: ReplayBundle | null,
  stepIndex: number,
): Set<string> {
  const edges = new Set<string>();
  if (!replay || stepIndex < 0) {
    return edges;
  }
  for (let index = 0; index <= stepIndex; index += 1) {
    const step = replay.steps[index];
    if (!step || step.tool_name !== "move" || step.result_status === "error") {
      continue;
    }
    const from = step.state_before.sector;
    const to = step.state_after.sector;
    if (typeof from === "number" && typeof to === "number") {
      edges.add(`${Math.min(from, to)}-${Math.max(from, to)}`);
    }
  }
  return edges;
}

export function getActiveCoursePath(
  replay: ReplayBundle | null,
  stepIndex: number,
): number[] {
  if (!replay || stepIndex < 0) {
    return [];
  }
  for (let index = stepIndex; index >= 0; index -= 1) {
    const path = replay.steps[index]?.details.course_path;
    if (path && path.length > 1) {
      return path;
    }
  }
  return [];
}

export function getInferenceInputForStep(
  replay: ReplayBundle | null,
  stepIndex: number,
): ReplayInferenceInput | null {
  if (!replay) {
    return null;
  }
  const turn = getCurrentTurn(replay, stepIndex);
  if (!turn || typeof turn.inference_index !== "number") {
    return null;
  }
  return (
    replay.inference_inputs.find((input) => input.inference_index === turn.inference_index) ??
    null
  );
}
