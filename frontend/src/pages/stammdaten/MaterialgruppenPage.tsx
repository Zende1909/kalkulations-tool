import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Materialgruppe } from "../../types/materialgruppe";
import {
  loadMaterialgruppeFormValues,
  submitMaterialgruppeFormValues,
} from "../../utils/materialgruppeFormDecimals";

const columnDefs: ColDef<Materialgruppe>[] = [
  { field: "gruppe", headerName: "Schlüssel", pinned: "left", width: 110 },
  { field: "bezeichnung", headerName: "Bezeichnung", minWidth: 180 },
  { field: "schmelzdichte_kg_m3", headerName: "Schmelzdichte kg/m³", width: 150 },
  { field: "waermekapazitaet_j_kg_k", headerName: "Wärmekapazität J/kg·K", width: 170 },
  { field: "waermeleitfaehigkeit_w_m_k", headerName: "Wärmeleitf. W/m·K", width: 150 },
  { field: "werkzeugtemperatur_c", headerName: "Werkzeug °C", width: 120 },
  { field: "schmelzetemperatur_c", headerName: "Schmelze °C", width: 120 },
  { field: "entformungstemperatur_c", headerName: "Entformung °C", width: 130 },
  { field: "aktiv", headerName: "Aktiv", width: 90 },
];

const formFields: FormField[] = [
  {
    name: "gruppe",
    label: "Gruppenschlüssel",
    type: "text",
    required: true,
    hint: "Kurzname, z. B. POM oder PE-HD. Wird beim Speichern normalisiert.",
  },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  {
    name: "schmelzdichte_kg_m3",
    label: "Schmelzdichte (kg/m³)",
    type: "number",
    required: true,
    step: "0.01",
  },
  {
    name: "waermekapazitaet_j_kg_k",
    label: "Wärmekapazität (J/kg·K)",
    type: "number",
    required: true,
    step: "0.01",
  },
  {
    name: "waermeleitfaehigkeit_w_m_k",
    label: "Wärmeleitfähigkeit (W/m·K)",
    type: "number",
    required: true,
    step: "0.0001",
  },
  {
    name: "werkzeugtemperatur_c",
    label: "Werkzeugtemperatur (°C)",
    type: "number",
    required: true,
    step: "0.1",
  },
  {
    name: "schmelzetemperatur_c",
    label: "Schmelzetemperatur (°C)",
    type: "number",
    required: true,
    step: "0.1",
  },
  {
    name: "entformungstemperatur_c",
    label: "Entformungstemperatur (°C)",
    type: "number",
    required: true,
    step: "0.1",
    hint: "Muss zwischen Werkzeug- und Schmelzetemperatur liegen.",
  },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  gruppe: "",
  bezeichnung: "",
  schmelzdichte_kg_m3: 0,
  waermekapazitaet_j_kg_k: 0,
  waermeleitfaehigkeit_w_m_k: 0,
  werkzeugtemperatur_c: 0,
  schmelzetemperatur_c: 0,
  entformungstemperatur_c: 0,
  aktiv: true,
};

export function MaterialgruppenPage() {
  return (
    <StammdatenGrid<Materialgruppe>
      title="Materialgruppen"
      entityLabel="Materialgruppe"
      endpoint="/materialgruppen"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      formMaxWidthClassName="max-w-2xl"
      formBanner={
        <p>
          Thermische Kennwerte für die Zykluszeit-Schätzung. Materialien verweisen über den
          Gruppenschlüssel auf diese Stammdaten.
        </p>
      }
      transformLoadValues={(values) => loadMaterialgruppeFormValues(values)}
      transformSubmitValues={(values) => submitMaterialgruppeFormValues(values)}
    />
  );
}
