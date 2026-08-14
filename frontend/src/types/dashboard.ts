export interface DashboardKpis {
  anzahl_projekte: number;
  anzahl_spritzguss_kalkulationen: number;
  anzahl_baugruppen: number;
  durchschnitt_endpreis_einzelteil: number | null;
  durchschnitt_baugruppenpreis: number | null;
  durchschnitt_preis_pro_stueck: number | null;
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

export interface ChartBarItem {
  label: string;
  value: number;
  typ: string;
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
  status: string;
  letzte_kalkulation: string | null;
  cost_structure: ChartBarItem[];
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
  lieferant: string;
  bestelldatum: string | null;
  liefertermin: string | null;
  amortisationsvolumen: number | null;
  kostenanteil_pro_teil: number | null;
  created_at: string | null;
}

export interface ProjectAmountItem {
  projekt: string;
  betrag: number;
}

export interface DashboardFilterOptions {
  projekte: string[];
  kunden: string[];
  statusse: string[];
  kalkulationsarten: string[];
}

export interface DashboardSummary {
  kpis: DashboardKpis;
  recent_calculations: RecentCalculationRow[];
  recent_investments: InvestmentRow[];
  assemblies: AssemblyRow[];
  investments: InvestmentRow[];
  price_comparison: ChartBarItem[];
  cost_structure: ChartBarItem[];
  investment_by_project: ProjectAmountItem[];
  revenue_by_project: ProjectAmountItem[];
  filter_options: DashboardFilterOptions;
  has_data: boolean;
  empty_message: string | null;
}

export interface AssemblyBomRow {
  position_type: string;
  bezeichnung: string;
  teilenummer: string;
  menge: number;
  mengenfaktor: number;
  einzelpreis: number | null;
  zwischensumme: number | null;
}

export interface AssemblyMarkupRow {
  typ: string;
  bezeichnung: string;
  betrag: number | null;
  satz_prozent: number | null;
}

export interface AssemblyOverview {
  id: number;
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  status: string;
  structure_version: number;
  assembly_type: string;
  jahresstueckzahl: number;
  letzte_kalkulation: string | null;
  bom: AssemblyBomRow[];
  einzelteilkosten: number;
  kaufteilkosten: number;
  veredelungskosten: number;
  investitionskosten: number;
  vvgk: number | null;
  gewinn: number | null;
  skonto: number | null;
  nettoverkaufspreis: number | null;
  bruttoverkaufspreis: number | null;
  preis_je_stueck: number | null;
  herstellkosten: number | null;
  jahresumsatz: number;
  gesamtsumme: number | null;
  zuschlagssaetze: AssemblyMarkupRow[];
  cost_structure: ChartBarItem[];
  investitionen: Array<{
    id: number;
    bezeichnung: string;
    typ: string;
    betrag: number;
    status: string;
  }>;
  has_result: boolean;
  generated_at: string | null;
}

export interface DashboardQuery {
  project?: string;
  customer?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  kalkulationsart?: string;
}
