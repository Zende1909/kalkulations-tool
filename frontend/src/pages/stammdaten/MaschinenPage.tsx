import type { ColDef } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Maschine, Werk } from "../../types/stammdaten";

const columnDefs: ColDef<Maschine>[] = [
  { field: "maschinen_nr", headerName: "Maschinen-Nr." },
  { field: "bezeichnung", headerName: "Bezeichnung" },
  { field: "werk_id", headerName: "Werk-ID" },
  { field: "stundensatz", headerName: "Stundensatz EUR/h" },
  { field: "stundensatz_source", headerName: "Satz Quellwährung" },
  { field: "schliesskraft_t", headerName: "Schließkraft (t)" },
  { field: "jahresstunden", headerName: "Jahresstunden" },
  { field: "setup_zeit_min", headerName: "Setup (min)" },
  { field: "aktiv", headerName: "Aktiv" },
];

/**
 * Maschinenmaske: nur maschinenabhängige Felder.
 * Standortparameter (Tage/Schichten/OEE/Sätze/Energiepreise) werden am Werk gepflegt.
 */
function buildMachineFormFields(werke: Werk[], currentWerkId: number | null): FormField[] {
  const active = werke.filter((w) => w.aktiv);
  const current = currentWerkId != null ? werke.find((w) => w.id === currentWerkId) : null;
  const options = [
    { value: "", label: "– Werk wählen –" },
    ...active.map((w) => ({
      value: String(w.id),
      label: `${w.code} – ${w.name}`,
    })),
  ];
  if (current && !current.aktiv && !options.some((o) => o.value === String(current.id))) {
    options.push({
      value: String(current.id),
      label: `${current.code} – ${current.name} (inaktiv)`,
    });
  }

  return [
    {
      name: "werk_id",
      label: "Werk",
      type: "select",
      required: true,
      options,
    },
    { name: "maschinen_nr", label: "Maschinen-Nr.", type: "text", required: true },
    { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
    { name: "maschinentyp", label: "Maschinentyp", type: "text" },
    { name: "variante", label: "Variante", type: "text" },
    {
      name: "stundensatz",
      label: "Stundensatz (EUR/h)",
      type: "number",
      step: "0.0001",
      readOnly: true,
      hint: "Berechnet aus Maschinen- und Werkparametern – nicht manuell überschreibbar.",
    },
    {
      name: "stundensatz_source",
      label: "Stundensatz (Quellwährung/h)",
      type: "number",
      step: "0.0001",
      readOnly: true,
    },
    { name: "source_currency", label: "Quellwährung", type: "text", readOnly: true },
    {
      name: "schliesskraft_t",
      label: "Schließkraft (t)",
      type: "number",
      required: true,
      step: "0.1",
    },
    { name: "investment", label: "Investment", type: "number", step: "1" },
    { name: "flaeche_sqm", label: "Fläche (m²)", type: "number", step: "0.1" },
    {
      name: "stromverbrauch_kwh_h",
      label: "Stromverbrauch kWh/h",
      type: "number",
      step: "0.1",
    },
    {
      name: "druckluftverbrauch_m3_h",
      label: "Druckluftverbrauch m³/h",
      type: "number",
      step: "0.1",
    },
    {
      name: "kuehlwasserverbrauch_m3_h",
      label: "Kühlwasserverbrauch m³/h",
      type: "number",
      step: "0.1",
    },
    { name: "setup_zeit_min", label: "Setup-Zeit (min)", type: "number", step: "1" },
    {
      name: "setup_mitarbeiter",
      label: "Setup-Mitarbeiteranzahl",
      type: "number",
      step: "1",
    },
    { name: "aktiv", label: "Aktiv", type: "checkbox" },
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

  const formFields = useMemo(
    () => buildMachineFormFields(werke, formWerkId),
    [werke, formWerkId],
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
      setMessage(
        `Stundensatz neu berechnet: ${Number(updated.stundensatz).toFixed(4)} €/h` +
          (updated.stundensatz_source != null
            ? ` (${updated.stundensatz_source} ${updated.source_currency ?? ""}/h, FX ${selectedWerk?.fx_to_eur ?? "–"})`
            : ""),
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Neuberechnung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [selectedId, canWrite, selectedWerk?.fx_to_eur]);

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
        title="Maschinen"
        entityLabel="Maschine"
        endpoint="/maschinen"
        columnDefs={columnDefs}
        formFields={formFields}
        emptyFormValues={emptyFormValues as Omit<Maschine, "id" | "created_at" | "updated_at">}
        formMaxWidthClassName="max-w-xl"
        formBanner={
          selectedWerk ? (
            <p>
              Kostenparameter werden aus Werk: <strong>{selectedWerk.code}</strong>{" "}
              übernommen. Kapazität, Space-Satz, Abschreibung, Zinsen, Versicherung,
              Instandhaltung und Energiepreise bitte unter Stammdaten → Werke pflegen.
            </p>
          ) : (
            <p>Bitte zuerst ein Werk wählen. Standortparameter werden am Werk gepflegt.</p>
          )
        }
        onSelectedIdChange={setSelectedId}
        onFormValuesChange={(values) => {
          const raw = values.werk_id;
          setFormWerkId(raw === "" || raw == null ? null : Number(raw));
        }}
        transformSubmitValues={(values) => {
          const werkRaw = values.werk_id;
          const werk_id = werkRaw === "" || werkRaw == null ? null : Number(werkRaw);
          const {
            stundensatz: _s,
            stundensatz_source: _ss,
            source_currency: _sc,
            ...rest
          } = values;
          return { ...rest, werk_id };
        }}
        toolbarExtra={
          canWrite ? (
            <div className="mb-3">
              <button
                type="button"
                disabled={!selectedId || busy}
                onClick={() => void recalculate()}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
              >
                {busy ? "Berechne…" : "Stundensatz neu berechnen"}
              </button>
              {!selectedId && (
                <span className="ml-2 text-xs text-gray-500">
                  Maschine in der Tabelle auswählen
                </span>
              )}
            </div>
          ) : null
        }
      />
    </div>
  );
}
