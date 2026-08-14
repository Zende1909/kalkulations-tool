export interface LifetimeYearRow {
  calendar_year: number;
  vehicle_volume: number;
  quantity_per_vehicle: number;
  project_volume: number;
  teilepreis_je_stueck?: number | null;
  baugruppenpreis_je_stueck?: number | null;
  jahresumsatz: number;
}

export interface BusinessCasePartRow {
  id: number;
  bezeichnung: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;
  gesamtstueckzahl_laufzeit?: number;
  endpreis_je_stueck: number | null;
  jahresumsatz: number;
  umsatzpotenzial_laufzeit?: number;
  lifetime_years?: LifetimeYearRow[];
  anzahl_veredelungsschritte: number;
}

export interface BusinessCaseAssemblyRow {
  id: number;
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;
  gesamtstueckzahl_laufzeit?: number;
  baugruppenpreis_je_stueck: number | null;
  jahresumsatz: number;
  umsatzpotenzial_laufzeit?: number;
  lifetime_years?: LifetimeYearRow[];
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
  amortization_volume: number | null;
  cost_per_piece: number | null;
  zuordnung: string;
  hinweis: string;
  bemerkung: string;
}

export interface BusinessCaseResponse {
  project: string;
  customer: string;
  kpis: {
    kunde: string;
    projekt: string;
    jahresstueckzahl_gesamt: number;
    gesamtstueckzahl_laufzeit?: number;
    umsatzpotenzial_laufzeit?: number;
    umsatzpotenzial_einzelteile: number;
    umsatzpotenzial_baugruppen: number;
    anzahl_einzelteile: number;
    anzahl_baugruppen: number;
    anzahl_investitionen: number;
    investitionen_gesamt: number;
    amortisationsinvestitionen_gesamt: number;
    einmalinvestitionen_gesamt: number;
    amortisationsanteil_je_stueck: number | null;
    teilepreis_je_stueck: number | null;
    baugruppenpreis_je_stueck: number | null;
  };
  parts: BusinessCasePartRow[];
  assemblies: BusinessCaseAssemblyRow[];
  investments: BusinessCaseInvestmentRow[];
  investment_summary: Record<string, unknown>;
  revenue_summary: {
    umsatzpotenzial_einzelteile: number;
    umsatzpotenzial_baugruppen: number;
    umsatzpotenzial_laufzeit?: number;
    umsatz_je_kalenderjahr?: { calendar_year: number; jahresumsatz: number }[];
    hinweis: string;
  };
  lifetime_volume_profile?: LifetimeYearRow[];
}
