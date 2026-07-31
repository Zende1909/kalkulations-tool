import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { Material } from "../../types/stammdaten";

const columnDefs: ColDef<Material>[] = [
  { field: "material_nr", headerName: "Material-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "preis_pro_kg", headerName: "Preis/kg" },
  { field: "dichte", headerName: "Dichte" },
  { field: "waehrung", headerName: "Währung" },
  { field: "aktiv", headerName: "Aktiv" },
];

const defaultRow = {
  bezeichnung: "Neues Material",
  material_nr: `MAT-${Date.now()}`,
  preis_pro_kg: 0,
  dichte: 1.0,
  waehrung: "EUR",
  aktiv: true,
};

export function MaterialienPage() {
  return (
    <StammdatenGrid<Material>
      title="Materialien"
      endpoint="/materialien"
      columnDefs={columnDefs}
      defaultRow={defaultRow}
    />
  );
}
