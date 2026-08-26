import type { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land, Werk } from "../../types/stammdaten";

const columnDefs: ColDef<Werk>[] = [
  { field: "code", headerName: "Code" },
  { field: "name", headerName: "Name" },
  { field: "land_id", headerName: "Land-ID" },
  { field: "currency", headerName: "Währung" },
  { field: "fx_to_eur", headerName: "FX → EUR" },
  { field: "arbeitstage_pro_jahr", headerName: "Tage/Jahr" },
  { field: "oee", headerName: "OEE" },
  { field: "aktiv", headerName: "Aktiv" },
];

export function WerkePage() {
  const [lands, setLands] = useState<Land[]>([]);
  useEffect(() => {
    api.get<Land[]>("/laender").then(setLands).catch(() => setLands([]));
  }, []);

  const formFields: FormField[] = [
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
    { name: "schichten_pro_tag", label: "Schichten/Tag", type: "number", step: "1" },
    {
      name: "stunden_pro_schicht",
      label: "Stunden/Schicht",
      type: "number",
      step: "0.1",
    },
    { name: "oee", label: "OEE (0–1)", type: "number", step: "0.01" },
    {
      name: "space_cost_satz_pro_sqm_jahr",
      label: "Space-Satz /m²/a",
      type: "number",
      step: "0.01",
    },
    {
      name: "abschreibungsdauer_jahre",
      label: "Abschreibungsdauer (Jahre)",
      type: "number",
      step: "1",
    },
    { name: "zinssatz", label: "Zinssatz", type: "number", step: "0.0001" },
    {
      name: "versicherungssatz",
      label: "Versicherungssatz",
      type: "number",
      step: "0.0001",
    },
    {
      name: "instandhaltungssatz",
      label: "Instandhaltungssatz",
      type: "number",
      step: "0.0001",
    },
    { name: "strompreis", label: "Strompreis", type: "number", step: "0.01" },
    { name: "druckluftpreis", label: "Druckluftpreis", type: "number", step: "0.01" },
    { name: "kuehlwasserpreis", label: "Kühlwasserpreis", type: "number", step: "0.01" },
    { name: "aktiv", label: "Aktiv", type: "checkbox" },
  ];

  return (
    <StammdatenGrid<Werk>
      title="Werke / Standorte"
      entityLabel="Werk"
      endpoint="/werke"
      columnDefs={columnDefs}
      formFields={formFields}
      formMaxWidthClassName="max-w-xl"
      emptyFormValues={{
        land_id: lands[0]?.id ?? 0,
        code: "",
        name: "",
        currency: "USD",
        fx_to_eur: 0.92,
        aktiv: true,
        arbeitstage_pro_jahr: 254,
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
      transformSubmitValues={(values) => {
        const numericKeys = [
          "fx_to_eur",
          "arbeitstage_pro_jahr",
          "schichten_pro_tag",
          "stunden_pro_schicht",
          "oee",
          "space_cost_satz_pro_sqm_jahr",
          "abschreibungsdauer_jahre",
          "zinssatz",
          "versicherungssatz",
          "instandhaltungssatz",
          "strompreis",
          "druckluftpreis",
          "kuehlwasserpreis",
        ] as const;
        const payload: Record<string, unknown> = { ...values };
        const landRaw = values.land_id;
        payload.land_id =
          landRaw === "" || landRaw == null ? null : Number(landRaw);
        for (const key of numericKeys) {
          const raw = values[key];
          if (raw === "" || raw == null) {
            payload[key] = null;
            continue;
          }
          if (typeof raw === "number" && Number.isFinite(raw)) {
            payload[key] = raw;
            continue;
          }
          const parsed = Number(String(raw).replace(",", "."));
          payload[key] = Number.isFinite(parsed) ? parsed : raw;
        }
        return payload;
      }}
    />
  );
}
