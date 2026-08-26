import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Lohnkosten } from "../../types/stammdaten";

const columnDefs: ColDef<Lohnkosten>[] = [
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "werk_id", headerName: "Werk-ID" },
  { field: "rolle", headerName: "Rolle" },
  { field: "kosten_pro_stunde", headerName: "EUR/h" },
  { field: "source_currency", headerName: "Quellwährung" },
  { field: "source_rate", headerName: "Originalsatz" },
  { field: "kostenstelle", headerName: "Kostenstelle" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "werk_id", label: "Werk-ID", type: "number", step: "1" },
  {
    name: "rolle",
    label: "Rolle",
    type: "select",
    options: [
      { value: "produktion", label: "Produktion" },
      { value: "setup", label: "Setup" },
      { value: "sonstig", label: "Sonstig" },
    ],
  },
  { name: "kosten_pro_stunde", label: "Kosten EUR/h", type: "number", required: true, step: "0.01" },
  { name: "source_currency", label: "Quellwährung", type: "text" },
  { name: "source_rate", label: "Originalsatz", type: "number", step: "0.01" },
  { name: "kostenstelle", label: "Kostenstelle", type: "text", required: true },
  { name: "gueltig_ab", label: "Gültig ab", type: "date", required: true },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

export function LohnkostenPage() {
  return (
    <StammdatenGrid<Lohnkosten>
      title="Lohnkosten"
      entityLabel="Lohnsatz"
      endpoint="/lohnkosten"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={{
        bezeichnung: "",
        kosten_pro_stunde: 0,
        kostenstelle: "",
        gueltig_ab: new Date().toISOString().slice(0, 10),
        aktiv: true,
        rolle: "produktion",
        werk_id: null,
      }}
    />
  );
}
