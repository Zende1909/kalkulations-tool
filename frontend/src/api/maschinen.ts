import { api } from "./client";
import type {
  MaschineAuslastungParams,
  MaschineAuslastungResponse,
} from "../types/maschineAuslastung";

export async function getMaschinenAuslastung(
  params: MaschineAuslastungParams,
): Promise<MaschineAuslastungResponse> {
  const search = new URLSearchParams();
  search.set("plant_id", String(params.plant_id));
  if (params.customer_id != null) search.set("customer_id", String(params.customer_id));
  if (params.program_id != null) search.set("program_id", String(params.program_id));
  if (params.project_status) search.set("project_status", params.project_status);
  for (const id of params.project_ids ?? []) {
    search.append("project_ids", String(id));
  }
  const q = search.toString();
  return api.get<MaschineAuslastungResponse>(`/maschinen/auslastung?${q}`);
}
