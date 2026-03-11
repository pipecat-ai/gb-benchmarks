/** Sector adjacency graph — source of truth: mini-rl-env.py lines 188-214 */
export const GRAPH: Record<number, number[]> = {
  0: [4874],
  172: [220],
  200: [2469],
  220: [172],
  916: [3885, 4884],
  1344: [2469, 3900, 4874],
  1487: [1928],
  1611: [1928, 2058],
  1928: [1487, 1611, 4382],
  2058: [1611, 2831],
  2217: [2266],
  2266: [3080, 3313, 3885],
  2469: [200, 1344, 4884],
  2766: [3494],
  2831: [2058, 3494, 4822],
  3080: [2266, 3313],
  3313: [2266, 3080],
  3494: [2766, 2831, 4874],
  3871: [3885],
  3885: [916, 2266, 3871],
  3900: [1344],
  4382: [1928],
  4822: [2831],
  4874: [0, 1344, 3494],
  4884: [916, 2469, 2833],
};

// Sector 2833 is referenced by 4884 but has no own entry — include as leaf
const ALL_SECTORS = new Set<number>();
for (const [sector, neighbors] of Object.entries(GRAPH)) {
  ALL_SECTORS.add(Number(sector));
  for (const n of neighbors) ALL_SECTORS.add(n);
}

/** All unique edges as [a, b] pairs (a < b) */
export const EDGES: [number, number][] = [];
const seen = new Set<string>();
for (const [sector, neighbors] of Object.entries(GRAPH)) {
  const s = Number(sector);
  for (const n of neighbors) {
    const key = `${Math.min(s, n)}-${Math.max(s, n)}`;
    if (!seen.has(key)) {
      seen.add(key);
      EDGES.push([Math.min(s, n), Math.max(s, n)]);
    }
  }
}

/** Disconnected sectors (172, 220) — not reachable from main graph */
export const DISCONNECTED = new Set([172, 220]);

/** Mega port sector */
export const MEGA_PORT_SECTOR = 1611;

/** Start sector */
export const START_SECTOR = 3080;

/**
 * Hand-tuned (x, y) positions in a 0 0 1000 600 SVG viewBox.
 * Main corridor runs left → right. Leaf nodes branch above/below.
 */
export const SECTOR_POSITIONS: Record<number, { x: number; y: number }> = {
  // Main corridor (left to right)
  3080: { x: 65, y: 300 },
  2266: { x: 175, y: 300 },
  3885: { x: 295, y: 300 },
  916: { x: 395, y: 300 },
  4884: { x: 490, y: 300 },
  2469: { x: 580, y: 300 },
  1344: { x: 660, y: 300 },
  4874: { x: 735, y: 300 },
  3494: { x: 805, y: 300 },
  2831: { x: 870, y: 300 },
  2058: { x: 925, y: 300 },
  1611: { x: 970, y: 300 },

  // Leaf nodes branching off corridor
  3313: { x: 105, y: 210 }, // connects 3080 ↔ 2266
  2217: { x: 175, y: 190 }, // connects 2266
  3871: { x: 295, y: 410 }, // connects 3885
  2833: { x: 490, y: 410 }, // connects 4884 (leaf)
  200: { x: 580, y: 190 }, // connects 2469
  3900: { x: 660, y: 410 }, // connects 1344
  0: { x: 735, y: 190 }, // connects 4874

  2766: { x: 805, y: 410 }, // connects 3494
  4822: { x: 870, y: 410 }, // connects 2831

  // 1611 sub-tree (above/right)
  1928: { x: 945, y: 195 }, // connects 1611, 1487, 4382
  1487: { x: 905, y: 115 }, // connects 1928
  4382: { x: 975, y: 115 }, // connects 1928

  // Isolated pair (bottom-left, dimmed)
  172: { x: 65, y: 530 },
  220: { x: 165, y: 530 },
};

export const SECTOR_IDS = Object.keys(SECTOR_POSITIONS).map(Number);
