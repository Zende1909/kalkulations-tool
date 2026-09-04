export type AssemblyFamilyMixStatus = "complete" | "incomplete" | "overflow" | "empty";

export interface AssemblyFamily {
  id: number;
  project_id: number;
  name: string;
  beschreibung: string;
  status: string;
  aktiv: boolean;
  ergebnis?: Record<string, unknown> | null;
}

export interface AssemblyVariantWrite {
  teilenummer: string;
  bezeichnung: string;
  anteil_prozent: number;
  beschreibung?: string;
  aktiv?: boolean;
  werk_id?: number | null;
}

export interface AssemblyVariant {
  id: number;
  family_id: number | null;
  teilenummer: string;
  name: string;
  beschreibung: string;
  anteil_prozent: number;
  jahresstueckzahl: number;
  aktiv: boolean;
  status: string;
  project_id: number | null;
  werk_id: number | null;
}

export interface AssemblyVariantComponent {
  component_type: string;
  component_id: number;
  bezeichnung: string;
  teilenummer: string;
  menge_je_variante: number;
  effektive_jahresmenge: number;
}

export interface AssemblyVariantSummary {
  id: number;
  teilenummer: string;
  bezeichnung: string;
  anteil_prozent: number;
  aktiv: boolean;
  jahresmenge: number;
  komponenten_anzahl: number;
  kosten_je_stueck: number;
  gewichteter_kostenbeitrag: number | null;
  komponenten: AssemblyVariantComponent[];
}

export interface AggregatedComponent {
  component_type: string;
  component_id: number;
  bezeichnung: string;
  teilenummer: string;
  effektive_jahresmenge: number;
  losgroesse?: number | null;
  anzahl_lose?: number | null;
}

export interface AssemblyFamilyMix {
  family_id: number;
  name: string;
  project_id: number;
  status: string;
  aktiv: boolean;
  project_jahresstueckzahl: number;
  mix_status: AssemblyFamilyMixStatus;
  mix_message: string;
  mix_is_complete: boolean;
  can_compute_full: boolean;
  active_share_sum_pct: number;
  missing_pct: number;
  overflow_pct: number;
  variants: AssemblyVariantSummary[];
  aggregated_components: AggregatedComponent[];
  gewichtete_kosten_pro_projektstueck: number | null;
}
