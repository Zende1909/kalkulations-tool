import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { Zuschlagssatz } from "../../types/stammdaten";

const columnDefs: ColDef<Zuschlagssatz>[] = [
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "satz_prozent", headerName: "Satz (%)" },
  { field: "typ", headerName: "Typ" },
  { field: "aktiv", headerName: "Aktiv" },
];

const defaultRow = {
  bezeichnung: "Neuer Zuschlagssatz",
  satz_prozent: 0,
  typ: "GEMEINKOSTEN",
  aktiv: true,
};

export function ZuschlagssaetzePage() {
  return (
    <StammdatenGrid<Zuschlagssatz>
      title="Zuschlagssätze"
      endpoint="/zuschlagssaetze"
      columnDefs={columnDefs}
      defaultRow={defaultRow}
    />
  );
}
