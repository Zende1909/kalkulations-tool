import type { ColDef } from "ag-grid-community";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land, Werk } from "../../types/stammdaten";
import { WERK_RATE_FRACTION_FIELDS } from "../../utils/decimalInput";
import { loadWerkFormValues, submitWerkFormValues } from "../../utils/werkFormDecimals";

const RATE_HINT = "Eingabe als Prozentwert, z. B. 8 = 8 %";

const columnDefs: ColDef<Werk>[] = [
  { field: "code", headerName: "Code" },
  { field: "name", headerName: "Name" },
  { field: "land_id", headerName: "Land-ID" },
  { field: "currency", headerName: "Währung" },
  { field: "fx_to_eur", headerName: "FX → EUR" },
  { field: "arbeitstage_pro_jahr", headerName: "Tage/Jahr" },
  { field: "produktionsintervall_arbeitstage", headerName: "Prod.-Intervall" },
  { field: "oee", headerName: "OEE (0–1)" },
  { field: "aktiv", headerName: "Aktiv" },
];

function rateFractionWarnings(
  values: Record<string, string | number | boolean>,
): string[] {
  const labels: Record<string, string> = {
    zinssatz: "Zinssatz",
    versicherungssatz: "Versicherungssatz",
    instandhaltungssatz: "Instandhaltungssatz",
  };
  const warnings: string[] = [];
  for (const key of WERK_RATE_FRACTION_FIELDS) {
    const raw = values[key];
    if (raw === "" || raw == null) continue;
    const num = typeof raw === "number" ? raw : Number(raw);
    if (Number.isFinite(num) && num > 100) {
      warnings.push(
        `${labels[key]}: Anzeigewert ${num} liegt außerhalb 0–100 %. Bitte Stammdaten manuell prüfen (keine Automatikkorrektur).`,
      );
    }
  }
  return warnings;
}

/** Warnung anhand der API-Rohwerte (Anteil), bevor ×100. */
export function warningsForStoredRateFractions(werk: Partial<Werk>): string[] {
  const labels: Record<string, string> = {
    zinssatz: "Zinssatz",
    versicherungssatz: "Versicherungssatz",
    instandhaltungssatz: "Instandhaltungssatz",
  };
  const out: string[] = [];
  for (const key of WERK_RATE_FRACTION_FIELDS) {
    const v = werk[key];
    if (v == null || !Number.isFinite(v)) continue;
    if (v < 0 || v > 1) {
      out.push(
        `${labels[key]}: gespeicherter Anteil ${v} liegt außerhalb 0–1 ` +
          `(erwartet z. B. 0,08 für 8 %). Bitte manuell korrigieren – keine automatische Anpassung.`,
      );
    }
  }
  return out;
}

