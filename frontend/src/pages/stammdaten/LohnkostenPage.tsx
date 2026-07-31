import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Lohnkosten } from "../../types/stammdaten";

const columnDefs: ColDef<Lohnkosten>[] = [
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "kosten_pro_stunde", headerName: "Kosten/h" },
  { field: "kostenstelle", headerName: "Kostenstelle" },
  { field: "gueltig_ab", headerName: "Gültig ab" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "kosten_pro_stunde", label: "Kosten pro Stunde", type: "number", required: true, step: "0.01" },
  { name: "kostenstelle", label: "Kostenstelle", type: "text", required: true },
  { name: "gueltig_ab", label: "Gültig ab", type: "date", required: true },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  kosten_pro_stunde: 0,
  kostenstelle: "",
  gueltig_ab: new Date().toISOString().slice(0, 10),
  aktiv: true,
};

export function LohnkostenPage() {
  return (
    <StammdatenGrid<Lohnkosten>
      title="Lohnkosten"
      entityLabel="Lohnkosten"
      endpoint="/lohnkosten"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
    />
  );
}
