export interface MaschineAuslastungProjectContribution {
  project_id: number;
  project_name: string;
  source_type: string;
  source_label: string;
  jahresstueckzahl: number;
  run_hours: number;
  setup_hours: number;
  required_hours: number;
}

export interface MaschineAuslastungYearRow {
  year: number;
  calendar_year: number;
  machine_id: number;
  maschine_id: number;
  machine_name: string;
  maschinen_nr: string;
  gross_hours: number | null;
  oee: number | null;
  oee_in_available_hours: boolean;
  available_hours: number | null;
  run_hours: number;
  setup_hours: number;
  required_hours: number;
  utilization_pct: number | null;
  utilization_percent: number | null;
  remaining_hours: number | null;
  rest_capacity_hours: number | null;
  overload_hours: number | null;
  is_overloaded: boolean;
  overloaded: boolean;
  has_demand: boolean;
  project_ids: number[];
  projects: MaschineAuslastungProjectContribution[];
}

export interface MaschineAuslastungRow {
  maschine_id: number;
  maschinen_nr: string;
  bezeichnung: string;
  werk_id: number | null;
  werk_name: string | null;
  gross_hours: number | null;
  oee: number | null;
  oee_in_available_hours: boolean;
  available_hours: number | null;
  run_hours: number;
  setup_hours: number;
  required_hours: number;
  utilization_pct: number | null;
  rest_capacity_hours: number | null;
  overload_hours: number | null;
  is_overloaded: boolean;
  has_demand: boolean;
  years_with_demand: number;
  yearly_breakdown: MaschineAuslastungYearRow[];
  projects: MaschineAuslastungProjectContribution[];
}

export interface MaschineAuslastungPlanningPeriod {
  label: string;
  basis: string;
  available_hours_per_machine_year: number | null;
  oee_in_available_hours: boolean;
}

export interface MaschineAuslastungSummary {
  machine_count: number;
  machines_with_demand: number;
  overloaded_count: number;
  average_utilization_pct: number | null;
  plant_utilization_pct: number | null;
  max_utilization_pct: number | null;
  max_utilization_maschine_id: number | null;
  max_utilization_maschine_name: string | null;
  max_utilization_year: number | null;
}

export interface MaschineAuslastungResponse {
  plant_id: number;
  plant_name: string;
  customer_id: number | null;
  program_id: number | null;
  project_status: string | null;
  project_ids: number[];
  resolved_project_ids: number[];
  no_projects_selected: boolean;
  uses_all_matching_projects: boolean;
  years: number[];
  planning_period: MaschineAuslastungPlanningPeriod;
  summary: MaschineAuslastungSummary;
  yearly_rows: MaschineAuslastungYearRow[];
  machines: MaschineAuslastungRow[];
}

export interface MaschineAuslastungParams {
  plant_id: number;
  customer_id?: number;
  program_id?: number;
  project_ids?: number[];
  project_status?: string;
}

export const UTILIZATION_YEARS = Array.from({ length: 15 }, (_, i) => 2026 + i);
