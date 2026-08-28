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
  /** Materialausschuss-Betrag (inkl. Ausschuss − direkt) */
  materialausschuss_betrag?: number;
  materialgemeinkosten: number;
  /** Alias fachlich: Materialkosten inkl. MGK (MGK genau einmal) */
  materialkosten_gesamt: number;
  mgk_basis?: number;
  maschinenkosten: number;
  fertigungslohn: number;
  fertigungsgemeinkosten: number;
  fgk_basis?: number;
  werkzeugkostenanteil: number;
  werkzeug_einmalzahlung: number;
  herstellkosten: number;
  vvgk: number;
  selbstkosten: number;
  gewinn: number;
  nettoverkaufspreis: number;
  skonto: number;
  verkaufspreis: number;
  applied_mgk_pct?: number;
  applied_fgk_pct?: number;
  applied_vvgk_pct?: number;
  applied_gewinn_pct?: number;
  applied_skonto_pct?: number;
  bruttokapazitaet_exakt?: number;
  bruttokapazitaet?: number;
  nettokapazitaet?: number;
  losgroesse_modus?: "automatisch" | "manuell";
  losgroesse_automatisch?: number | null;
  losgroesse_aktiv?: number | null;
  losgroesse_manuell?: number | null;
  losgroesse_jahresbedarf?: number | null;
  produktionsintervall_arbeitstage?: number | null;
  arbeitstage_pro_jahr?: number | null;
  losgroesse_hinweis?: string | null;
  setup_kosten_je_teil?: number;
  setup_maschinenkosten_je_teil?: number;
  setup_lohnkosten_je_teil?: number;
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
  material: Record<string, number | string | null>;
  fertigung: Record<string, number | string | null>;
  werkzeug: Record<string, number | string | null>;
  gemeinkosten: Record<string, number | string | null>;
  verkaufspreis: Record<string, number | string | null>;
  veredelung?: Record<string, number | string | null>;
  zusammenfassung?: Record<string, number | string | null>;
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

  customer_id: number | null;
  program_id: number | null;
  project_id: number | null;
  calculation_year: number | null;
  project_volume: number | null;

  material_id: number | null;
  schussgewicht_g: number;
  teilegewicht_netto_g: number;
  ausschussquote_pct: number;
  materialpreis_pro_kg: number;
  /** Nominierung am Materialeinsatz dieser Kalkulation */
  material_nominierung: "selbstnominiert" | "oem_nominiert" | null;

  werk_id: number | null;
  losgroesse: number | null;
  losgroesse_modus: "automatisch" | "manuell";
  losgroesse_manuell: number | null;
  setup_zeit_min: number;
  setup_maschinenstundensatz: number;
  setup_lohnstundensatz: number;
  setup_mitarbeiter: number;
  setup_aktiv: boolean;

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
  customer_id: null,
  program_id: null,
  project_id: null,
  calculation_year: null,
  project_volume: null,
  material_id: null,
  schussgewicht_g: 0,
  teilegewicht_netto_g: 0,
  ausschussquote_pct: 0,
  materialpreis_pro_kg: 0,
  material_nominierung: null,
  werk_id: null,
  losgroesse: null,
  losgroesse_modus: "automatisch",
  losgroesse_manuell: null,
  setup_zeit_min: 0,
  setup_maschinenstundensatz: 0,
  setup_lohnstundensatz: 0,
  setup_mitarbeiter: 0,
  setup_aktiv: false,
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
