export interface PositionPricing {
  cost_per_piece: number | null;
  has_cost_per_piece: boolean;
  bottom_price_per_piece: number | null;
  actual_price_per_piece: number | null;
  guide_price_per_piece: number | null;
  project_volume: number;
  bottom_price_revenue: number | null;
  actual_revenue: number | null;
  cost_total: number | null;
  margin_bottom_price_per_piece: number | null;
  margin_actual_price_per_piece: number | null;
  margin_bottom_price_total: number | null;
  margin_actual_total: number | null;
  margin_bottom_price_pct: number | null;
  margin_actual_price_pct: number | null;
  margin_bottom_price_total_pct: number | null;
  margin_actual_total_pct: number | null;
  price_warnings: string[];
  has_manual_bottom_price: boolean;
  has_manual_actual_price: boolean;
}

export interface BusinessCasePartRow extends PositionPricing {
  id: number;
  assignment_type: string;
  bezeichnung: string;
  teilenummer: string;
  material_number: string;
  kunde: string;
  program: string;
  projekt: string;
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  jahresstueckzahl: number;
  gesamtstueckzahl_laufzeit: number;
  endpreis_je_stueck: number | null;
  anzahl_veredelungsschritte: number;
}

export interface BusinessCaseAssemblyRow extends PositionPricing {
  id: number;
  assignment_type: string;
  name: string;
  teilenummer: string;
  material_number: string;
  kunde: string;
  program: string;
  projekt: string;
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  jahresstueckzahl: number;
  gesamtstueckzahl_laufzeit: number;
  baugruppenpreis_je_stueck: number | null;
  jahresumsatz: number;
  umsatzpotenzial_laufzeit: number | null;
  anzahl_einzelteile: number;
  anzahl_kaufteile: number;
  anzahl_veredelungsschritte: number;
}

export interface BusinessCaseInvestmentRow {
  id: number;
  bezeichnung: string;
  investment_type: string;
  payment_type: string;
  amount: number;
  cost_amount: number;
  bottom_price: number | null;
  revenue_amount: number | null;
  margin_revenue_minus_cost: number | null;
  margin_revenue_minus_bottom_price: number | null;
  margin_bottom_price_minus_cost: number | null;
  margin_revenue_minus_cost_pct: number | null;
  margin_revenue_minus_bottom_price_pct: number | null;
  amount_warnings: string[];
  assignment_type: string | null;
  assignment_type_label: string;
  material_number: string;
  customer_name: string;
  program_name: string;
  project_name: string;
  amortization_volume: number | null;
  cost_per_piece: number | null;
  zuordnung: string;
  hinweis: string;
  bemerkung: string;
}

export interface BusinessCaseFilter {
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  customer: string;
  program: string;
  project: string;
}

export interface BusinessCaseSegmentKpis {
  cost_total: number | null;
  bottom_price_revenue_total: number | null;
  actual_revenue_total: number | null;
  ebit_bottom: number | null;
  ebit_bottom_pct: number | null;
  ebit_actual: number | null;
  ebit_actual_pct: number | null;
  roi_bottom_pct?: number | null;
  roi_actual_pct?: number | null;
  roi_operating_bottom_pct?: number | null;
  roi_operating_actual_pct?: number | null;
}

export interface BusinessCaseCapexKpis {
  cost_total: number | null;
  bound_capital_share_pct: number | null;
  note: string;
}

export interface BusinessCaseCapitalKpis {
  capex_total: number;
  operative_investment_cost_total: number;
  non_capex_investment_cost_total: number;
  total_investment_cost_total: number;
  bound_capital_total: number | null;
  capex_share_of_bound_capital_pct: number | null;
  roi_incl_capex_bottom_pct: number | null;
  roi_incl_capex_actual_pct: number | null;
}

export interface BusinessCaseOperatingKpis {
  cost_total: number | null;
  bottom_price_revenue_total: number | null;
  actual_revenue_total: number | null;
  ebit_bottom: number | null;
  ebit_bottom_pct: number | null;
  ebit_actual: number | null;
  ebit_actual_pct: number | null;
  roi_operating_bottom_pct: number | null;
  roi_operating_actual_pct: number | null;
}

export interface BusinessCaseKpiSummary {
  parts: BusinessCaseSegmentKpis;
  investments: BusinessCaseSegmentKpis;
  investments_operating: BusinessCaseSegmentKpis;
  capex: BusinessCaseCapexKpis;
  operating: BusinessCaseOperatingKpis;
  capital: BusinessCaseCapitalKpis;
  total: BusinessCaseSegmentKpis;
  revenue_breakdown: {
    parts_bottom_price_revenue: number | null;
    parts_actual_revenue: number | null;
    investments_bottom_price_revenue: number | null;
    investments_actual_revenue: number | null;
    total_bottom_price_revenue: number | null;
    total_actual_revenue: number | null;
  };
  cost_breakdown: {
    parts_standalone: number | null;
    assemblies: number | null;
    parts_total: number | null;
    capex: number;
    entwicklung: number;
    legacy: number;
    operative_investments: number;
    investments_total: number;
    operative_total: number | null;
    bound_capital: number | null;
    total: number | null;
  };
  ebit_note: string;
  roi_note: string;
}

