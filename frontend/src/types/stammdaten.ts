export interface Material {
  id: number;
  bezeichnung: string;
  material_nr: string;
  preis_pro_kg: number;
  dichte: number;
  injection_pressure_kg_cm2: number;
  waehrung: string;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}

export interface Land {
  id: number;
  code: string;
  name: string;
  aktiv: boolean;
  created_at: string;
  updated_at: string;
}

export interface Werk {
  id: number;
  land_id: number;
  code: string;
  name: string;
  currency: string;
  fx_to_eur: number;
  aktiv: boolean;
  arbeitstage_pro_jahr?: number | null;
  produktionsintervall_arbeitstage?: number | null;
  schichten_pro_tag?: number | null;
  stunden_pro_schicht?: number | null;
  oee?: number | null;
  space_cost_satz_pro_sqm_jahr?: number | null;
  abschreibungsdauer_jahre?: number | null;
  zinssatz?: number | null;
  versicherungssatz?: number | null;
  instandhaltungssatz?: number | null;
  strompreis?: number | null;
  druckluftpreis?: number | null;
  kuehlwasserpreis?: number | null;
  created_at: string;
  updated_at: string;
}

export interface WerkZuschlag {
  id: number;
  werk_id: number;
  typ: string;
  bezeichnung: string;
  satz_prozent: number;
  kostenbasis: string;
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
  werk_id?: number | null;
  maschinentyp?: string | null;
  variante?: string | null;
  source_currency?: string | null;
  arbeitstage_pro_jahr?: number | null;
  schichten_pro_tag?: number | null;
  stunden_pro_schicht?: number | null;
  oee?: number | null;
  investment?: number | null;
  flaeche_sqm?: number | null;
  space_cost_satz_pro_sqm_jahr?: number | null;
  abschreibungsdauer_jahre?: number | null;
  zinssatz?: number | null;
  versicherungssatz?: number | null;
  instandhaltungssatz?: number | null;
  stromverbrauch_kwh_h?: number | null;
  strompreis?: number | null;
  druckluftverbrauch_m3_h?: number | null;
  druckluftpreis?: number | null;
  kuehlwasserverbrauch_m3_h?: number | null;
  kuehlwasserpreis?: number | null;
  setup_zeit_min?: number | null;
  setup_mitarbeiter?: number | null;
  jahresstunden?: number | null;
  space_costs_pro_stunde?: number | null;
  abschreibung_pro_stunde?: number | null;
  zinsen_pro_stunde?: number | null;
  versicherung_pro_stunde?: number | null;
  instandhaltung_pro_stunde?: number | null;
  energie_pro_stunde?: number | null;
  stundensatz_source?: number | null;
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
  werk_id?: number | null;
  rolle?: string;
  source_currency?: string | null;
  source_rate?: number | null;
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
