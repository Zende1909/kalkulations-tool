import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land } from "../../types/stammdaten";

const columnDefs: ColDef<Land>[] = [
  { field: "code", headerName: "Code" },
  { field: "name", headerName: "Name" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "code", label: "Code", type: "text", required: true },
  { name: "name", label: "Name", type: "text", required: true },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

export function LaenderPage() {
  return (
    <StammdatenGrid<Land>
      title="Länder / Regionen"
      entityLabel="Land"
      endpoint="/laender"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={{ code: "", name: "", aktiv: true }}
    />
  );
}