export interface BusinessCaseKpis {
  kunde: string;
  programm: string;
  projekt: string;
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  project_volume_total: number;
  parts_cost_total: number | null;
  operative_cost_total: number | null;
  cost_total: number | null;
  bound_capital_total: number | null;
  capex_cost_total: number;
  non_capex_investment_cost_total: number;
  bottom_price_revenue_total: number | null;
  actual_revenue_total: number | null;
  parts_bottom_price_revenue_total: number | null;
  parts_actual_revenue_total: number | null;
  margin_bottom_price_total: number | null;
  margin_actual_total: number | null;
  margin_bottom_price_total_pct: number | null;
  margin_actual_total_pct: number | null;
  ebit_bottom_total: number | null;
  ebit_bottom_total_pct: number | null;
  ebit_actual_total: number | null;
  ebit_actual_total_pct: number | null;
  roi_bottom_pct: number | null;
  roi_actual_pct: number | null;
  roi_incl_capex_bottom_pct: number | null;
  roi_incl_capex_actual_pct: number | null;
  roi_operating_bottom_pct: number | null;
  roi_operating_actual_pct: number | null;
  parts_ebit_bottom: number | null;
  parts_ebit_bottom_pct: number | null;
  parts_ebit_actual: number | null;
  parts_ebit_actual_pct: number | null;
  parts_roi_bottom_pct: number | null;
  parts_roi_actual_pct: number | null;
  investments_ebit_bottom: number | null;
  investments_ebit_bottom_pct: number | null;
  investments_ebit_actual: number | null;
  investments_ebit_actual_pct: number | null;
  investments_roi_bottom_pct: number | null;
  investments_roi_actual_pct: number | null;
  anzahl_einzelteile: number;
  anzahl_baugruppen: number;
  anzahl_einzelteile_in_baugruppen_ausgeschlossen: number;
  anzahl_investitionen: number;
  investitionen_gesamt: number;
  amortisationsinvestitionen_gesamt: number;
  einmalinvestitionen_gesamt: number;
  capex_investitionen_gesamt: number;
  entwicklungsinvestitionen_gesamt: number;
  amortisationsanteil_je_stueck: number | null;
  investition_cost_total: number;
  investition_bottom_price_total: number;
  investition_revenue_total: number;
  margin_revenue_minus_cost_total: number | null;
  margin_revenue_minus_bottom_price_total: number | null;
  margin_bottom_price_minus_cost_total: number | null;
}

export interface BusinessCaseResponse {
  filter: BusinessCaseFilter;
  project: string;
  customer: string;
  program: string;
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  kpis: BusinessCaseKpis;
  parts: BusinessCasePartRow[];
  assemblies: BusinessCaseAssemblyRow[];
  investments: BusinessCaseInvestmentRow[];
  investments_capex: BusinessCaseInvestmentRow[];
  investments_entwicklung: BusinessCaseInvestmentRow[];
  investments_other: BusinessCaseInvestmentRow[];
  sales_summary: Record<string, unknown>;
  investment_summary: Record<string, unknown>;
  investment_financial_summary: {
    capex: InvestmentCategorySummary;
    entwicklung: InvestmentCategorySummary;
    legacy: InvestmentCategorySummary;
    material_assignments: InvestmentFinancialBlock;
    project_assignments: InvestmentFinancialBlock;
    totals: InvestmentFinancialBlock;
  };
  kpi_summary: BusinessCaseKpiSummary;
  revenue_summary: {
    hinweis: string;
    excluded_einzelteile_in_baugruppen: number;
  };
  revenue_by_year: BusinessCaseRevenueYearRow[];
}

export interface BusinessCaseRevenueYearRow {
  calendar_year: number;
  project_volume: number;
  bottom_price_revenue: number | null;
  actual_revenue: number | null;
}

export interface InvestmentFinancialBlock {
  count: number;
  cost_amount_total: number;
  bottom_price_total: number;
  revenue_amount_total: number;
  margin_revenue_minus_cost_total: number | null;
  margin_revenue_minus_bottom_price_total: number | null;
  margin_bottom_price_minus_cost_total: number | null;
  margin_revenue_minus_cost_pct?: number | null;
  margin_revenue_minus_bottom_price_pct?: number | null;
}

export interface InvestmentCategorySummary extends InvestmentFinancialBlock {
  margin_revenue_minus_cost_pct?: number | null;
  margin_revenue_minus_bottom_price_pct?: number | null;
}

export interface ManualPriceUpsert {
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  assignment_type: "einzelteil" | "baugruppe";
  object_id: number;
  bottom_price_per_piece?: number | null;
  actual_price_per_piece?: number | null;
}

export type PriceEditTarget = {
  assignmentType: "einzelteil" | "baugruppe";
  row: BusinessCasePartRow | BusinessCaseAssemblyRow;
  label: string;
  materialNumber: string;
};
