import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Materialgruppe } from "../../types/materialgruppe";
import {
  loadMaterialgruppeFormValues,
  submitMaterialgruppeFormValues,
} from "../../utils/materialgruppeFormDecimals";

const emptyFormValues = {
  gruppe: "",
  bezeichnung: "",
  schmelzdichte_kg_m3: 0,
  waermekapazitaet_j_kg_k: 0,
  waermeleitfaehigkeit_w_m_k: 0,
  werkzeugtemperatur_c: 0,
  schmelzetemperatur_c: 0,
  entformungstemperatur_c: 0,
  aktiv: true,
};

export function MaterialgruppenPage() {
  const t = useT();

  const columnDefs = useMemo(
    (): ColDef<Materialgruppe>[] => [
      { field: "gruppe", headerName: t("masterData.key"), pinned: "left", width: 110 },
      { field: "bezeichnung", headerName: t("masterData.designation"), minWidth: 180 },
      { field: "schmelzdichte_kg_m3", headerName: t("masterData.meltDensityCol"), width: 150 },
      {
        field: "waermekapazitaet_j_kg_k",
        headerName: t("masterData.heatCapacityCol"),
        width: 170,
      },
      {
        field: "waermeleitfaehigkeit_w_m_k",
        headerName: t("masterData.thermalConductivityCol"),
        width: 150,
      },
      { field: "werkzeugtemperatur_c", headerName: t("masterData.moldTempCol"), width: 120 },
      { field: "schmelzetemperatur_c", headerName: t("masterData.meltTempCol"), width: 120 },
      {
        field: "entformungstemperatur_c",
        headerName: t("masterData.ejectionTempCol"),
        width: 130,
      },
      { field: "aktiv", headerName: t("common.active"), width: 90 },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      {
        name: "gruppe",
        label: t("masterData.groupKey"),
        type: "text",
        required: true,
        hint: t("masterData.groupKeyHint"),
      },
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      {
        name: "schmelzdichte_kg_m3",
        label: t("masterData.meltDensity"),
        type: "number",
        required: true,
        step: "0.01",
      },
      {
        name: "waermekapazitaet_j_kg_k",
        label: t("masterData.heatCapacity"),
        type: "number",
        required: true,
        step: "0.01",
      },
      {
        name: "waermeleitfaehigkeit_w_m_k",
        label: t("masterData.thermalConductivity"),
        type: "number",
        required: true,
        step: "0.0001",
      },
      {
        name: "werkzeugtemperatur_c",
        label: t("masterData.moldTemp"),
        type: "number",
        required: true,
        step: "0.1",
      },
      {
        name: "schmelzetemperatur_c",
        label: t("masterData.meltTemp"),
        type: "number",
        required: true,
        step: "0.1",
      },
      {
        name: "entformungstemperatur_c",
        label: t("masterData.ejectionTemp"),
        type: "number",
        required: true,
        step: "0.1",
        hint: t("masterData.ejectionTempHint"),
      },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  return (
    <StammdatenGrid<Materialgruppe>
      title={t("nav.materialGroups")}
      description={t("pages.materialGroupsDesc")}
      entityLabel={t("masterData.materialGroup")}
      endpoint="/materialgruppen"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={emptyFormValues}
      formMaxWidthClassName="max-w-2xl"
      formBanner={<p>{t("masterData.materialGroupBanner")}</p>}
      transformLoadValues={(values) => loadMaterialgruppeFormValues(values)}
      transformSubmitValues={(values) => submitMaterialgruppeFormValues(values)}
    />
  );
}
