export interface BusinessCasePartRow {
  id: number;
  bezeichnung: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;
  endpreis_je_stueck: number | null;
  jahresumsatz: number;
  anzahl_veredelungsschritte: number;
}

export interface BusinessCaseAssemblyRow {
  id: number;
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  jahresstueckzahl: number;
  baugruppenpreis_je_stueck: number | null;
  jahresumsatz: number;
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
    hinweis: string;
  };
}
