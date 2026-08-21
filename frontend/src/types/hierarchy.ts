export const COMPONENT_AREAS = ["Interior", "Exterior"] as const;
export type ComponentArea = (typeof COMPONENT_AREAS)[number];

export const PROGRAM_STATUSES = [
  "Anfrage",
  "Angebot",
  "Beauftragt",
  "Laufend",
  "Abgeschlossen",
  "Inaktiv",
] as const;

export const PROJECT_STATUSES = [
  "Anfrage",
  "Kalkulation",
  "Angebot",
  "Beauftragt",
  "Laufend",
  "Abgeschlossen",
  "Inaktiv",
] as const;

export interface Customer {
  id: number;
  customer_number: string;
  name: string;
  notes: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Program {
  id: number;
  customer_id: number;
  program_number: string;
  name: string;
  vehicle_series: string;
  sop: string | null;
  eop: string | null;
  status: string;
  production_plant: string;
  notes: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProgramVolume {
  id: number;
  program_id: number;
  calendar_year: number;
  vehicle_volume: number;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: number;
  program_id: number;
  project_number: string;
  name: string;
  component_area: string;
  quantity_per_vehicle: number;
  status: string;
  notes: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectVolumeCalculation {
  project_id: number;
  program_id: number;
  calendar_year: number;
  vehicle_volume: number;
  quantity_per_vehicle: number;
  project_volume: number;
}

export interface ProgramVolumeProfileRow {
  id: number | null;
  calendar_year: number;
  vehicle_volume: number;
  in_sop_eop_range: boolean;
}

export interface ProgramVolumeProfile {
  program_id: number;
  sop: string | null;
  eop: string | null;
  sop_eop_years: number[];
  rows: ProgramVolumeProfileRow[];
}

export interface ProgramVolumeBulkItem {
  calendar_year: number;
  vehicle_volume: number;
}

export interface ProjectVolumeProfileRow {
  calendar_year: number;
  vehicle_volume: number;
  quantity_per_vehicle: number;
  project_volume: number;
}

export interface ProjectVolumeProfile {
  project_id: number;
  program_id: number;
  quantity_per_vehicle: number;
  total_project_volume: number;
  rows: ProjectVolumeProfileRow[];
}

export interface ProjectAverageJahresstueckzahl {
  project_id: number;
  year_count: number;
  sum_project_volume: number;
  average_raw: number | null;
  jahresstueckzahl: number | null;
  has_volumes: boolean;
}

export interface SopEopChangeWarning {
  years_with_data_outside_new_range: number[];
  message: string;
}