export function WerkePage() {
  const [lands, setLands] = useState<Land[]>([]);
  const [formBannerExtra, setFormBannerExtra] = useState<string[]>([]);

  useEffect(() => {
    api.get<Land[]>("/laender").then(setLands).catch(() => setLands([]));
  }, []);

  const formFields: FormField[] = useMemo(
    () => [
      {
        name: "land_id",
        label: "Land",
        type: "select",
        required: true,
        options: lands.map((l) => ({ value: String(l.id), label: `${l.code} – ${l.name}` })),
      },
      { name: "code", label: "Code", type: "text", required: true },
      { name: "name", label: "Name", type: "text", required: true },
      { name: "currency", label: "Quellwährung", type: "text", required: true },
      {
        name: "fx_to_eur",
        label: "Wechselkurs → EUR",
        type: "number",
        required: true,
        step: "0.0001",
      },
      {
        name: "arbeitstage_pro_jahr",
        label: "Arbeitstage/Jahr",
        type: "number",
        step: "1",
      },
      {
        name: "produktionsintervall_arbeitstage",
        label: "Produktionsintervall (Arbeitstage)",
        type: "number",
        step: "1",
        hint: "Standard 30 Arbeitstage für automatische Losgröße – keine EOQ/Andler-Formel.",
      },
      { name: "schichten_pro_tag", label: "Schichten/Tag", type: "number", step: "1" },
      {
        name: "stunden_pro_schicht",
        label: "Stunden/Schicht",
        type: "number",
        step: "0.1",
      },
      {
        name: "oee",
        label: "OEE (0–1)",
        type: "number",
        step: "0.0001",
        hint: "Anteil, z. B. 0,9 = 90 %. Nicht als Prozentpunkt eingeben.",
      },
      {
        name: "space_cost_satz_pro_sqm_jahr",
        label: "Space-Satz (€/m²/a)",
        type: "number",
        step: "0.0001",
        hint: "Absoluter Kostensatz in Quellwährung, z. B. 30 oder 30,5 – keine Prozentangabe.",
      },
      {
        name: "abschreibungsdauer_jahre",
        label: "Abschreibungsdauer (Jahre)",
        type: "number",
        step: "1",
      },
      {
        name: "zinssatz",
        label: "Zinssatz (%)",
        type: "number",
        step: "0.0001",
        hint: RATE_HINT,
      },
      {
        name: "versicherungssatz",
        label: "Versicherungssatz (%)",
        type: "number",
        step: "0.0001",
        hint: RATE_HINT,
      },
      {
        name: "instandhaltungssatz",
        label: "Instandhaltungssatz (%)",
        type: "number",
        step: "0.0001",
        hint: RATE_HINT,
      },
      {
        name: "strompreis",
        label: "Strompreis (€/kWh)",
        type: "number",
        step: "0.0001",
        hint: "Dezimalwert, z. B. 0,06 oder 0.06 – keine Prozentumrechnung.",
      },
      {
        name: "druckluftpreis",
        label: "Druckluftpreis (€/m³)",
        type: "number",
        step: "0.0001",
        hint: "Dezimalwert, z. B. 0,06 oder 0.06 – keine Prozentumrechnung.",
      },
      {
        name: "kuehlwasserpreis",
        label: "Kühlwasserpreis (€/m³)",
        type: "number",
        step: "0.0001",
        hint: "Dezimalwert, z. B. 0,03 oder 0.03 – keine Prozentumrechnung.",
      },
      { name: "aktiv", label: "Aktiv", type: "checkbox" },
    ],
    [lands],
  );

  return (
    <StammdatenGrid<Werk>
      title="Werke / Standorte"
      entityLabel="Werk"
      endpoint="/werke"
      columnDefs={columnDefs}
      formFields={formFields}
      formMaxWidthClassName="max-w-xl"
      formBanner={
        formBannerExtra.length > 0 ? (
          <div className="space-y-1 text-amber-900">
            <p className="font-medium">Auffällige gespeicherte Kostensätze</p>
            <ul className="list-disc pl-4 text-sm">
              {formBannerExtra.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        ) : undefined
      }
      emptyFormValues={{
        land_id: lands[0]?.id ?? 0,
        code: "",
        name: "",
        currency: "USD",
        fx_to_eur: 0.92,
        aktiv: true,
        arbeitstage_pro_jahr: 254,
        produktionsintervall_arbeitstage: 30,
        schichten_pro_tag: 2,
        stunden_pro_schicht: 8,
        oee: 0.9,
        space_cost_satz_pro_sqm_jahr: 30,
        abschreibungsdauer_jahre: 10,
        zinssatz: 0.08,
        versicherungssatz: 0.0045,
        instandhaltungssatz: 0.02,
        strompreis: 0.06,
        druckluftpreis: 0.06,
        kuehlwasserpreis: 0.03,
      }}
      transformLoadValues={(values, mode) => {
        if (mode === "edit") {
          setFormBannerExtra(
            warningsForStoredRateFractions(values as unknown as Partial<Werk>),
          );
        } else {
          setFormBannerExtra([]);
        }
        return loadWerkFormValues(values);
      }}
      transformSubmitValues={(values) => {
        const uiWarnings = rateFractionWarnings(values);
        if (uiWarnings.length) {
          setFormBannerExtra(uiWarnings);
        }
        return submitWerkFormValues(values);
      }}
    />
  );
}
