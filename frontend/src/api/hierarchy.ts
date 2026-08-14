import { api } from "./client";
import type {
  Customer,
  Program,
  ProgramVolume,
  Project,
  ProjectVolumeCalculation,
} from "../types/hierarchy";

function q(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export async function listCustomers(search?: string, active?: boolean): Promise<Customer[]> {
  return api.get<Customer[]>(`/customers${q({ search, active })}`);
}

export async function createCustomer(payload: Omit<Customer, "id" | "created_at" | "updated_at">): Promise<Customer> {
  return api.post<Customer>("/customers", payload);
}

export async function updateCustomer(id: number, payload: Partial<Customer>): Promise<Customer> {
  return api.put<Customer>(`/customers/${id}`, payload);
}

export async function deactivateCustomer(id: number): Promise<void> {
  return api.delete(`/customers/${id}`);
}

export async function listPrograms(customerId?: number, search?: string): Promise<Program[]> {
  return api.get<Program[]>(`/programs${q({ customer_id: customerId, search })}`);
}

export async function createProgram(payload: Omit<Program, "id" | "created_at" | "updated_at">): Promise<Program> {
  return api.post<Program>("/programs", payload);
}

export async function updateProgram(id: number, payload: Partial<Program>): Promise<Program> {
  return api.put<Program>(`/programs/${id}`, payload);
}

export async function deactivateProgram(id: number): Promise<void> {
  return api.delete(`/programs/${id}`);
}

export async function listProgramVolumes(programId: number): Promise<ProgramVolume[]> {
  return api.get<ProgramVolume[]>(`/programs/${programId}/volumes`);
}

export async function listAvailableYears(programId: number): Promise<number[]> {
  return api.get<number[]>(`/programs/${programId}/available-years`);
}

export async function createProgramVolume(
  payload: Omit<ProgramVolume, "id" | "created_at" | "updated_at">,
): Promise<ProgramVolume> {
  return api.post<ProgramVolume>("/program-volumes", payload);
}

export async function updateProgramVolume(id: number, payload: Partial<ProgramVolume>): Promise<ProgramVolume> {
  return api.put<ProgramVolume>(`/program-volumes/${id}`, payload);
}

export async function deleteProgramVolume(id: number): Promise<void> {
  return api.delete(`/program-volumes/${id}`);
}

export async function listProjects(programId?: number, search?: string): Promise<Project[]> {
  return api.get<Project[]>(`/projects${q({ program_id: programId, search })}`);
}

export async function createProject(payload: Omit<Project, "id" | "created_at" | "updated_at">): Promise<Project> {
  return api.post<Project>("/projects", payload);
}

export async function updateProject(id: number, payload: Partial<Project>): Promise<Project> {
  return api.put<Project>(`/projects/${id}`, payload);
}

export async function deactivateProject(id: number): Promise<void> {
  return api.delete(`/projects/${id}`);
}

export async function getCalculatedProjectVolume(
  projectId: number,
  calendarYear: number,
): Promise<ProjectVolumeCalculation> {
  return api.get<ProjectVolumeCalculation>(
    `/projects/${projectId}/calculated-volume${q({ calendar_year: calendarYear })}`,
  );
}
