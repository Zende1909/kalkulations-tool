import { useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";

import { OptionalHierarchySelector } from "../../components/hierarchy/OptionalHierarchySelector";
import type { HierarchySelection } from "../../components/hierarchy/HierarchySelector";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Kaufteil } from "../../types/baugruppe";
import {
  loadKaufteilFormValues,
  submitKaufteilFormValues,
} from "../../utils/kaufteilFormDecimals";

function hierarchyFromFormValues(
  values: Record<string, string | number | boolean>,
): HierarchySelection {
  const toId = (key: string): number | null => {
    const raw = values[key];
    if (raw === "" || raw == null) return null;
    const n = typeof raw === "number" ? raw : Number(raw);
    return Number.isFinite(n) ? n : null;
  };
  return {
    customer_id: toId("customer_id"),
    program_id: toId("program_id"),
    project_id: toId("project_id"),
  };
}

function projectLabel(row: Kaufteil): string {
  if (row.project_id == null) return "(Standard)";
  return `Projekt #${row.project_id}`;
}

const columnDefs: ColDef<Kaufteil>[] = [
  { field: "artikelnummer", headerName: "Artikel-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  {
    field: "project_id",
    headerName: "Projekt",
    valueFormatter: (p) => projectLabel(p.data as Kaufteil),
  },
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
  {
    field: "aktiv",
    headerName: "Aktiv",
    valueFormatter: (p) => (p.value ? "Ja" : "Nein (inaktiv)"),
  },
];

const formFields: FormField[] = [
  { name: "artikelnummer", label: "Artikel-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "beschreibung", label: "Beschreibung", type: "text" },
  { name: "lieferant", label: "Lieferant", type: "text" },
  { name: "einheit", label: "Einheit", type: "text", required: true },
  { name: "preis", label: "Preis", type: "number", required: true, step: "0.0001", hint: "Dezimalwert, z. B. 0,10 oder 0.10" },
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
  {
    name: "sga_override_aktiv",
    label: "SG&A-Satz manuell überschreiben",
    type: "checkbox",
    hint: "Ohne Aktivierung gilt der zentrale Standard-SG&A-Satz für Kaufteile.",
  },
  {
    name: "sga_satz_manuell",
    label: "Manueller SG&A-Satz (%)",
    type: "number",
    step: "0.01",
    hint: "Nur bei aktivierter Überschreibung. Basis: Einkauf + MGK + OEM-Handling.",
  },
  { name: "gueltig_ab", label: "Gültig ab", type: "date" },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const HIERARCHY_KEYS = ["customer_id", "program_id", "project_id"] as const;

const emptyFormValues = {
  artikelnummer: "",
  bezeichnung: "",
  beschreibung: "",
  lieferant: "",
  einheit: "Stück",
  preis: 0,
  waehrung: "EUR",
  nominierung: "selbstnominiert" as const,
  sga_override_aktiv: false,
  sga_satz_manuell: null as number | null,
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
    if (hierarchy.project_id != null) {
      params.set("project_id", String(hierarchy.project_id));
      params.set("include_standard", "true");
    }
    return params.toString();
  }, [hierarchy]);

  return (
    <StammdatenGrid<Kaufteil>
      title="Kaufteile"
      entityLabel="Kaufteil"
      endpoint="/kaufteile"
      listQuery={listQuery}
      additionalFormKeys={[...HIERARCHY_KEYS, "sga_override_aktiv", "sga_satz_manuell"]}
      formMaxWidthClassName="max-w-2xl"
      formExtraContent={(values, onChange) => (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Projektzuordnung</h4>
          <OptionalHierarchySelector
            value={hierarchyFromFormValues(values)}
            onChange={(next) => {
              onChange("customer_id", next.customer_id ?? "");
              onChange("program_id", next.program_id ?? "");
              onChange("project_id", next.project_id ?? "");
            }}
          />
        </div>
      )}
      toolbarExtra={
        <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4">
          <p className="mb-2 text-sm text-gray-600">
            Filter: Kunde → Programm → Projekt (optional). Ohne Filter bleiben alle Kaufteile
            sichtbar. Mit Projektfilter werden projektbezogene und Standardkaufteile angezeigt.
            Altbestand ohne Nominierung bitte nachklassifizieren – sonst schlägt die
            Baugruppenkalkulation mit Hinweis fehl (kein stiller Standardsatz).
          </p>
          <OptionalHierarchySelector value={hierarchy} onChange={setHierarchy} />
        </div>
      }
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadKaufteilFormValues(values)}
      transformSubmitValues={(values) => submitKaufteilFormValues(values)}
    />
  );
}
