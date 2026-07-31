export const VEREDELUNGSARTEN = [
  "Montage",
  "Ultraschallschweißen",
  "Vibrationsschweißen",
  "Lackieren",
  "Bedrucken",
  "Kaschieren",
  "Clipsen",
  "Schrauben",
  "Sonstige",
] as const;

export type Veredelungsart = (typeof VEREDELUNGSARTEN)[number];

export interface Veredelungsschritt {
  id: number;
  bezeichnung: string;
  veredelungsart: Veredelungsart;
  reihenfolge: number;
  beschreibung: string;
  taktzeit_s: number;
  anzahl_mitarbeiter: number;
  lohnkosten_id: number | null;
  lohnstundensatz: number;
  maschinenstundensatz: number | null;
  verbrauchskosten_je_stueck: number;
  ausschussquote_pct: number;
  fgk_pct: number;
  aktiv: boolean;
  lohnkosten_je_stueck: number;
  maschinenkosten_je_stueck: number;
  fertigungsgemeinkosten: number;
  kosten_vor_ausschuss: number;
  kosten_inkl_ausschuss: number;
  created_at: string;
  updated_at: string;
}

export type VeredelungsschrittPayload = Omit<
  Veredelungsschritt,
  | "id"
  | "created_at"
  | "updated_at"
  | "lohnkosten_je_stueck"
  | "maschinenkosten_je_stueck"
  | "fertigungsgemeinkosten"
  | "kosten_vor_ausschuss"
  | "kosten_inkl_ausschuss"
>;

export const emptyVeredelungForm = (): VeredelungsschrittPayload => ({
  bezeichnung: "",
  veredelungsart: "Montage",
  reihenfolge: 1,
  beschreibung: "",
  taktzeit_s: 0,
  anzahl_mitarbeiter: 1,
  lohnkosten_id: null,
  lohnstundensatz: 0,
  maschinenstundensatz: null,
  verbrauchskosten_je_stueck: 0,
  ausschussquote_pct: 0,
  fgk_pct: 0,
  aktiv: true,
});
