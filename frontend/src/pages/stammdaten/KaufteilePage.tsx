import { useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";

import { HierarchySelector } from "../../components/hierarchy/HierarchySelector";
import type { HierarchySelection } from "../../components/hierarchy/HierarchySelector";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Kaufteil } from "../../types/baugruppe";

const columnDefs: ColDef<Kaufteil>[] = [
  { field: "artikelnummer", headerName: "Artikel-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  {
    field: "nominierung",
    headerName: "Nominierung",
    valueFormatter: (p) => {
      if (p.value === "selbstnominiert") return "selbstnominiert";
      if (p.value === "oem_nominiert") return "OEM-nominiert";
      return "— nicht klassifiziert";
    },
  },
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
  {
    name: "nominierung",
    label: "Nominierung (MGK)",
    type: "select",
    required: true,
    options: [
      { value: "selbstnominiert", label: "selbstnominiert (MGK aus Stammdaten)" },
      { value: "oem_nominiert", label: "OEM-nominiert (MGK aus Stammdaten)" },
    ],
  },
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
  nominierung: "selbstnominiert" as const,
  customer_id: null as number | null,
  program_id: null as number | null,
  project_id: null as number | null,
  gueltig_ab: null as string | null,
  aktiv: true,
};

export function KaufteilePage() {
  const [hierarchy, setHierarchy] = useState<HierarchySelection>({
    customer_id: null,
    program_id: null,
    project_id: null,
  });

  const listQuery = useMemo(() => {
    const params = new URLSearchParams();
    if (hierarchy.customer_id != null) params.set("customer_id", String(hierarchy.customer_id));
    if (hierarchy.program_id != null) params.set("program_id", String(hierarchy.program_id));
    if (hierarchy.project_id != null) params.set("project_id", String(hierarchy.project_id));
    return params.toString();
  }, [hierarchy]);

  return (
    <StammdatenGrid<Kaufteil>
      title="Kaufteile"
      entityLabel="Kaufteil"
      endpoint="/kaufteile"
      listQuery={listQuery}
      toolbarExtra={
        <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4">
          <p className="mb-2 text-sm text-gray-600">
            Filter: Kunde → Programm → Projekt (optional). Ohne Filter bleiben alle Kaufteile
            sichtbar. Altbestand ohne Nominierung bitte nachklassifizieren – sonst schlägt die
            Baugruppenkalkulation mit Hinweis fehl (kein stiller Standardsatz).
          </p>
          <HierarchySelector value={hierarchy} onChange={setHierarchy} />
        </div>
      }
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
    />
  );
}
