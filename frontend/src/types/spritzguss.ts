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

export type MaschinenGroesseModus = "masse" | "flaeche";

export interface MaschinenGroesseResult {
  modus: MaschinenGroesseModus;
  injection_pressure_kg_cm2: number;
  kavitaeten: number;
  breite_mm?: number | null;
  laenge_mm?: number | null;
  oeffnungen_pct?: number | null;
  proj_flaeche_mm2?: number | null;
  proj_flaeche_netto_mm2?: number | null;
  zuhaltekraft_ohne_sicherheit_t: number;
  sicherheitszuschlag_faktor: number;
  zuhaltekraft_erforderlich_t: number;
  empfohlene_maschine_id?: number | null;
  empfohlene_maschine_name?: string | null;
  empfohlene_maschine_schliesskraft_t?: number | null;
  warnung?: string | null;
}

/**
 * Informative Werkzeug-/Maschinenklasse. Sie beschreibt die Größenordnung des
 * Werkzeugs; die Nebenzeit folgt den einzelnen Komponenten (Werkzeugbewegung,
 * Einspritzen/Nachdruck, Dosierüberhang, Entnahme, Prozessaufwand).
 * Muss zu `GROESSENKLASSEN` im Backend-Service `zykluszeit` passen.
 */
export const ZYKLUSZEIT_GROESSENKLASSEN = [
  { key: "klein", label: "Klein – Handteil, einfache Entformung" },
  { key: "mittel", label: "Mittel – Standardteil, Roboterentnahme" },
  { key: "gross", label: "Groß – Großteil, Kernzug oder Einlegeteil" },
] as const;

export type ZykluszeitTeilegroesse = (typeof ZYKLUSZEIT_GROESSENKLASSEN)[number]["key"];

/**
 * `auto` leitet die Klasse aus der erforderlichen Zuhaltekraft ab, in die
 * Kavitäten und projizierte Fläche bereits eingehen.
 * Muss zu `AUSWAHLWERTE` im Backend-Service `zykluszeit` passen.
 */
export const ZYKLUSZEIT_GROESSENKLASSE_AUTO = "auto";
export type ZykluszeitGroessenklasse = ZykluszeitTeilegroesse | "auto";

export const ZYKLUSZEIT_DEFAULT_GROESSENKLASSE: ZykluszeitGroessenklasse = "auto";
export const ZYKLUSZEIT_FALLBACK_TEILEGROESSE: ZykluszeitTeilegroesse = "mittel";
export const ZYKLUSZEIT_KUEHLFAKTOR = 1.5;

/** Schwellen aus `AUTO_SCHWELLEN_T` im Backend-Service `zykluszeit`. */
export const ZYKLUSZEIT_AUTO_SCHWELLEN_T: ReadonlyArray<[number, ZykluszeitTeilegroesse]> = [
  [100, "klein"],
  [300, "mittel"],
];

export function teilegroesseAusZuhaltekraft(
  zuhaltekraftT: number | null | undefined,
): ZykluszeitTeilegroesse {
  if (zuhaltekraftT == null || !Number.isFinite(zuhaltekraftT) || zuhaltekraftT <= 0) {
    return ZYKLUSZEIT_FALLBACK_TEILEGROESSE;
  }
  for (const [grenze, klasse] of ZYKLUSZEIT_AUTO_SCHWELLEN_T) {
    if (zuhaltekraftT <= grenze) return klasse;
  }
  return "gross";
}

export function effektiveGroessenklasse(
  klasse: string | null | undefined,
  zuhaltekraftT: number | null | undefined,
): ZykluszeitTeilegroesse {
  const treffer = ZYKLUSZEIT_GROESSENKLASSEN.find((k) => k.key === klasse);
  return treffer ? treffer.key : teilegroesseAusZuhaltekraft(zuhaltekraftT);
}

export type ZykluszeitProzessaufwand = "normal" | "aufwendig";
export const ZYKLUSZEIT_DEFAULT_PROZESSAUFWAND: ZykluszeitProzessaufwand = "normal";
export const ZYKLUSZEIT_PROZESSAUFWAND_ZUSCHLAG_S = 5;

/**
 * Entnahmeart des Teils. Muss zu `ENTNAHMEART_WERTE` im Backend-Service
 * `zykluszeit` passen; fehlende Werte gelten als `greifer`.
 */
export type ZykluszeitEntnahmeart = "werkzeugfallend" | "greifer";
export const ZYKLUSZEIT_DEFAULT_ENTNAHMEART: ZykluszeitEntnahmeart = "greifer";
export const ZYKLUSZEIT_ENTNAHMEARTEN = [
  {
    key: "werkzeugfallend",
    label: "werkzeugfallend – Teil fällt frei aus",
    beschreibung:
      "Teil fällt nach dem Auswerfen frei aus dem Werkzeug, das Werkzeug kann direkt wieder schließen.",
  },
  {
    key: "greifer",
    label: "greifer – Handlingsystem entnimmt",
    beschreibung:
      "Handlingsystem oder Roboter fährt in das offene Werkzeug ein, entnimmt das Teil und fährt aus, bevor das Werkzeug schließen kann.",
  },
] as const;

export function entnahmeartNormalisiert(wert: unknown): ZykluszeitEntnahmeart {
  return wert === "werkzeugfallend" ? "werkzeugfallend" : ZYKLUSZEIT_DEFAULT_ENTNAHMEART;
}

export type ZykluszeitQuelle = "manuell" | "vorschlag";

