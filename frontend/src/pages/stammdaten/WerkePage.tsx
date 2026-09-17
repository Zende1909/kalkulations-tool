import type { ColDef } from "ag-grid-community";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land, Werk } from "../../types/stammdaten";
import { WERK_RATE_FRACTION_FIELDS } from "../../utils/decimalInput";
import { loadWerkFormValues, submitWerkFormValues } from "../../utils/werkFormDecimals";

type TFn = (key: string, params?: Record<string, string | number>) => string;

function rateLabels(t: TFn): Record<string, string> {
  return {
    zinssatz: t("masterData.interestRate"),
    versicherungssatz: t("masterData.insuranceRate"),
    instandhaltungssatz: t("masterData.maintenanceRate"),
  };
}

function rateFractionWarnings(
  values: Record<string, string | number | boolean>,
  t: TFn,
): string[] {
  const labels = rateLabels(t);
  const warnings: string[] = [];
  for (const key of WERK_RATE_FRACTION_FIELDS) {
    const raw = values[key];
    if (raw === "" || raw == null) continue;
    const num = typeof raw === "number" ? raw : Number(raw);
    if (Number.isFinite(num) && num > 100) {
      warnings.push(
        t("masterData.rateOutOfRangeUi", { label: labels[key], value: num }),
      );
    }
  }
  return warnings;
}

/** Warnung anhand der API-Rohwerte (Anteil), bevor ×100. */
export function warningsForStoredRateFractions(
  werk: Partial<Werk>,
  t: TFn,
): string[] {
  const labels = rateLabels(t);
  const out: string[] = [];
  for (const key of WERK_RATE_FRACTION_FIELDS) {
    const v = werk[key];
    if (v == null || !Number.isFinite(v)) continue;
    if (v < 0 || v > 1) {
      out.push(
        t("masterData.rateOutOfRangeStored", { label: labels[key], value: v }),
      );
    }
  }
  return out;
}

export function WerkePage() {
  const t = useT();
  const [lands, setLands] = useState<Land[]>([]);
  const [formBannerExtra, setFormBannerExtra] = useState<string[]>([]);

  useEffect(() => {
    api.get<Land[]>("/laender").then(setLands).catch(() => setLands([]));
  }, []);

  const columnDefs = useMemo(
    (): ColDef<Werk>[] => [
      { field: "code", headerName: t("masterData.code") },
      { field: "name", headerName: t("masterData.name") },
      { field: "land_id", headerName: t("masterData.landId") },
      { field: "currency", headerName: t("masterData.currency") },
      { field: "fx_to_eur", headerName: t("masterData.fxToEur") },
      { field: "arbeitstage_pro_jahr", headerName: t("masterData.daysPerYear") },
      { field: "produktionsintervall_arbeitstage", headerName: t("masterData.prodInterval") },
      { field: "oee", headerName: t("masterData.oee01") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields: FormField[] = useMemo(
    () => [
      {
        name: "land_id",
        label: t("masterData.country"),
        type: "select",
        required: true,
        options: lands.map((l) => ({ value: String(l.id), label: `${l.code} – ${l.name}` })),
      },
      { name: "code", label: t("masterData.code"), type: "text", required: true },
      { name: "name", label: t("masterData.name"), type: "text", required: true },
      { name: "currency", label: t("masterData.sourceCurrency"), type: "text", required: true },
      {
        name: "fx_to_eur",
        label: t("masterData.fxToEurLabel"),
        type: "number",
        required: true,
        step: "0.0001",
      },
      {
        name: "arbeitstage_pro_jahr",
        label: t("masterData.workdaysPerYear"),
        type: "number",
        step: "1",
      },
      {
        name: "produktionsintervall_arbeitstage",
        label: t("masterData.productionIntervalDays"),
        type: "number",
        step: "1",
        hint: t("masterData.productionIntervalHint"),
      },
      { name: "schichten_pro_tag", label: t("masterData.shiftsPerDay"), type: "number", step: "1" },
      {
        name: "stunden_pro_schicht",
        label: t("masterData.hoursPerShift"),
        type: "number",
        step: "0.1",
      },
      {
        name: "oee",
        label: t("masterData.oee01"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.oeeHint"),
      },
      {
        name: "space_cost_satz_pro_sqm_jahr",
        label: t("masterData.spaceCostRate"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.spaceCostHint"),
      },
      {
        name: "abschreibungsdauer_jahre",
        label: t("masterData.depreciationYears"),
        type: "number",
        step: "1",
      },
      {
        name: "zinssatz",
        label: t("masterData.interestRatePct"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.ratePercentHint"),
      },
      {
        name: "versicherungssatz",
        label: t("masterData.insuranceRatePct"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.ratePercentHint"),
      },
      {
        name: "instandhaltungssatz",
        label: t("masterData.maintenanceRatePct"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.ratePercentHint"),
      },
      {
        name: "strompreis",
        label: t("masterData.electricityPrice"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.absoluteDecimalHint", { example: t("masterData.exampleEnergy") }),
      },
      {
        name: "druckluftpreis",
        label: t("masterData.compressedAirPrice"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.absoluteDecimalHint", { example: t("masterData.exampleEnergy") }),
      },
      {
        name: "kuehlwasserpreis",
        label: t("masterData.coolingWaterPrice"),
        type: "number",
        step: "0.0001",
        hint: t("masterData.absoluteDecimalHint", { example: t("masterData.exampleCooling") }),
      },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [lands, t],
  );

  return (
    <StammdatenGrid<Werk>
      title={t("nav.plants")}
      description={t("pages.plantsDesc")}
      entityLabel={t("masterData.plant")}
      endpoint="/werke"
      columnDefs={columnDefs}
      formFields={formFields}
      formMaxWidthClassName="max-w-xl"
      formBanner={
        formBannerExtra.length > 0 ? (
          <div className="space-y-1 text-amber-900">
            <p className="font-medium">{t("masterData.unusualStoredRates")}</p>
            <ul className="list-disc pl-4 text-sm">
              {formBannerExtra.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        ) : undefined
      }
      emptyFormValues={{
        land_id: lands[0]?.id ?? 0,
        code: "",
        name: "",
        currency: "USD",
        fx_to_eur: 0.92,
        aktiv: true,
        arbeitstage_pro_jahr: 254,
        produktionsintervall_arbeitstage: 30,
        schichten_pro_tag: 2,
        stunden_pro_schicht: 8,
        oee: 0.9,
        space_cost_satz_pro_sqm_jahr: 30,
        abschreibungsdauer_jahre: 10,
        zinssatz: 0.08,
        versicherungssatz: 0.0045,
        instandhaltungssatz: 0.02,
        strompreis: 0.06,
        druckluftpreis: 0.06,
        kuehlwasserpreis: 0.03,
      }}
      transformLoadValues={(values, mode) => {
        if (mode === "edit") {
          setFormBannerExtra(
            warningsForStoredRateFractions(values as unknown as Partial<Werk>, t),
          );
        } else {
          setFormBannerExtra([]);
        }
        return loadWerkFormValues(values);
      }}
      transformSubmitValues={(values) => {
        const uiWarnings = rateFractionWarnings(values, t);
        if (uiWarnings.length) {
          setFormBannerExtra(uiWarnings);
        }
        return submitWerkFormValues(values);
      }}
    />
  );
}
