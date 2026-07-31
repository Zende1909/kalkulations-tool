import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { Maschine } from "../../types/stammdaten";

const columnDefs: ColDef<Maschine>[] = [
  { field: "maschinen_nr", headerName: "Maschinen-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "stundensatz", headerName: "Stundensatz" },
  { field: "schliesskraft_t", headerName: "Schließkraft (t)" },
  { field: "aktiv", headerName: "Aktiv" },
];

const defaultRow = {
  bezeichnung: "Neue Maschine",
  maschinen_nr: `MAS-${Date.now()}`,
  stundensatz: 0,
  schliesskraft_t: 0,
  aktiv: true,
};

export function MaschinenPage() {
  return (
    <StammdatenGrid<Maschine>
      title="Maschinen"
      endpoint="/maschinen"
      columnDefs={columnDefs}
      defaultRow={defaultRow}
    />
  );
}
