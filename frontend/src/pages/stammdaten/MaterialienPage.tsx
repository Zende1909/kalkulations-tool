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
  { field: "waehrung", headerName: "Währung" },
  { field: "aktiv", headerName: "Aktiv" },
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
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  material_nr: "",
  preis_pro_kg: 0,
  dichte: 1.0,
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
