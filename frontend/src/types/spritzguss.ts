export interface VeredelungZuordnungInput {
  veredelungsschritt_id: number;
  reihenfolge: number;
  aktiv: boolean;
  mengenfaktor: number;
}

export interface VeredelungZuordnung extends VeredelungZuordnungInput {
  id: number;
  kalkulation_id: number;
  snapshot_bezeichnung: string;
  snapshot_veredelungsart: string;
  snapshot_kosten_inkl_ausschuss: number;
  kosten_gesamt: number;
}

export interface SpritzgussErgebnis {
  materialgewicht_kg: number;
  materialkosten: number;
  materialkosten_inkl_ausschuss: number;
  materialgemeinkosten: number;
  materialkosten_gesamt: number;
  maschinenkosten: number;
  fertigungslohn: number;
  fertigungsgemeinkosten: number;
  werkzeugkostenanteil: number;
  werkzeug_einmalzahlung: number;
  herstellkosten: number;
  vvgk: number;
  selbstkosten: number;
  gewinn: number;
  nettoverkaufspreis: number;
  skonto: number;
  verkaufspreis: number;
  spritzguss_gesamt?: number;
  veredelung_gesamt?: number;
  endpreis_je_stueck?: number;
  veredelung_schritte?: Array<{
    veredelungsschritt_id: number;
    bezeichnung: string;
    veredelungsart: string;
    reihenfolge: number;
    aktiv: boolean;
    mengenfaktor: number;
    kosten_inkl_ausschuss: number;
    kosten_gesamt: number;
  }>;
}

export interface SpritzgussBloecke {
  material: Record<string, number>;
  fertigung: Record<string, number>;
  werkzeug: Record<string, number>;
  gemeinkosten: Record<string, number>;
  verkaufspreis: Record<string, number>;
  veredelung?: Record<string, number>;
  zusammenfassung?: Record<string, number>;
}

export interface SpritzgussCalcResponse {
  ergebnis: SpritzgussErgebnis;
  bloecke: SpritzgussBloecke;
  veredelung_zuordnungen?: VeredelungZuordnung[];
}

export type WerkzeugAbrechnungsart = "amortisation" | "einmalzahlung";

export interface SpritzgussFormData {
  teilebezeichnung: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;

  material_id: number | null;
  schussgewicht_g: number;
  teilegewicht_netto_g: number;
  ausschussquote_pct: number;
  materialpreis_pro_kg: number;

  maschine_id: number | null;
  zykluszeit_s: number;
  kavitaeten: number;
  maschinenstundensatz: number;

  lohnkosten_id: number | null;
  lohnstundensatz: number;

  werkzeug_abrechnungsart: WerkzeugAbrechnungsart;
  werkzeugkosten_eur: number;
  amortisationsvolumen: number | null;

  mgk_pct: number;
  fgk_pct: number;
  vvgk_pct: number;
  gewinn_pct: number;
  skonto_pct: number;

  notizen: string;
  aktiv: boolean;
}

export interface SpritzgussKalkulation extends SpritzgussFormData {
  id: number;
  ergebnis: SpritzgussErgebnis | null;
  ergebnis_bloecke: SpritzgussBloecke | null;
  veredelung_zuordnungen?: VeredelungZuordnung[];
  created_at: string;
  updated_at: string;
}

export interface SpritzgussListItem {
  id: number;
  teilebezeichnung: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;
  verkaufspreis: number | null;
  updated_at: string;
  aktiv: boolean;
}

export const emptySpritzgussForm = (): SpritzgussFormData => ({
  teilebezeichnung: "",
  teilenummer: "",
  kunde: "",
  projekt: "",
  jahresstueckzahl: 0,
  material_id: null,
  schussgewicht_g: 0,
  teilegewicht_netto_g: 0,
  ausschussquote_pct: 0,
  materialpreis_pro_kg: 0,
  maschine_id: null,
  zykluszeit_s: 0,
  kavitaeten: 1,
  maschinenstundensatz: 0,
  lohnkosten_id: null,
  lohnstundensatz: 0,
  werkzeug_abrechnungsart: "amortisation",
  werkzeugkosten_eur: 0,
  amortisationsvolumen: 1,
  mgk_pct: 0,
  fgk_pct: 0,
  vvgk_pct: 0,
  gewinn_pct: 0,
  skonto_pct: 0,
  notizen: "",
  aktiv: true,
});