export interface ZykluszeitVorschlag {
  berechenbar: boolean;
  hinweis?: string | null;
  warnungen?: string[] | null;
  wandstaerke_mm?: number | null;
  materialgruppe?: string | null;
  material_bezeichnung?: string | null;
  materialklasse?: string | null;
  groessenklasse?: string | null;
  groessenklasse_auswahl?: string | null;
  zuhaltekraft_t?: number | null;
  schussgewicht_g?: number | null;
  kavitaeten?: number | null;
  entnahmeart?: string | null;
  prozessaufwand?: string | null;
  kuehlfaktor?: number | null;
  temperaturleitfaehigkeit_m2_s?: number | null;
  werkzeugtemperatur_c?: number | null;
  schmelzetemperatur_c?: number | null;
  entformungstemperatur_c?: number | null;
  optimale_kuehlzeit_s?: number | null;
  kuehlzeit_s?: number | null;
  nebenzeit_werkzeugbewegung_s?: number | null;
  nebenzeit_einspritz_nachdruck_s?: number | null;
  nebenzeit_dosierzeit_s?: number | null;
  nebenzeit_dosier_ueberhang_s?: number | null;
  nebenzeit_entnahme_s?: number | null;
  nebenzeit_prozessaufwand_zuschlag_s?: number | null;
  plastifizierleistung_kg_h?: number | null;
  schussmasse_gesamt_g?: number | null;
  nebenzeiten_automatisch_s?: number | null;
  schussgewicht_fallback?: boolean | null;
  zuhaltekraft_fallback?: boolean | null;
  nebenzeiten_gesamt_s?: number | null;
  nebenzeit_quelle?: string | null;
  /** Vorschlag in ganzen Sekunden; dieser Wert wird übernommen. */
  gesamtzykluszeit_s?: number | null;
  /** Ungerundete Summe aus Kühlzeit und Nebenzeit. */
  gesamtzykluszeit_exakt_s?: number | null;
  /** gueltig | nicht_plausibel | nicht_berechenbar */
  status?: "gueltig" | "nicht_plausibel" | "nicht_berechenbar" | string | null;
  kann_uebernommen_werden?: boolean | null;
  dosierzeit_warnfaktor?: number | null;
  dosierzeit_warngrenze_s?: number | null;
}

export interface SpritzgussCalcResponse {
  ergebnis: SpritzgussErgebnis;
  bloecke: SpritzgussBloecke;
  veredelung_zuordnungen?: VeredelungZuordnung[];
  maschinen_groesse?: MaschinenGroesseResult | null;
  zykluszeit_vorschlag?: ZykluszeitVorschlag | null;
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

  maschinen_groesse_modus: MaschinenGroesseModus | null;
  maschinen_groesse_breite_mm: number | null;
  maschinen_groesse_laenge_mm: number | null;
  maschinen_groesse_oeffnungen_pct: number | null;
  maschinen_groesse_proj_flaeche_mm2: number | null;

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

  /** Zykluszeit-Schätzung; wandstaerke_mm = kühlzeitrelevante Wandstärke */
  zykluszeit_quelle: ZykluszeitQuelle;
  zykluszeit_wandstaerke_mm: number | null;
  zykluszeit_groessenklasse: ZykluszeitGroessenklasse;
  zykluszeit_prozessaufwand: ZykluszeitProzessaufwand;
  zykluszeit_entnahmeart: ZykluszeitEntnahmeart;
  /** Übersteuert die automatische Nebenzeit vollständig, wenn gesetzt. */
  zykluszeit_nebenzeiten_gesamt_s: number | null;

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
  teilbild_mime: string | null;
  teilbild_data: string | null;
}

export interface SpritzgussKalkulation extends SpritzgussFormData {
  id: number;
  maschinen_groesse_injection_pressure_kg_cm2?: number | null;
  maschinen_groesse_proj_flaeche_netto_mm2?: number | null;
  maschinen_groesse_zuhaltekraft_ohne_sicherheit_t?: number | null;
  maschinen_groesse_sicherheitszuschlag_faktor?: number | null;
  maschinen_groesse_zuhaltekraft_erforderlich_t?: number | null;
  maschinen_groesse_empfohlene_maschine_id?: number | null;
  maschinen_groesse_warnung?: string | null;
  zykluszeit_kuehlzeit_s?: number | null;
  zykluszeit_vorschlag_s?: number | null;
  zykluszeit_hinweis?: string | null;
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
  project_id: number | null;
  customer_id: number | null;
  program_id: number | null;
  jahresstueckzahl: number;
  verkaufspreis: number | null;
  selbstkosten: number | null;
  updated_at: string;
  aktiv: boolean;
  teilbild_mime: string | null;
  teilbild_data: string | null;
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
  maschinen_groesse_modus: null,
  maschinen_groesse_breite_mm: null,
  maschinen_groesse_laenge_mm: null,
  maschinen_groesse_oeffnungen_pct: null,
  maschinen_groesse_proj_flaeche_mm2: null,
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
  zykluszeit_quelle: "manuell",
  zykluszeit_wandstaerke_mm: null,
  zykluszeit_groessenklasse: ZYKLUSZEIT_DEFAULT_GROESSENKLASSE,
  zykluszeit_prozessaufwand: ZYKLUSZEIT_DEFAULT_PROZESSAUFWAND,
  zykluszeit_entnahmeart: ZYKLUSZEIT_DEFAULT_ENTNAHMEART,
  zykluszeit_nebenzeiten_gesamt_s: null,
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
  teilbild_mime: null,
  teilbild_data: null,
});
