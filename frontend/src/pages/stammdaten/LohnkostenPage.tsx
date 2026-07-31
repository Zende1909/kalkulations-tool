import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { Lohnkosten } from "../../types/stammdaten";

const columnDefs: ColDef<Lohnkosten>[] = [
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "kosten_pro_stunde", headerName: "Kosten/h" },
  { field: "kostenstelle", headerName: "Kostenstelle" },
  { field: "gueltig_ab", headerName: "Gültig ab" },
  { field: "aktiv", headerName: "Aktiv" },
];

const defaultRow = {
  bezeichnung: "Neue Lohnkosten",
  kosten_pro_stunde: 0,
  kostenstelle: "KS-001",
  gueltig_ab: new Date().toISOString().slice(0, 10),
  aktiv: true,
};

export function LohnkostenPage() {
  return (
    <StammdatenGrid<Lohnkosten>
      title="Lohnkosten"
      endpoint="/lohnkosten"
      columnDefs={columnDefs}
      defaultRow={defaultRow}
    />
  );
}
