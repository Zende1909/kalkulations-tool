export const INVESTMENT_TYPES = [
  "Werkzeug",
  "Vorrichtung",
  "Maschine",
  "Prüfmittel",
  "Lehre",
  "Montageanlage",
  "Sonstige",
] as const;

export const PAYMENT_TYPES = ["Amortisation", "Einmalzahlung", "CAPEX", "Entwicklung"] as const;

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
  cost_amount: number;
  bottom_price: number | null;
  revenue_amount: number | null;
  amount: number;
  margin_revenue_minus_cost: number | null;
  margin_revenue_minus_bottom_price: number | null;
  margin_bottom_price_minus_cost: number | null;
  amount_warnings: string[];
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

export interface InvestmentFinancialBlock {
  count: number;
  cost_amount_total: number;
  bottom_price_total: number;
  revenue_amount_total: number;
  margin_revenue_minus_cost_total: number | null;
  margin_revenue_minus_bottom_price_total: number | null;
  margin_bottom_price_minus_cost_total: number | null;
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
  investition_cost_total: number;
  investition_bottom_price_total: number;
  investition_revenue_total: number;
  margin_revenue_minus_cost_total: number | null;
  margin_revenue_minus_bottom_price_total: number | null;
  margin_bottom_price_minus_cost_total: number | null;
  investition_financial_summary?: {
    material_assignments: InvestmentFinancialBlock;
    project_assignments: InvestmentFinancialBlock;
    totals: InvestmentFinancialBlock;
  };
  amortisationsanteil_je_stueck: number | null;
  preis_inkl_amortisation_je_stueck: number | null;
  einmalinvestitionen: Array<{
    id: number;
    name: string;
    amount: number;
    cost_amount: number;
    bottom_price: number | null;
    revenue_amount: number | null;
    hinweis: string;
  }>;
  anzahl_investitionen: number;
  hat_gespeicherte_kalkulation: boolean;
}

export interface InvestitionPayload {
  name: string;
  investment_type: string;
  payment_type: PaymentType | string;
  cost_amount: number;
  bottom_price?: number | null;
  revenue_amount?: number | null;
  amount?: number;
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
  cost_amount: 0,
  bottom_price: null,
  revenue_amount: null,
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
export const CAPEX_HINWEIS = "Werksinvestition ohne Bottom Price und Erlös";
export const ENTWICKLUNG_HINWEIS = "Entwicklungsinvestition mit optionalem Bottom Price und Erlös";

export function paymentHintFor(paymentType: string): string {
  if (paymentType === "Einmalzahlung") return EINMALZAHLUNG_HINWEIS;
  if (paymentType === "CAPEX") return CAPEX_HINWEIS;
  if (paymentType === "Entwicklung") return ENTWICKLUNG_HINWEIS;
  return "";
}

export function isCapexPayment(paymentType: string): boolean {
  return paymentType === "CAPEX";
}

export function isEntwicklungPayment(paymentType: string): boolean {
  return paymentType === "Entwicklung";
}

export type ZuordnungFilter = "" | AssignmentType;
