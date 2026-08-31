export interface MaschineAuslastungProjectContribution {
  project_id: number;
  project_name: string;
  source_type: string;
  source_label: string;
  jahresstueckzahl: number;
  required_hours: number;
}

export interface MaschineAuslastungYearRow {
  calendar_year: number;
  required_hours: number;
  available_hours: number | null;
  utilization_pct: number | null;
}

export interface MaschineAuslastungRow {
  maschine_id: number;
  maschinen_nr: string;
  bezeichnung: string;
  werk_id: number | null;
  werk_name: string | null;
  available_hours: number | null;
  required_hours: number;
  utilization_pct: number | null;
  rest_capacity_hours: number | null;
  overload_hours: number | null;
  is_overloaded: boolean;
  has_demand: boolean;
  projects: MaschineAuslastungProjectContribution[];
  yearly_breakdown: MaschineAuslastungYearRow[];
}

export interface MaschineAuslastungPlanningPeriod {
  label: string;
  basis: string;
  available_hours_per_machine_year: number | null;
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
}

export interface MaschineAuslastungResponse {
  plant_id: number;
  plant_name: string;
  customer_id: number | null;
  program_id: number | null;
  project_ids: number[];
  no_projects_selected: boolean;
  planning_period: MaschineAuslastungPlanningPeriod;
  summary: MaschineAuslastungSummary;
  machines: MaschineAuslastungRow[];
}

export interface MaschineAuslastungParams {
  plant_id: number;
  customer_id?: number;
  program_id?: number;
  project_ids?: number[];
}
