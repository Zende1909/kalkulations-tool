import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  ColDef,
  GetRowIdParams,
  ICellRendererParams,
  RowDoubleClickedEvent,
  RowSelectedEvent,
} from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import { api, getApiBaseUrl, NetworkError } from "../api/client";
import {
  createVeredelungsschritt,
  deleteVeredelungsschritt,
  listVeredelungsschritte,
  updateVeredelungsschritt,
} from "../api/veredelung";
import { useAuth } from "../context/AuthContext";
import type { Lohnkosten } from "../types/stammdaten";
import {
  emptyVeredelungForm,
  VEREDELUNGSARTEN,
  type Veredelungsart,
  type Veredelungsschritt,
  type VeredelungsschrittPayload,
} from "../types/veredelung";
import { FormDecimalInput } from "../components/FormDecimalInput";
import { formatDecimalForInputDe, PercentPointsParseError } from "../utils/decimalInput";
import {
  loadVeredelungDecimalRaw,
  parseVeredelungDecimalFields,
} from "../utils/veredelungFormDecimals";
import { useT } from "../i18n";

type FormMode = "create" | "edit";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

type TFn = (key: string, params?: Record<string, string | number | null | undefined>) => string;

function formatFetchError(err: unknown, method: string, url: string, t: TFn): string {
  if (err instanceof NetworkError) return err.message;
  if (err instanceof Error) return err.message;
  return t("finishing.unknownError", { method, url });
}

const FINISHING_ART_KEYS: Record<string, string> = {
  Montage: "finishing.artMontage",
  Ultraschallschweißen: "finishing.artUltraschallschweissen",
  Vibrationsschweißen: "finishing.artVibrationsschweissen",
  Lackieren: "finishing.artLackieren",
  Bedrucken: "finishing.artBedrucken",
  Kaschieren: "finishing.artKaschieren",
  Clipsen: "finishing.artClipsen",
  Schrauben: "finishing.artSchrauben",
  Sonstige: "finishing.artSonstige",
};

function validateForm(form: VeredelungsschrittPayload, t: TFn): string | null {
  if (!form.bezeichnung.trim()) return t("finishing.errName");
  if (!Number.isInteger(form.reihenfolge) || form.reihenfolge < 1) {
    return t("finishing.errSequence");
  }
  if (form.taktzeit_s < 0) return t("finishing.errCycleTime");
  if (!Number.isInteger(form.anzahl_mitarbeiter) || form.anzahl_mitarbeiter < 1) {
    return t("finishing.errStaff");
  }
  if (form.lohnstundensatz < 0) return t("finishing.errLaborRate");
  if (form.maschinenstundensatz != null && form.maschinenstundensatz < 0) {
    return t("finishing.errMachineRate");
  }
  if (form.verbrauchskosten_je_stueck < 0) {
    return t("finishing.errConsumables");
  }
  if (form.ausschussquote_pct < 0 || form.ausschussquote_pct >= 100) {
    return t("finishing.errScrap");
  }
  return null;
}

