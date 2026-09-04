export type ProjectAssemblyMixStatus = "complete" | "incomplete" | "overflow" | "empty";

export interface ProjectAssemblyMixComponent {
  component_type: string;
  component_id: number;
  bezeichnung: string;
  teilenummer: string;
  menge_je_variante?: number;
  effektive_jahresmenge: number;
  losgroesse?: number | null;
  anzahl_lose?: number | null;
}

export interface ProjectAssemblyMixRow {
  id: number;
  teilenummer: string;
  bezeichnung: string;
  anteil_prozent: number | null;
  aktiv: boolean;
  jahresmenge: number;
  komponenten_anzahl: number;
  kosten_je_stueck: number;
  gewichteter_kostenbeitrag: number | null;
  komponenten: ProjectAssemblyMixComponent[];
  legacy_standalone: boolean;
  in_project_mix: boolean;
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

/** Projektbezogener Baugruppen-Variantenmix (API: GET /baugruppen/project-mix). */
export interface ProjectAssemblyMix {
  family_id: number | null;
  name: string;
  project_id: number;
  status: string;
  aktiv: boolean;
  project_jahresstueckzahl: number;
  mix_status: ProjectAssemblyMixStatus;
  mix_message: string;
  mix_is_complete: boolean;
  can_compute_full: boolean;
  active_share_sum_pct: number;
  missing_pct: number;
  overflow_pct: number;
  baugruppen: ProjectAssemblyMixRow[];
  /** Alias der API – gleiche Zeilen wie baugruppen. */
  variants: ProjectAssemblyMixRow[];
  aggregated_components: AggregatedComponent[];
  gewichtete_kosten_pro_projektstueck: number | null;
}

export function mixStatusLabel(status: ProjectAssemblyMixStatus): string {
  switch (status) {
    case "complete":
      return "vollständig";
    case "incomplete":
      return "unvollständig";
    case "overflow":
      return "überschritten";
    case "empty":
      return "leer";
  }
}
