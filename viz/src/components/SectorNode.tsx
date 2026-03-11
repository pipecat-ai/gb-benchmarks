import { DISCONNECTED, MEGA_PORT_SECTOR, SECTOR_POSITIONS } from "../data/graph";
import { PORTS } from "../data/ports";

interface SectorNodeProps {
  sector: number;
  isCurrent: boolean;
  isVisited: boolean;
  isStart: boolean;
  pulseKind: "trade" | "recharge" | "error" | null;
}

const RADIUS = 20;

export function SectorNode({
  sector,
  isCurrent,
  isVisited,
  isStart,
  pulseKind,
}: SectorNodeProps) {
  const position = SECTOR_POSITIONS[sector];
  if (!position) {
    return null;
  }

  const port = PORTS[sector];
  const isMega = sector === MEGA_PORT_SECTOR;
  const isDisconnected = DISCONNECTED.has(sector);

  const fill = isCurrent
    ? "rgba(34,211,238,0.18)"
    : isMega && isVisited
      ? "rgba(250,204,21,0.2)"
      : isVisited
        ? "rgba(190,242,100,0.14)"
        : "rgba(15,23,42,0.72)";

  const stroke = isCurrent
    ? "rgba(103,232,249,1)"
    : isMega
      ? "rgba(250,204,21,0.85)"
      : isVisited
        ? "rgba(190,242,100,0.85)"
        : "rgba(226,232,240,0.35)";

  const labelColor = isCurrent ? "#67e8f9" : isDisconnected ? "rgba(148,163,184,0.45)" : "#f8fafc";

  return (
    <g>
      {pulseKind && (
        <circle
          key={`${sector}-${pulseKind}`}
          className={`sector-pulse sector-pulse-${pulseKind}`}
          cx={position.x}
          cy={position.y}
          r={RADIUS + 3}
        />
      )}
      <circle
        cx={position.x}
        cy={position.y}
        r={RADIUS}
        fill={fill}
        stroke={stroke}
        strokeWidth={isCurrent ? 3 : isStart ? 2.2 : 1.5}
        strokeDasharray={isStart && !isCurrent ? "5 4" : undefined}
        opacity={isDisconnected ? 0.5 : 1}
        className="sector-node"
      />
      <text
        x={position.x}
        y={position.y + 1}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={10}
        fontFamily="'IBM Plex Mono', 'SFMono-Regular', monospace"
        fill={labelColor}
      >
        {sector}
      </text>
      {port && (
        <text
          x={position.x}
          y={position.y + RADIUS + 12}
          textAnchor="middle"
          fontSize={8}
          fontFamily="'IBM Plex Mono', 'SFMono-Regular', monospace"
          fontWeight="700"
          fill={isMega ? "rgba(250,204,21,0.95)" : "rgba(226,232,240,0.72)"}
        >
          {port.name}
        </text>
      )}
    </g>
  );
}
