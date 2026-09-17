import { useEffect, useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";

import { OptionalHierarchySelector } from "../../components/hierarchy/OptionalHierarchySelector";
import type { HierarchySelection } from "../../components/hierarchy/HierarchySelector";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import { useActiveProject } from "../../context/ActiveProjectContext";
import { useT } from "../../i18n";
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

const HIERARCHY_KEYS = ["customer_id", "program_id", "project_id"] as const;

const baseEmptyFormValues = {
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
  const t = useT();
  const { selection } = useActiveProject();
  const [hierarchy, setHierarchy] = useState<HierarchySelection>(() => ({
    customer_id: selection.customer_id,
    program_id: selection.program_id,
    project_id: selection.project_id,
  }));

  useEffect(() => {
    setHierarchy({
      customer_id: selection.customer_id,
      program_id: selection.program_id,
      project_id: selection.project_id,
    });
  }, [selection.customer_id, selection.program_id, selection.project_id]);

  const emptyFormValues = useMemo(
    () => ({
      ...baseEmptyFormValues,
      customer_id: hierarchy.customer_id,
      program_id: hierarchy.program_id,
      project_id: hierarchy.project_id,
    }),
    [hierarchy],
  );

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

  const columnDefs = useMemo(
    (): ColDef<Kaufteil>[] => [
      { field: "artikelnummer", headerName: t("masterData.articleNo") },
      { field: "bezeichnung", headerName: t("masterData.designation") },
      {
        field: "project_id",
        headerName: t("masterData.projectLabel"),
        valueFormatter: (p) => {
          const row = p.data as Kaufteil;
          if (row.project_id == null) return t("masterData.standardTag");
          return t("masterData.projectHash", { id: row.project_id });
        },
      },
      {
        field: "nominierung",
        headerName: t("masterData.nomination"),
        valueFormatter: (p) => {
          if (p.value === "selbstnominiert") return t("masterData.selfNominated");
          if (p.value === "oem_nominiert") return t("masterData.oemNominated");
          return t("masterData.notClassified");
        },
      },
      { field: "lieferant", headerName: t("masterData.supplier") },
      { field: "preis", headerName: t("masterData.price") },
      { field: "einheit", headerName: t("masterData.unit") },
      { field: "waehrung", headerName: t("masterData.currency") },
      {
        field: "aktiv",
        headerName: t("common.active"),
        valueFormatter: (p) => (p.value ? t("common.yes") : t("masterData.noInactive")),
      },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "artikelnummer", label: t("masterData.articleNo"), type: "text", required: true },
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      { name: "beschreibung", label: t("masterData.description"), type: "text" },
      { name: "lieferant", label: t("masterData.supplier"), type: "text" },
      { name: "einheit", label: t("masterData.unit"), type: "text", required: true },
      {
        name: "preis",
        label: t("masterData.price"),
        type: "number",
        required: true,
        step: "0.0001",
        hint: t("masterData.decimalHint", { example: t("masterData.exampleEnergy") }),
      },
      { name: "waehrung", label: t("masterData.currency"), type: "text", required: true },
      {
        name: "nominierung",
        label: t("masterData.nominationMgk"),
        type: "select",
        required: true,
        options: [
          { value: "selbstnominiert", label: t("masterData.selfNominatedMgk") },
          { value: "oem_nominiert", label: t("masterData.oemNominatedMgk") },
        ],
      },
      {
        name: "sga_override_aktiv",
        label: t("masterData.sgaOverride"),
        type: "checkbox",
        hint: t("masterData.sgaOverrideHint"),
      },
      {
        name: "sga_satz_manuell",
        label: t("masterData.sgaManualPct"),
        type: "number",
        step: "0.01",
        hint: t("masterData.sgaManualHint"),
      },
      { name: "gueltig_ab", label: t("masterData.validFrom"), type: "date" },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  return (
    <StammdatenGrid<Kaufteil>
      title={t("nav.purchasedParts")}
      description={t("pages.purchasedPartsDesc")}
      entityLabel={t("masterData.purchasedPart")}
      endpoint="/kaufteile"
      listQuery={listQuery}
      additionalFormKeys={[...HIERARCHY_KEYS, "sga_override_aktiv", "sga_satz_manuell"]}
      formMaxWidthClassName="max-w-2xl"
      formExtraContent={(values, onChange) => (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-800">
            {t("masterData.projectAssignment")}
          </h4>
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
          <p className="mb-2 text-sm text-gray-600">{t("masterData.purchasedPartsFilterHint")}</p>
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
