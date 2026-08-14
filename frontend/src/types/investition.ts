export const INVESTMENT_TYPES = [
  "Werkzeug",
  "Vorrichtung",
  "Maschine",
  "Prüfmittel",
  "Lehre",
  "Montageanlage",
  "Sonstige",
] as const;

export const PAYMENT_TYPES = ["Amortisation", "Einmalzahlung"] as const;

export type InvestmentType = (typeof INVESTMENT_TYPES)[number];
export type PaymentType = (typeof PAYMENT_TYPES)[number];

export interface Investition {
  id: number;
  name: string;
  investment_type: InvestmentType | string;
  payment_type: PaymentType | string;
  amount: number;
  amortization_volume: number | null;
  cost_per_piece: number | null;
  project: string;
  customer: string;
  calculation_id: number | null;
  baugruppe_id: number | null;
  description: string;
  included_in_unit_price: boolean;
  archived: boolean;
  zuordnung: string;
  payment_hint: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessCaseSummary {
  filter: {
    project: string | null;
    customer: string | null;
    calculation_id: number | null;
    baugruppe_id: number | null;
  };
  teilepreis_je_stueck: number | null;
  baugruppenpreis_je_stueck: number | null;
  jahresstueckzahl: number | null;
  jahresumsatz: number | null;
  investitionen_gesamt: number;
  amortisationsinvestitionen_gesamt: number;
  einmalinvestitionen_gesamt: number;
  amortisationsanteil_je_stueck: number | null;
  preis_inkl_amortisation_je_stueck: number | null;
  einmalinvestitionen: Array<{ id: number; name: string; amount: number; hinweis: string }>;
  anzahl_investitionen: number;
  hat_gespeicherte_kalkulation: boolean;
}

export interface InvestitionPayload {
  name: string;
  investment_type: string;
  payment_type: PaymentType | string;
  amount: number;
  amortization_volume?: number | null;
  project: string;
  customer: string;
  part_name?: string;
  part_number?: string;
  calculation_id?: number | null;
  baugruppe_id?: number | null;
  description: string;
}

export interface BusinessCaseFilters {
  project?: string;
  customer?: string;
  calculation_id?: number;
  baugruppe_id?: number;
  scope?: "gesamtprojekt" | "einzelteil" | "baugruppe";
}

export const emptyInvestitionForm = (): InvestitionPayload => ({
  name: "",
  investment_type: "Werkzeug",
  payment_type: "",
  amount: 0,
  amortization_volume: null,
  project: "",
  customer: "",
  calculation_id: null,
  baugruppe_id: null,
  description: "",
});

export const EINMALZAHLUNG_HINWEIS = "Separat, nicht im Stückpreis enthalten";

export type ZuordnungFilter = "" | "einzelteil" | "baugruppe" | "projekt";
