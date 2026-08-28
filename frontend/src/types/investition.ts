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

export const ASSIGNMENT_TYPES = [
  "einzelteil",
  "kaufteil",
  "baugruppe",
  "gesamtprojekt",
] as const;

export type InvestmentType = (typeof INVESTMENT_TYPES)[number];
export type PaymentType = (typeof PAYMENT_TYPES)[number];
export type AssignmentType = (typeof ASSIGNMENT_TYPES)[number];

export const ASSIGNMENT_TYPE_LABELS: Record<AssignmentType, string> = {
  einzelteil: "Einzelteil",
  kaufteil: "Kaufteil",
  baugruppe: "Baugruppe",
  gesamtprojekt: "Gesamtprojekt",
};

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
  customer_id: number | null;
  program_id: number | null;
  linked_project_id: number | null;
  assignment_type: AssignmentType | string | null;
  assignment_type_label: string;
  part_number: string;
  part_name: string;
  calculation_id: number | null;
  baugruppe_id: number | null;
  kaufteil_id: number | null;
  description: string;
  included_in_unit_price: boolean;
  archived: boolean;
  zuordnung: string;
  payment_hint: string;
  created_at: string;
  updated_at: string;
}

export interface InvestitionTarget {
  object_id: number;
  assignment_type: AssignmentType | string;
  label: string;
  material_number: string;
  part_name: string;
  status?: string | null;
  part_price?: number | null;
  supplier?: string | null;
  nominierung?: string | null;
  customer_name?: string | null;
  program_name?: string | null;
  project_name?: string | null;
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
  project?: string;
  customer?: string;
  customer_id?: number | null;
  program_id?: number | null;
  linked_project_id?: number | null;
  assignment_type?: AssignmentType | string | null;
  part_name?: string;
  part_number?: string;
  calculation_id?: number | null;
  baugruppe_id?: number | null;
  kaufteil_id?: number | null;
  description: string;
}

export interface BusinessCaseFilters {
  project?: string;
  linked_project_id?: number;
  customer?: string;
  customer_id?: number;
  program_id?: number;
  calculation_id?: number;
  baugruppe_id?: number;
  kaufteil_id?: number;
  assignment_type?: AssignmentType | string;
  scope?: "gesamtprojekt" | "einzelteil" | "baugruppe" | "kaufteil";
}

export interface InvestitionTargetFilters {
  customer_id: number;
  program_id: number;
  project_id: number;
  assignment_type: AssignmentType | string;
}

export const emptyInvestitionForm = (): InvestitionPayload => ({
  name: "",
  investment_type: "Werkzeug",
  payment_type: "",
  amount: 0,
  amortization_volume: null,
  project: "",
  customer: "",
  customer_id: null,
  program_id: null,
  linked_project_id: null,
  assignment_type: null,
  calculation_id: null,
  baugruppe_id: null,
  kaufteil_id: null,
  description: "",
});

export const EINMALZAHLUNG_HINWEIS = "Separat, nicht im Stückpreis enthalten";

export type ZuordnungFilter = "" | AssignmentType;
