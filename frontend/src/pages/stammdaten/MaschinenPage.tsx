import type { ColDef } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Maschine, Werk } from "../../types/stammdaten";
import {
  loadMaschineFormValues,
  submitMaschineFormValues,
} from "../../utils/maschineFormDecimals";

/**
 * Maschinenmaske: nur maschinenabhängige Felder.
 * Standortparameter (Tage/Schichten/OEE/Sätze/Energiepreise) werden am Werk gepflegt.
 */
function buildMachineFormFields(
  werke: Werk[],
  currentWerkId: number | null,
  t: (key: string, params?: Record<string, string | number>) => string,
): FormField[] {
  const active = werke.filter((w) => w.aktiv);
  const current = currentWerkId != null ? werke.find((w) => w.id === currentWerkId) : null;
  const options = [
    { value: "", label: t("masterData.selectPlant") },
    ...active.map((w) => ({
      value: String(w.id),
      label: `${w.code} – ${w.name}`,
    })),
  ];
  if (current && !current.aktiv && !options.some((o) => o.value === String(current.id))) {
    options.push({
      value: String(current.id),
      label: `${current.code} – ${current.name} ${t("masterData.plantInactive")}`,
    });
  }

  return [
    {
      name: "werk_id",
      label: t("masterData.plant"),
      type: "select",
      required: true,
      options,
    },
    { name: "maschinen_nr", label: t("masterData.machineNo"), type: "text", required: true },
    { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
    { name: "maschinentyp", label: t("masterData.machineType"), type: "text" },
    { name: "variante", label: t("masterData.variant"), type: "text" },
    {
      name: "stundensatz",
      label: t("masterData.hourlyRateEurH"),
      type: "number",
      step: "0.0001",
      readOnly: true,
      hint: t("masterData.hourlyRateCalculatedHint"),
    },
    {
      name: "stundensatz_source",
      label: t("masterData.hourlyRateSource"),
      type: "number",
      step: "0.0001",
      readOnly: true,
    },
    { name: "source_currency", label: t("masterData.sourceCurrency"), type: "text", readOnly: true },
    {
      name: "schliesskraft_t",
      label: t("masterData.clampingForceT"),
      type: "number",
      required: true,
      step: "0.1",
    },
    { name: "investment", label: t("masterData.investment"), type: "number", step: "1" },
    { name: "flaeche_sqm", label: t("masterData.areaSqm"), type: "number", step: "0.1" },
    {
      name: "stromverbrauch_kwh_h",
      label: t("masterData.powerConsumption"),
      type: "number",
      step: "0.1",
    },
    {
      name: "druckluftverbrauch_m3_h",
      label: t("masterData.compressedAirConsumption"),
      type: "number",
      step: "0.1",
    },
    {
      name: "kuehlwasserverbrauch_m3_h",
      label: t("masterData.coolingWaterConsumption"),
      type: "number",
      step: "0.1",
    },
    { name: "setup_zeit_min", label: t("masterData.setupTimeMin"), type: "number", step: "1" },
    {
      name: "setup_mitarbeiter",
      label: t("masterData.setupOperators"),
      type: "number",
      step: "0.0001",
      hint: t("masterData.decimalExampleOneFive"),
    },
    { name: "aktiv", label: t("common.active"), type: "checkbox" },
  ];
}

const emptyFormValues = {
  bezeichnung: "",
  maschinen_nr: "",
  stundensatz: 0,
  stundensatz_source: 0,
  schliesskraft_t: 0,
  aktiv: true,
  werk_id: null as number | null,
  source_currency: "",
  maschinentyp: "",
  variante: "",
  investment: null as number | null,
  flaeche_sqm: null as number | null,
  stromverbrauch_kwh_h: null as number | null,
  druckluftverbrauch_m3_h: null as number | null,
  kuehlwasserverbrauch_m3_h: null as number | null,
  setup_zeit_min: null as number | null,
  setup_mitarbeiter: null as number | null,
};

export function MaschinenPage() {
  const t = useT();
  const { canWrite } = useAuth();
  const [werke, setWerke] = useState<Werk[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formWerkId, setFormWerkId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api.get<Werk[]>("/werke").then(setWerke).catch(() => setWerke([]));
  }, [reloadKey]);

  const columnDefs = useMemo(
    (): ColDef<Maschine>[] => [
      { field: "maschinen_nr", headerName: t("masterData.machineNo") },
      { field: "bezeichnung", headerName: t("masterData.designation") },
      { field: "werk_id", headerName: t("masterData.plantId") },
      { field: "stundensatz", headerName: t("masterData.hourlyRateEur") },
      { field: "stundensatz_source", headerName: t("masterData.rateSourceCurrency") },
      { field: "schliesskraft_t", headerName: t("masterData.clampingForceT") },
      { field: "jahresstunden", headerName: t("masterData.annualHours") },
      { field: "setup_zeit_min", headerName: t("masterData.setupMin") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields = useMemo(
    () => buildMachineFormFields(werke, formWerkId, t),
    [werke, formWerkId, t],
  );

  const selectedWerk = useMemo(
    () => (formWerkId != null ? werke.find((w) => w.id === formWerkId) : null),
    [werke, formWerkId],
  );

  const recalculate = useCallback(async () => {
    if (!selectedId || !canWrite) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.post<Maschine>(
        `/maschinen/${selectedId}/recalculate-rate`,
        {},
      );
      const fxSuffix =
        updated.stundensatz_source != null
          ? t("masterData.rateRecalculatedFx", {
              source: updated.stundensatz_source,
              currency: updated.source_currency ?? "",
              fx: selectedWerk?.fx_to_eur ?? t("common.dash"),
            })
          : "";
      setMessage(
        t("masterData.rateRecalculated", {
          rate: Number(updated.stundensatz).toFixed(4),
        }) + fxSuffix,
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("masterData.recalculateFailed"));
    } finally {
      setBusy(false);
    }
  }, [selectedId, canWrite, selectedWerk?.fx_to_eur, t]);

  return (
    <div className="space-y-2">
      {(message || error) && (
        <div
          className={`rounded-md px-3 py-2 text-sm ${
            error ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
          }`}
        >
          {error ?? message}
        </div>
      )}
      <StammdatenGrid<Maschine>
        key={reloadKey}
        title={t("nav.machines")}
        description={t("pages.machinesDesc")}
        entityLabel={t("masterData.machine")}
        endpoint="/maschinen"
        columnDefs={columnDefs}
        formFields={formFields}
        emptyFormValues={emptyFormValues as Omit<Maschine, "id" | "created_at" | "updated_at">}
        formMaxWidthClassName="max-w-xl"
        formBanner={
          selectedWerk ? (
            <p>{t("masterData.plantParamsBanner", { code: selectedWerk.code })}</p>
          ) : (
            <p>{t("masterData.selectPlantFirst")}</p>
          )
        }
        onSelectedIdChange={setSelectedId}
        onFormValuesChange={(values) => {
          const raw = values.werk_id;
          setFormWerkId(raw === "" || raw == null ? null : Number(raw));
        }}
        transformLoadValues={(values) => loadMaschineFormValues(values)}
        transformSubmitValues={(values) => submitMaschineFormValues(values)}
        toolbarExtra={
          canWrite ? (
            <div className="mb-3">
              <button
                type="button"
                disabled={!selectedId || busy}
                onClick={() => void recalculate()}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
              >
                {busy ? t("masterData.calculating") : t("masterData.recalculateHourlyRate")}
              </button>
              {!selectedId && (
                <span className="ml-2 text-xs text-gray-500">
                  {t("masterData.selectMachineInTable")}
                </span>
              )}
            </div>
          ) : null
        }
      />
    </div>
  );
}
