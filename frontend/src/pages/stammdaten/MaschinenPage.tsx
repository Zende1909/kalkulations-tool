import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Maschine } from "../../types/stammdaten";

const columnDefs: ColDef<Maschine>[] = [
  { field: "maschinen_nr", headerName: "Maschinen-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "stundensatz", headerName: "Stundensatz" },
  { field: "schliesskraft_t", headerName: "Schließkraft (t)" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "maschinen_nr", label: "Maschinen-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "stundensatz", label: "Stundensatz (EUR/h)", type: "number", required: true, step: "0.01" },
  { name: "schliesskraft_t", label: "Schließkraft (t)", type: "number", required: true, step: "0.1" },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  maschinen_nr: "",
  stundensatz: 0,
  schliesskraft_t: 0,
  aktiv: true,
};

export function MaschinenPage() {
  return (
    <StammdatenGrid<Maschine>
      title="Maschinen"
      entityLabel="Maschine"
      endpoint="/maschinen"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
    />
  );
}
