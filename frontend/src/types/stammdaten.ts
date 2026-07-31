export interface Material {
  id: number;
  bezeichnung: string;
  material_nr: string;
  preis_pro_kg: number;
  dichte: number;
  waehrung: string;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}

export interface Maschine {
  id: number;
  bezeichnung: string;
  maschinen_nr: string;
  stundensatz: number;
  schliesskraft_t: number;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}

export interface Lohnkosten {
  id: number;
  bezeichnung: string;
  kosten_pro_stunde: number;
  kostenstelle: string;
  gueltig_ab: string;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}

export interface Zuschlagssatz {
  id: number;
  bezeichnung: string;
  satz_prozent: number;
  typ: string;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}
