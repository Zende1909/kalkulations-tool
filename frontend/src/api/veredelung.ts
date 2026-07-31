import { api } from "./client";
import type {
  Veredelungsschritt,
  VeredelungsschrittPayload,
} from "../types/veredelung";

const ENDPOINT = "/veredelung";

export function listVeredelungsschritte() {
  return api.get<Veredelungsschritt[]>(ENDPOINT);
}

export function createVeredelungsschritt(data: VeredelungsschrittPayload) {
  return api.post<Veredelungsschritt>(ENDPOINT, data);
}

export function updateVeredelungsschritt(
  id: number,
  data: Partial<VeredelungsschrittPayload>,
) {
  return api.put<Veredelungsschritt>(`${ENDPOINT}/${id}`, data);
}

export function deleteVeredelungsschritt(id: number) {
  return api.delete(`${ENDPOINT}/${id}`);
}
