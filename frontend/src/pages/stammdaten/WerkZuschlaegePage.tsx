import type { ColDef } from "ag-grid-community";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Werk, WerkZuschlag } from "../../types/stammdaten";

const columnDefs: ColDef<WerkZuschlag>[] = [
  { field: "typ", headerName: "Typ" },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "satz_prozent", headerName: "Satz %" },
  { field: "kostenbasis", headerName: "Kostenbasis" },
  { field: "aktiv", headerName: "Aktiv" },
];

export function WerkZuschlaegePage() {
  const [werke, setWerke] = useState<Werk[]>([]);
  const [werkId, setWerkId] = useState<number | "">("");

  useEffect(() => {
    api.get<Werk[]>("/werke").then((rows) => {
      setWerke(rows.filter((w) => w.aktiv));
      if (rows.length > 0) setWerkId(rows[0].id);
    });
  }, []);

  const formFields: FormField[] = useMemo(
    () => [
      { name: "typ", label: "Typ", type: "text", required: true },
      { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
      { name: "satz_prozent", label: "Satz (%)", type: "number", required: true, step: "0.01" },
      { name: "kostenbasis", label: "Kostenbasis", type: "text", required: true },
      { name: "aktiv", label: "Aktiv", type: "checkbox" },
    ],
    [],
  );

  if (werkId === "") {
    return <p className="text-sm text-gray-600">Lade Werke…</p>;
  }

  return (
    <div className="space-y-3">
      <label className="block max-w-md text-sm">
        <span className="font-medium text-gray-700">Werk</span>
        <select
          value={werkId}
          onChange={(e) => setWerkId(Number(e.target.value))}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
        >
          {werke.map((w) => (
            <option key={w.id} value={w.id}>
              {w.code} – {w.name}
            </option>
          ))}
        </select>
      </label>
      <StammdatenGrid<WerkZuschlag>
        key={werkId}
        title="Werk-Zuschläge"
        entityLabel="Werk-Zuschlag"
        endpoint={`/werke/${werkId}/zuschlaege`}
        columnDefs={columnDefs}
        formFields={formFields}
        emptyFormValues={{
          werk_id: Number(werkId),
          typ: "handling_oem_kaufteil",
          bezeichnung: "",
          satz_prozent: 0,
          kostenbasis: "einkaufspreis",
          aktiv: true,
        }}
      />
    </div>
  );
}
