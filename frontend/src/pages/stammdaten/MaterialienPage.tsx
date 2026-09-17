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
import { useT } from "../../i18n";
import {
  loadMaterialFormValues,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

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
  const t = useT();
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

  const columnDefs = useMemo(
    (): ColDef<Material>[] => [
      {
        field: "material_nr",
        headerName: t("masterData.materialNo"),
        minWidth: 130,
        pinned: "left",
      },
      { field: "bezeichnung", headerName: t("masterData.designation"), minWidth: 180 },
      {
        field: "preis_pro_kg",
        headerName: t("masterData.pricePerKgCol"),
        type: "numericColumn",
        valueFormatter: decimalValueFormatter(4),
        cellClass: "text-right",
        headerClass: "ag-right-aligned-header",
        minWidth: 110,
      },
      {
        field: "dichte",
        headerName: t("masterData.density"),
        type: "numericColumn",
        valueFormatter: decimalValueFormatter(4),
        cellClass: "text-right",
        headerClass: "ag-right-aligned-header",
        minWidth: 100,
      },
      {
        field: "injection_pressure_kg_cm2",
        headerName: t("masterData.injectionPressureCol"),
        type: "numericColumn",
        valueFormatter: decimalValueFormatter(2),
        cellClass: "text-right",
        headerClass: "ag-right-aligned-header",
        minWidth: 150,
      },
      {
        field: "materialgruppe",
        headerName: t("masterData.materialGroupField"),
        minWidth: 140,
      },
      { field: "waehrung", headerName: t("masterData.currency"), minWidth: 90, maxWidth: 110 },
      {
        field: "aktiv",
        headerName: t("masterData.status"),
        minWidth: 110,
        maxWidth: 130,
        cellRenderer: activeStatusCellRenderer,
        filter: false,
      },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "material_nr", label: t("masterData.materialNo"), type: "text", required: true },
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      {
        name: "preis_pro_kg",
        label: t("masterData.pricePerKg"),
        type: "number",
        required: true,
        step: "0.0001",
        hint: t("masterData.decimalHint", { example: t("masterData.examplePrice") }),
      },
      {
        name: "dichte",
        label: t("masterData.density"),
        type: "number",
        required: true,
        step: "0.0001",
        hint: t("masterData.decimalHint", { example: t("masterData.exampleDensity") }),
      },
      { name: "waehrung", label: t("masterData.currency"), type: "text", required: true },
      {
        name: "injection_pressure_kg_cm2",
        label: t("masterData.injectionPressure"),
        type: "number",
        required: true,
        step: "0.01",
        hint: t("masterData.injectionPressureHint"),
      },
      {
        name: "materialgruppe",
        label: t("masterData.materialGroupField"),
        type: "select",
        options: [
          "",
          ...gruppen.map((gruppe) => ({
            value: gruppe.gruppe,
            label: `${gruppe.gruppe} – ${gruppe.bezeichnung}`,
          })),
        ],
        hint: t("masterData.materialGroupHint"),
      },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [gruppen, t],
  );

  return (
    <StammdatenGrid<Material>
      title={t("nav.materials")}
      description={t("pages.materialsDesc")}
      entityLabel={t("masterData.material")}
      endpoint="/materialien"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadMaterialFormValues(values)}
      transformSubmitValues={(values) => submitMaterialFormValues(values)}
    />
  );
}
