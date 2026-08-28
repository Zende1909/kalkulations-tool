/** Automatische Losgröße – Spiegel der Backend-Formel (Produktionsintervall, keine EOQ). */

export const DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE = 30;

export function berechneAutomatischeLosgroesse(
  jahresbedarf: number,
  produktionsintervallArbeitstage: number,
  arbeitstageProJahr: number,
): number | null {
  if (!Number.isFinite(jahresbedarf) || jahresbedarf <= 0) return null;
  if (!Number.isFinite(produktionsintervallArbeitstage) || produktionsintervallArbeitstage <= 0) {
    return null;
  }
  if (!Number.isFinite(arbeitstageProJahr) || arbeitstageProJahr <= 0) return null;
  const raw = (jahresbedarf * produktionsintervallArbeitstage) / arbeitstageProJahr;
  const bedarfInt = Math.ceil(jahresbedarf);
  return Math.max(1, Math.min(Math.ceil(raw), bedarfInt));
}

export function werkProduktionsintervall(
  werk: { produktionsintervall_arbeitstage?: number | null } | null | undefined,
): number {
  const val = werk?.produktionsintervall_arbeitstage;
  if (val == null || val <= 0) return DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE;
  return val;
}

export type LosgroesseModus = "automatisch" | "manuell";

export function inferLegacyLosgroesseModus(
  modus: LosgroesseModus | null | undefined,
  losgroesse: number | null | undefined,
): LosgroesseModus {
  if (modus === "automatisch" || modus === "manuell") return modus;
  return losgroesse != null && losgroesse > 0 ? "manuell" : "automatisch";
}
