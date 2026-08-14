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

export const INVESTITION_STATUS = [
  "In Planung",
  "Angefragt",
  "Bestellt",
  "In Herstellung",
  "Geliefert",
  "Abgenommen",
  "Abgeschlossen",
  "Storniert",
] as const;

export type InvestmentType = (typeof INVESTMENT_TYPES)[number];
export type PaymentType = (typeof PAYMENT_TYPES)[number];
export type InvestitionStatus = (typeof INVESTITION_STATUS)[number];

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
  part_name: string;
  part_number: string;
  calculation_id: number | null;
  baugruppe_id: number | null;
  supplier: string;
  order_date: string | null;
  delivery_date: string | null;
  status: InvestitionStatus | string;
  description: string;
  included_in_unit_price: boolean;
  archived: boolean;
  zuordnung: string;
  payment_hint: string;
  created_at: string;
  updated_at: string;
}

export interface InvestitionSummary {
  gesamtinvestitionen: number;
  anzahl_investitionen: number;
  summe_einmalzahlungen: number;
  summe_amortisiert: number;
  in_planung: number;
  bestellt: number;
  abgeschlossen: number;
}

export interface InvestitionPayload {
  name: string;
  investment_type: string;
  payment_type: PaymentType | string;
  amount: number;
  amortization_volume?: number | null;
  project: string;
  customer: string;
  part_name: string;
  part_number: string;
  calculation_id?: number | null;
  baugruppe_id?: number | null;
  supplier: string;
  order_date?: string | null;
  delivery_date?: string | null;
  status: string;
  description: string;
  included_in_unit_price?: boolean | null;
}

export interface InvestitionFilters {
  project?: string;
  customer?: string;
  investment_type?: string;
  payment_type?: string;
  status?: string;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const emptyInvestitionForm = (): InvestitionPayload => ({
  name: "",
  investment_type: "Werkzeug",
  payment_type: "Einmalzahlung",
  amount: 0,
  amortization_volume: null,
  project: "",
  customer: "",
  part_name: "",
  part_number: "",
  calculation_id: null,
  baugruppe_id: null,
  supplier: "",
  order_date: null,
  delivery_date: null,
  status: "In Planung",
  description: "",
});

export const EINMALZAHLUNG_HINWEIS = "Separat, nicht im Stückpreis enthalten";
