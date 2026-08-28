import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import { ZUSCHLAGSSATZ_TYP_OPTIONS } from "../../constants/zuschlagssatzTypen";
import type { Zuschlagssatz } from "../../types/stammdaten";
import {
  loadZuschlagssatzFormValues,
  submitZuschlagssatzFormValues,
} from "../../utils/zuschlagssatzFormDecimals";

const columnDefs: ColDef<Zuschlagssatz>[] = [
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "satz_prozent", headerName: "Satz (%)" },
  { field: "typ", headerName: "Typ" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "satz_prozent", label: "Satz (%)", type: "number", required: true, step: "0.01" },
  {
    name: "typ",
    label: "Typ",
    type: "select",
    required: true,
    options: ZUSCHLAGSSATZ_TYP_OPTIONS,
  },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  satz_prozent: 0,
  typ: "GEMEINKOSTEN",
  aktiv: true,
};

export function ZuschlagssaetzePage() {
  return (
    <StammdatenGrid<Zuschlagssatz>
      title="Zuschlagssätze"
      entityLabel="Zuschlagssatz"
      endpoint="/zuschlagssaetze"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadZuschlagssatzFormValues(values)}
      transformSubmitValues={(values) => submitZuschlagssatzFormValues(values)}
    />
  );
}
