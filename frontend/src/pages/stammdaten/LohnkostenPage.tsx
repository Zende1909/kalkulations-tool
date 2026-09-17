import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Lohnkosten } from "../../types/stammdaten";
import {
  loadLohnkostenFormValues,
  submitLohnkostenFormValues,
} from "../../utils/lohnkostenFormDecimals";

export function LohnkostenPage() {
  const t = useT();

  const columnDefs = useMemo(
    (): ColDef<Lohnkosten>[] => [
      { field: "bezeichnung", headerName: t("masterData.designation") },
      { field: "werk_id", headerName: t("masterData.plantId") },
      { field: "rolle", headerName: t("masterData.role") },
      { field: "kosten_pro_stunde", headerName: t("masterData.eurPerHour") },
      { field: "source_currency", headerName: t("masterData.sourceCurrency") },
      { field: "source_rate", headerName: t("masterData.originalRate") },
      { field: "kostenstelle", headerName: t("masterData.costCenter") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      { name: "werk_id", label: t("masterData.plantId"), type: "number", step: "1" },
      {
        name: "rolle",
        label: t("masterData.role"),
        type: "select",
        options: [
          { value: "produktion", label: t("masterData.roleProduction") },
          { value: "setup", label: t("masterData.roleSetup") },
          { value: "sonstig", label: t("masterData.roleOther") },
        ],
      },
      {
        name: "kosten_pro_stunde",
        label: t("masterData.costEurH"),
        type: "number",
        required: true,
        step: "0.0001",
      },
      { name: "source_currency", label: t("masterData.sourceCurrency"), type: "text" },
      { name: "source_rate", label: t("masterData.originalRate"), type: "number", step: "0.0001" },
      { name: "kostenstelle", label: t("masterData.costCenter"), type: "text", required: true },
      { name: "gueltig_ab", label: t("masterData.validFrom"), type: "date", required: true },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  return (
    <StammdatenGrid<Lohnkosten>
      title={t("nav.laborCosts")}
      description={t("pages.laborCostsDesc")}
      entityLabel={t("masterData.laborRate")}
      endpoint="/lohnkosten"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={{
        bezeichnung: "",
        kosten_pro_stunde: 0,
        kostenstelle: "",
        gueltig_ab: new Date().toISOString().slice(0, 10),
        aktiv: true,
        rolle: "produktion",
        werk_id: null,
      }}
      transformLoadValues={(values) => loadLohnkostenFormValues(values)}
      transformSubmitValues={(values) => submitLohnkostenFormValues(values)}
    />
  );
}
