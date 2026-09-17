import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import { ZUSCHLAGSSATZ_TYP_OPTIONS } from "../../constants/zuschlagssatzTypen";
import type { Zuschlagssatz } from "../../types/stammdaten";
import {
  loadZuschlagssatzFormValues,
  submitZuschlagssatzFormValues,
} from "../../utils/zuschlagssatzFormDecimals";

const TYP_LABEL_KEYS: Record<string, string> = {
  GEMEINKOSTEN: "masterData.typGemeinkosten",
  GEWINN: "masterData.typGewinn",
  VERSCHROTTUNG: "masterData.typVerschrottung",
  mgk_kaufteil_selbst: "masterData.typMgkSelbst",
  mgk_kaufteil_oem: "masterData.typMgkOem",
  fgk: "masterData.typFgk",
  vvgk: "masterData.typVvgk",
  gewinn: "masterData.typGewinnProfit",
  skonto: "masterData.typSkonto",
};

const emptyFormValues = {
  bezeichnung: "",
  satz_prozent: 0,
  typ: "GEMEINKOSTEN",
  aktiv: true,
};

export function ZuschlagssaetzePage() {
  const t = useT();

  const columnDefs = useMemo(
    (): ColDef<Zuschlagssatz>[] => [
      { field: "bezeichnung", headerName: t("masterData.designation") },
      { field: "satz_prozent", headerName: t("masterData.ratePercent") },
      { field: "typ", headerName: t("masterData.type") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      {
        name: "satz_prozent",
        label: t("masterData.ratePercent"),
        type: "number",
        required: true,
        step: "0.01",
      },
      {
        name: "typ",
        label: t("masterData.type"),
        type: "select",
        required: true,
        options: ZUSCHLAGSSATZ_TYP_OPTIONS.map((opt) => ({
          value: opt.value,
          label: t(TYP_LABEL_KEYS[opt.value] ?? opt.label),
        })),
      },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  return (
    <StammdatenGrid<Zuschlagssatz>
      title={t("nav.markups")}
      description={t("pages.markupsDesc")}
      entityLabel={t("masterData.markupRate")}
      endpoint="/zuschlagssaetze"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      transformLoadValues={(values) => loadZuschlagssatzFormValues(values)}
      transformSubmitValues={(values) => submitZuschlagssatzFormValues(values)}
    />
  );
}