export function VeredelungPage() {
  const t = useT();
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Veredelungsschritt[]>([]);
  const [lohnsaetze, setLohnsaetze] = useState<Lohnkosten[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<VeredelungsschrittPayload>(emptyVeredelungForm());
  const [decimalRaw, setDecimalRaw] = useState<Record<string, string>>(() =>
    loadVeredelungDecimalRaw(emptyVeredelungForm()),
  );

  const handleDecimalChange = (fieldKey: string, raw: string) => {
    setDecimalRaw((current) => ({ ...current, [fieldKey]: raw }));
  };

  const apiUrl = `${getApiBaseUrl()}/veredelung`;

  const loadData = useCallback(async (options?: { initial?: boolean }) => {
    const isInitial = options?.initial === true;
    if (isInitial) setInitialLoading(true);
    else setRefreshing(true);
    try {
      setError(null);
      const data = await listVeredelungsschritte();
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(formatFetchError(err, "GET", apiUrl, t));
      throw err;
    } finally {
      if (isInitial) setInitialLoading(false);
      else setRefreshing(false);
    }
  }, [apiUrl, t]);

  useEffect(() => {
    loadData({ initial: true }).catch(() => undefined);
    api
      .get<Lohnkosten[]>("/lohnkosten")
      .then((items) => setLohnsaetze(items.filter((l) => l.aktiv)))
      .catch(() => undefined);
  }, [loadData]);

  const gesamtkostenAktiv = useMemo(
    () =>
      rows
        .filter((r) => r.aktiv)
        .reduce((sum, r) => sum + (r.kosten_inkl_ausschuss || 0), 0),
    [rows],
  );

  const openCreateForm = () => {
    setFormMode("create");
    setEditingId(null);
    setForm(emptyVeredelungForm());
    setDecimalRaw(loadVeredelungDecimalRaw(emptyVeredelungForm()));
    setFormError(null);
    setSuccess(null);
    setShowForm(true);
  };

  const openEditForm = useCallback(
    (row: Veredelungsschritt) => {
      if (!canWrite) return;
      setFormMode("edit");
      setEditingId(row.id);
      setSelectedId(row.id);
      setForm({
        bezeichnung: row.bezeichnung,
        veredelungsart: row.veredelungsart,
        reihenfolge: row.reihenfolge,
        beschreibung: row.beschreibung,
        taktzeit_s: row.taktzeit_s,
        anzahl_mitarbeiter: row.anzahl_mitarbeiter,
        lohnkosten_id: row.lohnkosten_id,
        lohnstundensatz: row.lohnstundensatz,
        maschinenstundensatz: row.maschinenstundensatz,
        verbrauchskosten_je_stueck: row.verbrauchskosten_je_stueck,
        ausschussquote_pct: row.ausschussquote_pct,
        fgk_pct: row.fgk_pct,
        aktiv: row.aktiv,
      });
      setDecimalRaw(loadVeredelungDecimalRaw(row));
      setFormError(null);
      setSuccess(null);
      setShowForm(true);
    },
    [canWrite],
  );

  const closeForm = () => {
    setShowForm(false);
    setFormError(null);
    setSubmitting(false);
    setEditingId(null);
    setFormMode("create");
  };

  const handleLohnSelect = (id: string) => {
    if (!id) {
      setForm((current) => ({ ...current, lohnkosten_id: null }));
      return;
    }
    const lohn = lohnsaetze.find((l) => l.id === Number(id));
    if (!lohn) return;
    setForm((current) => ({
      ...current,
      lohnkosten_id: lohn.id,
      lohnstundensatz: lohn.kosten_pro_stunde,
    }));
    setDecimalRaw((current) => ({
      ...current,
      lohnstundensatz: formatDecimalForInputDe(lohn.kosten_pro_stunde),
    }));
  };

  const handleSubmit = async () => {
    let formForValidation: VeredelungsschrittPayload;
    try {
      formForValidation = parseVeredelungDecimalFields(decimalRaw, form);
    } catch (err) {
      setFormError(
        err instanceof PercentPointsParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : t("finishing.invalidDecimals"),
      );
      return;
    }
    const clientError = validateForm(formForValidation, t);
    if (clientError) {
      setFormError(clientError);
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setError(null);
    setSuccess(null);
    try {
      const payload: VeredelungsschrittPayload = {
        ...formForValidation,
        bezeichnung: form.bezeichnung.trim(),
      };

      if (formMode === "edit" && editingId != null) {
        await updateVeredelungsschritt(editingId, payload);
        setShowForm(false);
        setEditingId(null);
        setFormMode("create");
        setSuccess(t("finishing.updated"));
      } else {
        await createVeredelungsschritt(payload);
        setShowForm(false);
        setSuccess(t("finishing.created"));
      }

      try {
        await loadData();
      } catch {
        // Erfolg bleibt sichtbar
      }
    } catch (err) {
      const method = formMode === "edit" ? "PUT" : "POST";
      const url =
        formMode === "edit" && editingId != null ? `${apiUrl}/${editingId}` : apiUrl;
      setFormError(formatFetchError(err, method, url, t));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (selectedId === null) {
      setError(t("finishing.selectRow"));
      return;
    }
    setError(null);
    setSuccess(null);
    try {
      await deleteVeredelungsschritt(selectedId);
      setSelectedId(null);
      await loadData();
      setSuccess(t("finishing.deleted"));
    } catch (err) {
      setError(formatFetchError(err, "DELETE", `${apiUrl}/${selectedId}`, t));
    }
  };

  const columnDefs = useMemo<ColDef<Veredelungsschritt>[]>(
    () => [
      { field: "reihenfolge", headerName: t("finishing.colSequence"), width: 110, sort: "asc" },
      { field: "bezeichnung", headerName: t("finishing.colDesignation"), minWidth: 140 },
      {
        field: "veredelungsart",
        headerName: t("finishing.colType"),
        minWidth: 140,
        valueFormatter: (p) =>
          p.value ? t(FINISHING_ART_KEYS[String(p.value)] ?? String(p.value)) : "",
      },
      { field: "taktzeit_s", headerName: t("finishing.colCycleTime"), width: 120 },
      { field: "anzahl_mitarbeiter", headerName: t("finishing.colStaff"), width: 80 },
      {
        field: "lohnkosten_je_stueck",
        headerName: t("finishing.colLaborPc"),
        valueFormatter: (p) => euro(p.value),
      },
      {
        field: "maschinenkosten_je_stueck",
        headerName: t("finishing.colMachinePc"),
        valueFormatter: (p) => euro(p.value),
      },
      {
        field: "kosten_vor_ausschuss",
        headerName: t("finishing.colBeforeScrap"),
        valueFormatter: (p) => euro(p.value),
      },
      {
        field: "kosten_inkl_ausschuss",
        headerName: t("finishing.colInclScrap"),
        valueFormatter: (p) => euro(p.value),
      },
      {
        field: "aktiv",
        headerName: t("finishing.colActive"),
        width: 90,
        valueFormatter: (p) => (p.value ? t("common.yes") : t("common.no")),
      },
    ],
    [t],
  );

  const cols = useMemo(() => {
    const base = [...columnDefs];
    if (canWrite) {
      base.push({
        headerName: "",
        colId: "actions",
        width: 130,
        maxWidth: 140,
        pinned: "right",
        sortable: false,
        filter: false,
        resizable: false,
        cellRenderer: (params: ICellRendererParams<Veredelungsschritt>) => {
          if (!params.data) return null;
          return (
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
              onClick={(event) => {
                event.stopPropagation();
                openEditForm(params.data as Veredelungsschritt);
              }}
            >
              {t("common.edit")}
            </button>
          );
        },
      });
    }
    return base;
  }, [canWrite, columnDefs, openEditForm]);

  const getRowId = useCallback(
    (params: GetRowIdParams<Veredelungsschritt>) => String(params.data?.id ?? ""),
    [],
  );

  const formTitle =
    formMode === "edit" ? t("finishing.editTitle") : t("finishing.createTitle");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t("nav.finishing")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("finishing.intro")}</p>
          <p className="mt-1 text-xs text-gray-500">
            API: {apiUrl}
            {refreshing ? t("finishing.apiRefreshing") : ""}
            {!initialLoading ? t("finishing.apiLoaded", { count: rows.length }) : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              loadData().catch(() => undefined);
            }}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            {t("common.reload")}
          </button>
          {canWrite && (
            <>
              <button
                type="button"
                onClick={openCreateForm}
                className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                {t("finishing.new")}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
              >
                {t("finishing.deleteSelected")}
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
          {success}
        </div>
      )}

      <div className="mb-4 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
        <span className="text-gray-600">{t("finishing.totalActiveCost")} </span>
        <span className="font-semibold tabular-nums text-gray-900">
          {t("finishing.perPiece", { amount: euro(gesamtkostenAktiv) })}
        </span>
      </div>

      {initialLoading ? (
        <p className="text-gray-600">{t("finishing.loading")}</p>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-gray-500">
          {t("finishing.empty")}
        </div>
      ) : (
        <div className="ag-theme-quartz" style={{ height: 500, width: "100%" }}>
          <AgGridReact<Veredelungsschritt>
            rowData={rows}
            columnDefs={cols}
            getRowId={getRowId}
            rowSelection="single"
            onRowSelected={(event: RowSelectedEvent<Veredelungsschritt>) => {
              if (event.node.isSelected()) {
                setSelectedId(event.data?.id ?? null);
              }
            }}
            onRowDoubleClicked={(event: RowDoubleClickedEvent<Veredelungsschritt>) => {
              if (event.data) openEditForm(event.data);
            }}
            defaultColDef={{
              flex: 1,
              minWidth: 100,
              sortable: true,
              filter: true,
              resizable: true,
            }}
            animateRows
          />
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">{formTitle}</h3>
              <button
                type="button"
                onClick={closeForm}
                className="text-gray-400 hover:text-gray-600"
                aria-label={t("common.close")}
              >
                ✕
              </button>
            </div>

            {formError && (
              <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            )}

            <form
              onSubmit={(event) => {
                event.preventDefault();
                handleSubmit().catch(() => undefined);
              }}
              className="grid gap-4 md:grid-cols-2"
            >
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("finishing.designation")}</span>
                <input
                  required
                  value={form.bezeichnung}
                  onChange={(e) =>
                    setForm((c) => ({ ...c, bezeichnung: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </label>

              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("finishing.finishingType")}</span>
                <select
                  required
                  value={form.veredelungsart}
                  onChange={(e) =>
                    setForm((c) => ({
                      ...c,
                      veredelungsart: e.target.value as Veredelungsart,
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  {VEREDELUNGSARTEN.map((art) => (
                    <option key={art} value={art}>
                      {t(FINISHING_ART_KEYS[art] ?? art)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("finishing.sequence")}</span>
                <input
                  type="number"
                  required
                  min={1}
                  step={1}
                  value={form.reihenfolge}
                  onChange={(e) =>
                    setForm((c) => ({
                      ...c,
                      reihenfolge: Number.parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </label>

              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("finishing.description")}</span>
                <textarea
                  value={form.beschreibung}
                  onChange={(e) =>
                    setForm((c) => ({ ...c, beschreibung: e.target.value }))
                  }
                  rows={2}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </label>

              <FormDecimalInput
                fieldKey="taktzeit_s"
                label={t("finishing.cycleTime")}
                value={form.taktzeit_s}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />

              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("finishing.staffCount")}</span>
                <input
                  type="number"
                  required
                  min={1}
                  step={1}
                  value={form.anzahl_mitarbeiter}
                  onChange={(e) =>
                    setForm((c) => ({
                      ...c,
                      anzahl_mitarbeiter: Number.parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </label>

              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("finishing.laborFromMaster")}</span>
                <select
                  value={form.lohnkosten_id ?? ""}
                  onChange={(e) => handleLohnSelect(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">{t("finishing.laborManual")}</option>
                  {lohnsaetze.map((lohn) => (
                    <option key={lohn.id} value={lohn.id}>
                      {lohn.bezeichnung} ({euro(lohn.kosten_pro_stunde)} €/h)
                    </option>
                  ))}
                </select>
              </label>

              <FormDecimalInput
                fieldKey="lohnstundensatz"
                label={t("finishing.laborRate")}
                value={form.lohnstundensatz}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />

              <FormDecimalInput
                fieldKey="maschinenstundensatz"
                label={t("finishing.machineRate")}
                value={form.maschinenstundensatz ?? 0}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />

              <FormDecimalInput
                fieldKey="verbrauchskosten_je_stueck"
                label={t("finishing.consumables")}
                value={form.verbrauchskosten_je_stueck}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />

              <FormDecimalInput
                fieldKey="ausschussquote_pct"
                label={t("finishing.scrapRate")}
                value={form.ausschussquote_pct}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />

              <label className="flex items-center gap-2 text-sm md:col-span-2">
                <input
                  type="checkbox"
                  checked={form.aktiv}
                  onChange={(e) =>
                    setForm((c) => ({ ...c, aktiv: e.target.checked }))
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="font-medium text-gray-700">{t("common.active")}</span>
              </label>

              <p className="text-sm text-gray-600 md:col-span-2">{t("finishing.fgkHint")}</p>

              <div className="flex justify-end gap-2 pt-2 md:col-span-2">
                <button
                  type="button"
                  onClick={closeForm}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                >
                  {submitting ? t("common.saving") : t("common.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
