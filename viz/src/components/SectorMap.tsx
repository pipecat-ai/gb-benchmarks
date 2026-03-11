import { EDGES, SECTOR_IDS, SECTOR_POSITIONS, START_SECTOR } from "../data/graph";
import {
  getActiveCoursePath,
  getCurrentStep,
  getShipSector,
  getTraveledEdges,
  getVisitedSectors,
  usePlaybackStore,
} from "../store/playback";
import { SectorLane } from "./SectorLane";
import { SectorNode } from "./SectorNode";

function routeEdgeSet(path: number[]): Set<string> {
  const edges = new Set<string>();
  for (let index = 0; index < path.length - 1; index += 1) {
    const from = path[index];
    const to = path[index + 1];
    edges.add(`${Math.min(from, to)}-${Math.max(from, to)}`);
  }
  return edges;
}

function deltaLabel(step: ReturnType<typeof getCurrentStep>): string | null {
  if (!step) {
    return null;
  }
  if (step.tool_name === "trade") {
    const credits = step.delta.credits ?? 0;
    const sign = credits >= 0 ? "+" : "";
    return `${sign}${credits} cr`;
  }
  if (step.tool_name === "recharge_warp_power") {
    const warp = step.delta.warp ?? 0;
    return `warp ${warp >= 0 ? "+" : ""}${warp}`;
  }
  return null;
}

export function SectorMap() {
  const replay = usePlaybackStore((state) => state.replay);
  const currentStepIndex = usePlaybackStore((state) => state.currentStepIndex);

  const currentStep = getCurrentStep(replay, currentStepIndex);
  const visited = getVisitedSectors(replay, currentStepIndex);
  const traveledEdges = getTraveledEdges(replay, currentStepIndex);
  const activeCourse = getActiveCoursePath(replay, currentStepIndex);
  const highlightedEdges = routeEdgeSet(activeCourse);
  const shipSector = getShipSector(replay, currentStepIndex);
  const startSector =
    ((replay?.run.metadata.initial_state as { sector?: number } | undefined)?.sector ?? START_SECTOR);

  const shipPosition =
    typeof shipSector === "number" ? SECTOR_POSITIONS[shipSector] : undefined;

  const pulseSector =
    currentStep?.tool_name === "trade" || currentStep?.tool_name === "recharge_warp_power"
      ? currentStep.state_after.sector
      : currentStep?.step_type === "error" || currentStep?.step_type === "turn_failure"
        ? currentStep.state_before.sector
        : null;

  const pulseKind =
    currentStep?.tool_name === "trade"
      ? "trade"
      : currentStep?.tool_name === "recharge_warp_power"
        ? "recharge"
        : currentStep?.step_type === "error" || currentStep?.step_type === "turn_failure"
          ? "error"
          : null;

  return (
    <div className="relative h-full overflow-hidden rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(190,242,100,0.16),transparent_34%),linear-gradient(180deg,rgba(2,6,23,0.92),rgba(15,23,42,0.94))] p-3 shadow-[0_25px_90px_rgba(0,0,0,0.4)]">
      <svg viewBox="0 0 1040 620" className="h-full w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <filter id="ship-glow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feFlood floodColor="rgba(103,232,249,0.8)" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="shadow" />
            <feMerge>
              <feMergeNode in="shadow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g opacity="0.18">
          <rect x="22" y="22" width="996" height="576" rx="26" fill="none" stroke="rgba(148,163,184,0.28)" />
        </g>

        {EDGES.map(([from, to]) => {
          const key = `${Math.min(from, to)}-${Math.max(from, to)}`;
          return (
            <SectorLane
              key={key}
              from={from}
              to={to}
              traveled={traveledEdges.has(key)}
              onRoute={highlightedEdges.has(key)}
            />
          );
        })}

        {SECTOR_IDS.map((sector) => (
          <SectorNode
            key={sector}
            sector={sector}
            isCurrent={sector === shipSector}
            isVisited={visited.has(sector)}
            isStart={sector === startSector}
            pulseKind={pulseSector === sector ? pulseKind : null}
          />
        ))}

        {shipPosition && (
          <g
            className="ship-token"
            style={{ transform: `translate(${shipPosition.x}px, ${shipPosition.y}px)` }}
            filter="url(#ship-glow)"
          >
            <circle r="8" fill="#67e8f9" />
            <path d="M 0 -16 L 9 9 L 0 4 L -9 9 Z" fill="#f8fafc" opacity="0.95" />
          </g>
        )}

        {shipPosition && deltaLabel(currentStep) && (
          <text
            key={`delta-${currentStepIndex}`}
            x={shipPosition.x}
            y={shipPosition.y - 26}
            textAnchor="middle"
            className="floating-delta"
            fontSize={13}
            fontWeight="700"
            fontFamily="'IBM Plex Mono', 'SFMono-Regular', monospace"
            fill={currentStep?.tool_name === "trade" ? "#bef264" : "#67e8f9"}
          >
            {deltaLabel(currentStep)}
          </text>
        )}
      </svg>
    </div>
  );
}
