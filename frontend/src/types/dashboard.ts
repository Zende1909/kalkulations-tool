export interface DashboardKpis {
  anzahl_projekte: number;
  anzahl_spritzguss_kalkulationen: number;
  anzahl_baugruppen: number;
  durchschnitt_endpreis_einzelteil: number | null;
  durchschnitt_baugruppenpreis: number | null;
  investitionen_gesamt: number;
  jahresstueckzahl: number;
  umsatzpotenzial_jahr: number;
}

export interface RecentCalculationRow {
  id: number;
  kalkulationsart: string;
  bezeichnung: string;
  nummer: string;
  kunde: string;
  projekt: string;
  endpreis_je_stueck: number | null;
  created_at: string;
  updated_at: string;
}

export interface AssemblyRow {
  id: number;
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  preis_je_stueck: number | null;
  jahresstueckzahl: number;
  jahresumsatz: number;
}

export interface InvestmentRow {
  id: number;
  bezeichnung: string;
  typ: string;
  betrag: number;
  projekt: string;
  kunde: string;
  status: string;
  im_stueckpreis: boolean;
  hinweis: string;
}

export interface ChartBarItem {
  label: string;
  value: number;
  typ: string;
}

export interface ProjectAmountItem {
  projekt: string;
  betrag: number;
}

export interface DashboardFilterOptions {
  projekte: string[];
  kunden: string[];
}

export interface DashboardSummary {
  kpis: DashboardKpis;
  recent_calculations: RecentCalculationRow[];
  assemblies: AssemblyRow[];
  investments: InvestmentRow[];
  price_comparison: ChartBarItem[];
  investment_by_project: ProjectAmountItem[];
  revenue_by_project: ProjectAmountItem[];
  filter_options: DashboardFilterOptions;
}
