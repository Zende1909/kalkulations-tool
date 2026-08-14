import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Kaufteil } from "../../types/baugruppe";

const columnDefs: ColDef<Kaufteil>[] = [
  { field: "artikelnummer", headerName: "Artikel-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "lieferant", headerName: "Lieferant" },
  { field: "preis", headerName: "Preis" },
  { field: "einheit", headerName: "Einheit" },
  { field: "waehrung", headerName: "Währung" },
  { field: "aktiv", headerName: "Aktiv" },
];

const formFields: FormField[] = [
  { name: "artikelnummer", label: "Artikel-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "beschreibung", label: "Beschreibung", type: "text" },
  { name: "lieferant", label: "Lieferant", type: "text" },
  { name: "einheit", label: "Einheit", type: "text", required: true },
  { name: "preis", label: "Preis", type: "number", required: true, step: "0.01" },
  { name: "waehrung", label: "Währung", type: "text", required: true },
  { name: "gueltig_ab", label: "Gültig ab", type: "date" },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  artikelnummer: "",
  bezeichnung: "",
  beschreibung: "",
  lieferant: "",
  einheit: "Stück",
  preis: 0,
  waehrung: "EUR",
  gueltig_ab: null,
  aktiv: true,
};

export function KaufteilePage() {
  return (
    <StammdatenGrid<Kaufteil>
      title="Kaufteile"
      entityLabel="Kaufteil"
      endpoint="/kaufteile"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
    />
  );
}
