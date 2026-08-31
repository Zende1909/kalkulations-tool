import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Material } from "../../types/stammdaten";
import {
  loadMaterialFormValues,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

const columnDefs: ColDef<Material>[] = [
  { field: "material_nr", headerName: "Material-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "preis_pro_kg", headerName: "Preis/kg" },
  { field: "dichte", headerName: "Dichte" },
  { field: "injection_pressure_kg_cm2", headerName: "Einspritzdruck kg/cm²" },
  { field: "materialgruppe", headerName: "Materialgruppe" },
  { field: "schmelzdichte_kg_m3", headerName: "Schmelzdichte kg/m³" },
  { field: "waermekapazitaet_j_kg_k", headerName: "Wärmekapazität J/(kg·K)" },
  { field: "waermeleitfaehigkeit_w_m_k", headerName: "Wärmeleitfähigkeit W/(m·K)" },
  { field: "werkzeugtemperatur_c", headerName: "Werkzeugtemp. °C" },
  { field: "schmelzetemperatur_c", headerName: "Schmelzetemp. °C" },
  { field: "entformungstemperatur_c", headerName: "Entformungstemp. °C" },
  { field: "waehrung", headerName: "Währung" },
  { field: "aktiv", headerName: "Aktiv" },
];

/** Muss zu `MATERIALGRUPPEN_DEFAULTS` im Backend passen. */
const MATERIALGRUPPEN = [
  "",
  "POM",
  "PP",
  "PE-HD",
  "PA6",
  "PA66",
  "ABS",
  "SAN",
  "PS",
  "PC",
  "PMMA",
  "PBT",
];

const formFields: FormField[] = [
  { name: "material_nr", label: "Material-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  {
    name: "preis_pro_kg",
    label: "Preis pro kg",
    type: "number",
    required: true,
    step: "0.0001",
    hint: "Dezimalwert, z. B. 2,10 oder 2.10",
  },
  {
    name: "dichte",
    label: "Dichte",
    type: "number",
    required: true,
    step: "0.0001",
    hint: "Dezimalwert, z. B. 1,04 oder 1.04",
  },
  { name: "waehrung", label: "Währung", type: "text", required: true },
  {
    name: "injection_pressure_kg_cm2",
    label: "Einspritzdruck",
    type: "number",
    required: true,
    step: "0.01",
    hint: "kg/cm² – Standard 500 bei neuen Materialien",
  },
  {
    name: "materialgruppe",
    label: "Materialgruppe (Thermik)",
    type: "select",
    options: MATERIALGRUPPEN,
    hint: "Belegt leere Thermikfelder mit Gruppen-Richtwerten vor – bitte gegen das Materialdatenblatt prüfen.",
  },
  {
    name: "schmelzdichte_kg_m3",
    label: "Schmelzdichte",
    type: "number",
    step: "0.01",
    hint: "kg/m³ – Dichte der Schmelze für die Kühlzeit, nicht die Feststoffdichte",
  },
  {
    name: "waermekapazitaet_j_kg_k",
    label: "Spezifische Wärmekapazität",
    type: "number",
    step: "1",
    hint: "J/(kg·K)",
  },
  {
    name: "waermeleitfaehigkeit_w_m_k",
    label: "Wärmeleitfähigkeit",
    type: "number",
    step: "0.001",
    hint: "W/(m·K)",
  },
  {
    name: "werkzeugtemperatur_c",
    label: "Werkzeugoberflächentemperatur",
    type: "number",
    step: "0.1",
    hint: "°C – muss kleiner als die Entformungstemperatur sein",
  },
  {
    name: "schmelzetemperatur_c",
    label: "Schmelzetemperatur",
    type: "number",
    step: "0.1",
    hint: "°C – muss größer als die Entformungstemperatur sein",
  },
  {
    name: "entformungstemperatur_c",
    label: "Entformungstemperatur",
    type: "number",
    step: "0.1",
    hint: "°C",
  },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  material_nr: "",
  preis_pro_kg: 0,
  dichte: 1.0,
  injection_pressure_kg_cm2: 500,
  materialgruppe: null,
  schmelzdichte_kg_m3: null,
  waermekapazitaet_j_kg_k: null,
  waermeleitfaehigkeit_w_m_k: null,
  werkzeugtemperatur_c: null,
  schmelzetemperatur_c: null,
  entformungstemperatur_c: null,
  waehrung: "EUR",
  aktiv: true,
};

export function MaterialienPage() {
  return (
    <StammdatenGrid<Material>
      title="Materialien"
      entityLabel="Material"
      endpoint="/materialien"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadMaterialFormValues(values)}
      transformSubmitValues={(values) => submitMaterialFormValues(values)}
    />
  );
}
