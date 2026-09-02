export interface Materialgruppe {
  id: number;
  gruppe: string;
  bezeichnung: string;
  schmelzdichte_kg_m3: number;
  waermekapazitaet_j_kg_k: number;
  waermeleitfaehigkeit_w_m_k: number;
  werkzeugtemperatur_c: number;
  schmelzetemperatur_c: number;
  entformungstemperatur_c: number;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}
