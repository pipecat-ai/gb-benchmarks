import { SECTOR_POSITIONS } from "../data/graph";

interface SectorLaneProps {
  from: number;
  to: number;
  traveled: boolean;
  onRoute: boolean;
}

export function SectorLane({ from, to, traveled, onRoute }: SectorLaneProps) {
  const start = SECTOR_POSITIONS[from];
  const end = SECTOR_POSITIONS[to];
  if (!start || !end) {
    return null;
  }

  const stroke = onRoute
    ? "rgba(103,232,249,0.85)"
    : traveled
      ? "rgba(190,242,100,0.65)"
      : "rgba(148,163,184,0.22)";

  const width = onRoute ? 4 : traveled ? 2.6 : 1.4;

  return (
    <line
      x1={start.x}
      y1={start.y}
      x2={end.x}
      y2={end.y}
      stroke={stroke}
      strokeWidth={width}
      strokeLinecap="round"
      className="sector-lane"
    />
  );
}
