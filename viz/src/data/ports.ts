/** Port definitions — source of truth: mini-rl-env.py lines 216-240 */
export interface PortDef {
  name: string;
  buys: Record<string, number>;
  sells: Record<string, number>;
  isMega: boolean;
}

export const PORTS: Record<number, PortDef> = {
  3080: {
    name: "BSB",
    buys: { quantum_foam: 33, neuro_symbolics: 52 },
    sells: { retro_organics: 8 },
    isMega: false,
  },
  1611: {
    name: "MEGA SSS",
    buys: {},
    sells: { quantum_foam: 19, retro_organics: 8, neuro_symbolics: 30 },
    isMega: true,
  },
  1928: {
    name: "BBS",
    buys: { quantum_foam: 32, retro_organics: 13 },
    sells: { neuro_symbolics: 30 },
    isMega: false,
  },
  2831: {
    name: "SSB",
    buys: { neuro_symbolics: 52 },
    sells: { quantum_foam: 19, retro_organics: 8 },
    isMega: false,
  },
  4874: {
    name: "SSS",
    buys: {},
    sells: { quantum_foam: 19, retro_organics: 8, neuro_symbolics: 30 },
    isMega: false,
  },
};

export const PORT_SECTORS = new Set(Object.keys(PORTS).map(Number));
