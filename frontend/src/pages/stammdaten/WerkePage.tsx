import type { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land, Werk } from "../../types/stammdaten";

const columnDefs: ColDef<Werk>[] = [
  { field: "code", headerName: "Code" },
  { field: "name", headerName: "Name" },
  { field: "land_id", headerName: "Land-ID" },
  { field: "currency", headerName: "Währung" },
  { field: "fx_to_eur", headerName: "FX → EUR" },
  { field: "aktiv", headerName: "Aktiv" },
];

export function WerkePage() {
  const [lands, setLands] = useState<Land[]>([]);
  useEffect(() => {
    api.get<Land[]>("/laender").then(setLands).catch(() => setLands([]));
  }, []);

  const formFields: FormField[] = [
    {
      name: "land_id",
      label: "Land",
      type: "select",
      required: true,
      options: lands.map((l) => ({ value: String(l.id), label: `${l.code} – ${l.name}` })),
    },
    { name: "code", label: "Code", type: "text", required: true },
    { name: "name", label: "Name", type: "text", required: true },
    { name: "currency", label: "Quellwährung", type: "text", required: true },
    { name: "fx_to_eur", label: "Wechselkurs → EUR", type: "number", required: true, step: "0.0001" },
    { name: "aktiv", label: "Aktiv", type: "checkbox" },
  ];

  return (
    <StammdatenGrid<Werk>
      title="Werke / Standorte"
      entityLabel="Werk"
      endpoint="/werke"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={{
        land_id: lands[0]?.id ?? 0,
        code: "",
        name: "",
        currency: "USD",
        fx_to_eur: 0.92,
        aktiv: true,
      }}
    />
  );
}
