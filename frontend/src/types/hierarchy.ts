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
