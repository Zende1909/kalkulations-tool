import type { ColDef } from "ag-grid-community";
import { useCallback, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Maschine } from "../../types/stammdaten";

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

const formFields: FormField[] = [
  { name: "maschinen_nr", label: "Maschinen-Nr.", type: "text", required: true },
  { name: "bezeichnung", label: "Bezeichnung", type: "text", required: true },
  { name: "werk_id", label: "Werk-ID", type: "number", step: "1" },
  { name: "maschinentyp", label: "Maschinentyp", type: "text" },
  { name: "variante", label: "Variante", type: "text" },
  { name: "stundensatz", label: "Stundensatz (EUR/h)", type: "number", required: true, step: "0.01" },
  { name: "schliesskraft_t", label: "Schließkraft (t)", type: "number", required: true, step: "0.1" },
  { name: "source_currency", label: "Quellwährung", type: "text" },
  { name: "arbeitstage_pro_jahr", label: "Arbeitstage/Jahr", type: "number", step: "1" },
  { name: "schichten_pro_tag", label: "Schichten/Tag", type: "number", step: "1" },
  { name: "stunden_pro_schicht", label: "Stunden/Schicht", type: "number", step: "0.1" },
  { name: "oee", label: "OEE (0–1)", type: "number", step: "0.01" },
  { name: "investment", label: "Investment", type: "number", step: "1" },
  { name: "flaeche_sqm", label: "Fläche (m²)", type: "number", step: "0.1" },
  { name: "space_cost_satz_pro_sqm_jahr", label: "Space-Satz /m²/a", type: "number", step: "0.01" },
  { name: "abschreibungsdauer_jahre", label: "Abschreibungsdauer (Jahre)", type: "number", step: "1" },
  { name: "zinssatz", label: "Zinssatz", type: "number", step: "0.0001" },
  { name: "versicherungssatz", label: "Versicherungssatz", type: "number", step: "0.0001" },
  { name: "instandhaltungssatz", label: "Instandhaltungssatz", type: "number", step: "0.0001" },
  { name: "stromverbrauch_kwh_h", label: "Stromverbrauch kWh/h", type: "number", step: "0.1" },
  { name: "strompreis", label: "Strompreis", type: "number", step: "0.01" },
  { name: "druckluftverbrauch_m3_h", label: "Druckluft m³/h", type: "number", step: "0.1" },
  { name: "druckluftpreis", label: "Druckluftpreis", type: "number", step: "0.01" },
  { name: "kuehlwasserverbrauch_m3_h", label: "Kühlwasser m³/h", type: "number", step: "0.1" },
  { name: "kuehlwasserpreis", label: "Kühlwasserpreis", type: "number", step: "0.01" },
  { name: "setup_zeit_min", label: "Setup-Zeit (min)", type: "number", step: "1" },
  { name: "setup_mitarbeiter", label: "Setup-Mitarbeiter", type: "number", step: "1" },
  { name: "aktiv", label: "Aktiv", type: "checkbox" },
];

const emptyFormValues = {
  bezeichnung: "",
  maschinen_nr: "",
  stundensatz: 0,
  schliesskraft_t: 0,
  aktiv: true,
  werk_id: null,
  source_currency: "USD",
};

export function MaschinenPage() {
  const { canWrite } = useAuth();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

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
        `Stundensatz neu berechnet: ${updated.stundensatz?.toFixed?.(4) ?? updated.stundensatz} €/h` +
          (updated.stundensatz_source != null
            ? ` (${updated.stundensatz_source} ${updated.source_currency ?? ""}/h)`
            : ""),
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Neuberechnung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [selectedId, canWrite]);

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
        emptyFormValues={emptyFormValues}
        onSelectedIdChange={setSelectedId}
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
