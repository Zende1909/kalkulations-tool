import { useEffect, useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import {
  activeStatusCellRenderer,
  decimalValueFormatter,
} from "../../components/ui/agGridFormatters";
import type { Material } from "../../types/stammdaten";
import type { Materialgruppe } from "../../types/materialgruppe";
import {
  loadMaterialFormValues,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

const columnDefs: ColDef<Material>[] = [
  { field: "material_nr", headerName: "Material-Nr.", minWidth: 130, pinned: "left" },
  { field: "bezeichnung", headerName: "Bezeichnung", minWidth: 180 },
  {
    field: "preis_pro_kg",
    headerName: "Preis/kg",
    type: "numericColumn",
    valueFormatter: decimalValueFormatter(4),
    cellClass: "text-right",
    headerClass: "ag-right-aligned-header",
    minWidth: 110,
  },
  {
    field: "dichte",
    headerName: "Dichte",
    type: "numericColumn",
    valueFormatter: decimalValueFormatter(4),
    cellClass: "text-right",
    headerClass: "ag-right-aligned-header",
    minWidth: 100,
  },
  {
    field: "injection_pressure_kg_cm2",
    headerName: "Einspritzdruck kg/cm²",
    type: "numericColumn",
    valueFormatter: decimalValueFormatter(2),
    cellClass: "text-right",
    headerClass: "ag-right-aligned-header",
    minWidth: 150,
  },
  { field: "materialgruppe", headerName: "Materialgruppe", minWidth: 140 },
  { field: "waehrung", headerName: "Währung", minWidth: 90, maxWidth: 110 },
  {
    field: "aktiv",
    headerName: "Status",
    minWidth: 110,
    maxWidth: 130,
    cellRenderer: activeStatusCellRenderer,
    filter: false,
  },
];

const baseFormFields: FormField[] = [
  { name: "material_nr", label: "Material-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  {
    name: "preis_pro_kg",
    label: "Preis pro kg",
    type: "number",
    required: true,
    step: "0.0001",
    hint: "Dezimalwert, z. B. 2,10 oder 2.10",
  },
  {
    name: "dichte",
    label: "Dichte",
    type: "number",
    required: true,
    step: "0.0001",
    hint: "Dezimalwert, z. B. 1,04 oder 1.04",
  },
  { name: "waehrung", label: "Währung", type: "text", required: true },
  {
    name: "injection_pressure_kg_cm2",
    label: "Einspritzdruck",
    type: "number",
    required: true,
    step: "0.01",
    hint: "kg/cm² – Standard 500 bei neuen Materialien",
  },
  {
    name: "materialgruppe",
    label: "Materialgruppe",
    type: "select",
    options: [""],
    hint: "Aus den Stammdaten Materialgruppen. Steuert die Zykluszeit-Schätzung.",
  },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  material_nr: "",
  preis_pro_kg: 0,
  dichte: 1.0,
  injection_pressure_kg_cm2: 500,
  materialgruppe: null,
  waehrung: "EUR",
  aktiv: true,
};

export function MaterialienPage() {
  const [gruppen, setGruppen] = useState<Materialgruppe[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Materialgruppe[]>("/materialgruppen?nur_aktiv=true")
      .then((rows) => {
        if (!cancelled) setGruppen(rows);
      })
      .catch(() => {
        if (!cancelled) setGruppen([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const formFields = useMemo(
    (): FormField[] =>
      baseFormFields.map((field) =>
        field.name === "materialgruppe"
          ? {
              ...field,
              options: [
                "",
                ...gruppen.map((gruppe) => ({
                  value: gruppe.gruppe,
                  label: `${gruppe.gruppe} – ${gruppe.bezeichnung}`,
                })),
              ],
            }
          : field,
      ),
    [gruppen],
  );

  return (
    <StammdatenGrid<Material>
      title="Materialien"
      description="Materialstammdaten mit Preisen, Dichte, Einspritzdruck und Materialgruppe für Zykluszeit-Schätzungen."
      entityLabel="Material"
      endpoint="/materialien"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadMaterialFormValues(values)}
      transformSubmitValues={(values) => submitMaterialFormValues(values)}
    />
  );
}
