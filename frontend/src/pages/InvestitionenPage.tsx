import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ICellRendererParams, RowDoubleClickedEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import {
  archiveInvestition,
  createInvestition,
  getBusinessCase,
  listInvestitionen,
  updateInvestition,
} from "../api/investitionen";
import { listBaugruppen } from "../api/baugruppen";
import { listKalkulationen } from "../api/spritzguss";
import { useAuth } from "../context/AuthContext";
import type { BaugruppeListItem } from "../types/baugruppe";
import type { SpritzgussListItem } from "../types/spritzguss";
import {
  emptyInvestitionForm,
  EINMALZAHLUNG_HINWEIS,
  INVESTMENT_TYPES,
  PAYMENT_TYPES,
  type BusinessCaseFilters,
  type BusinessCaseSummary,
  type Investition,
  type InvestitionPayload,
  type ZuordnungFilter,
} from "../types/investition";

type FormMode = "create" | "edit";
type ZuordnungForm = "projekt" | "einzelteil" | "baugruppe";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function int(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE");
}

function validateForm(form: InvestitionPayload, zuordnung: ZuordnungForm): string | null {
  if (!form.name.trim()) return "Bezeichnung ist erforderlich.";
  if (!form.project.trim()) return "Projekt ist erforderlich.";
  if (!form.payment_type) return "Zahlungsart ist erforderlich.";
  if (form.amount < 0) return "Investitionsbetrag darf nicht negativ sein.";
  if (form.payment_type === "Amortisation") {
    const vol = form.amortization_volume;
    if (vol == null || !Number.isInteger(vol) || vol < 1) {
      return "Amortisationsvolumen muss eine positive ganze Zahl sein.";
    }
  }
  if (zuordnung === "einzelteil" && !form.calculation_id) {
    return "Bitte ein Einzelteil auswählen oder Zuordnung auf Gesamtprojekt setzen.";
  }
  if (zuordnung === "baugruppe" && !form.baugruppe_id) {
    return "Bitte eine Baugruppe auswählen oder Zuordnung auf Gesamtprojekt setzen.";
  }
  return null;
}

export function InvestitionenPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Investition[]>([]);
  const [businessCase, setBusinessCase] = useState<BusinessCaseSummary | null>(null);
  const [kalkulationen, setKalkulationen] = useState<SpritzgussListItem[]>([]);
  const [baugruppen, setBaugruppen] = useState<BaugruppeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<InvestitionPayload>(emptyInvestitionForm());
  const [zuordnungForm, setZuordnungForm] = useState<ZuordnungForm>("projekt");

  const [projectFilter, setProjectFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [zuordnungFilter, setZuordnungFilter] = useState<ZuordnungFilter>("");
  const [positionFilter, setPositionFilter] = useState("");

  const appliedFilters = useMemo((): BusinessCaseFilters => {
    const filters: BusinessCaseFilters = {};
    if (projectFilter) filters.project = projectFilter;
    if (customerFilter) filters.customer = customerFilter;
    if (zuordnungFilter === "einzelteil" && positionFilter) {
      filters.calculation_id = Number(positionFilter);
    } else if (zuordnungFilter === "baugruppe" && positionFilter) {
      filters.baugruppe_id = Number(positionFilter);
    } else if (zuordnungFilter === "projekt") {
      filters.scope = "gesamtprojekt";
    } else if (zuordnungFilter === "einzelteil") {
      filters.scope = "einzelteil";
    } else if (zuordnungFilter === "baugruppe") {
      filters.scope = "baugruppe";
    }
    return filters;
  }, [projectFilter, customerFilter, zuordnungFilter, positionFilter]);

  const projectOptions = useMemo(() => {
    const values = new Set<string>();
    kalkulationen.forEach((k) => k.projekt && values.add(k.projekt));
    baugruppen.forEach((b) => b.projekt && values.add(b.projekt));
    rows.forEach((r) => r.project && values.add(r.project));
    return Array.from(values).sort();
  }, [kalkulationen, baugruppen, rows]);

  const customerOptions = useMemo(() => {
    const values = new Set<string>();
    const sourceK = projectFilter
      ? kalkulationen.filter((k) => k.projekt === projectFilter)
      : kalkulationen;
    const sourceB = projectFilter
      ? baugruppen.filter((b) => b.projekt === projectFilter)
      : baugruppen;
    sourceK.forEach((k) => k.kunde && values.add(k.kunde));
    sourceB.forEach((b) => b.kunde && values.add(b.kunde));
    rows.forEach((r) => r.customer && values.add(r.customer));
    return Array.from(values).sort();
  }, [kalkulationen, baugruppen, rows, projectFilter]);

  const filteredKalkulationen = useMemo(
    () =>
      kalkulationen.filter((k) => {
        if (projectFilter && k.projekt !== projectFilter) return false;
        if (customerFilter && k.kunde !== customerFilter) return false;
        return true;
      }),
    [kalkulationen, projectFilter, customerFilter],
  );

  const filteredBaugruppen = useMemo(
    () =>
      baugruppen.filter((b) => {
        if (projectFilter && b.projekt !== projectFilter) return false;
        if (customerFilter && b.kunde !== customerFilter) return false;
        return true;
      }),
    [baugruppen, projectFilter, customerFilter],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, bc] = await Promise.all([
        listInvestitionen(appliedFilters),
        getBusinessCase(appliedFilters),
      ]);
      setRows(items);
      setBusinessCase(bc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    loadData().catch(() => undefined);
  }, [loadData]);

  useEffect(() => {
    listKalkulationen().then(setKalkulationen).catch(() => undefined);
    listBaugruppen().then(setBaugruppen).catch(() => undefined);
  }, []);

  const resetFilters = () => {
    setProjectFilter("");
    setCustomerFilter("");
    setZuordnungFilter("");
    setPositionFilter("");
  };

  const openCreate = () => {
    setFormMode("create");
    setEditingId(null);
    const initial = emptyInvestitionForm();
    if (projectFilter) initial.project = projectFilter;
    if (customerFilter) initial.customer = customerFilter;
    if (zuordnungFilter === "einzelteil" && positionFilter) {
      initial.calculation_id = Number(positionFilter);
      setZuordnungForm("einzelteil");
    } else if (zuordnungFilter === "baugruppe" && positionFilter) {
      initial.baugruppe_id = Number(positionFilter);
      setZuordnungForm("baugruppe");
    } else {
      setZuordnungForm("projekt");
    }
    setForm(initial);
    setShowForm(true);
    setError(null);
    setSuccess(null);
  };

  const openEdit = (item: Investition) => {
    setFormMode("edit");
    setEditingId(item.id);
    if (item.calculation_id) setZuordnungForm("einzelteil");
    else if (item.baugruppe_id) setZuordnungForm("baugruppe");
    else setZuordnungForm("projekt");
    setForm({
      name: item.name,
      investment_type: item.investment_type,
      payment_type: item.payment_type,
      amount: item.amount,
      amortization_volume: item.amortization_volume,
      project: item.project,
      customer: item.customer,
      calculation_id: item.calculation_id,
      baugruppe_id: item.baugruppe_id,
      description: item.description,
    });
    setShowForm(true);
    setError(null);
    setSuccess(null);
  };

  const handleSave = async () => {
    const validationError = validateForm(form, zuordnungForm);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: InvestitionPayload = {
        ...form,
        calculation_id: zuordnungForm === "einzelteil" ? form.calculation_id : null,
        baugruppe_id: zuordnungForm === "baugruppe" ? form.baugruppe_id : null,
        amortization_volume:
          form.payment_type === "Amortisation" ? form.amortization_volume : null,
      };
      if (formMode === "create") {
        await createInvestition(payload);
        setSuccess("Investitionsposition angelegt.");
      } else if (editingId != null) {
        await updateInvestition(editingId, payload);
        setSuccess("Investitionsposition gespeichert.");
      }
      setShowForm(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async (id: number) => {
    if (!window.confirm("Investitionsposition archivieren?")) return;
    setBusy(true);
    try {
      await archiveInvestition(id);
      setSuccess("Investitionsposition archiviert.");
      if (editingId === id) setShowForm(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archivieren fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const setField = <K extends keyof InvestitionPayload>(key: K, value: InvestitionPayload[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "payment_type" && value === "Einmalzahlung") {
        next.amortization_volume = null;
      }
      if (key === "calculation_id" && value) {
        const calc = kalkulationen.find((k) => k.id === value);
        if (calc) {
          next.project = calc.projekt || next.project;
          next.customer = calc.kunde || next.customer;
        }
      }
      if (key === "baugruppe_id" && value) {
        const bg = baugruppen.find((b) => b.id === value);
        if (bg) {
          next.project = bg.projekt || next.project;
          next.customer = bg.kunde || next.customer;
        }
      }
      return next;
    });
  };

  const columnDefs = useMemo<ColDef<Investition>[]>(
    () => [
      { field: "name", headerName: "Bezeichnung", flex: 1, minWidth: 160 },
      { field: "investment_type", headerName: "Art", width: 120 },
      { field: "payment_type", headerName: "Zahlungsart", width: 130 },
      {
        field: "amount",
        headerName: "Betrag",
        width: 120,
        valueFormatter: (p) => euro(p.value as number),
      },
      {
        field: "amortization_volume",
        headerName: "Amort.-Vol.",
        width: 110,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" && p.value != null ? String(p.value) : "–",
      },
      {
        field: "cost_per_piece",
        headerName: "Kosten/Stück",
        width: 120,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" ? euro(p.value as number | null) : "–",
      },
      { field: "project", headerName: "Projekt", width: 130 },
      { field: "zuordnung", headerName: "Zuordnung", flex: 1, minWidth: 180 },
      {
        headerName: "Hinweis",
        width: 240,
        cellRenderer: (p: ICellRendererParams<Investition>) =>
          p.data?.payment_type === "Einmalzahlung" ? (
            <span className="font-medium text-amber-800">{EINMALZAHLUNG_HINWEIS}</span>
          ) : (
            ""
          ),
      },
    ],
    [],
  );

  const kpiItems = businessCase
    ? [
        { label: "Teilepreis je Stück", value: euro(businessCase.teilepreis_je_stueck) },
        {
          label: "Baugruppenpreis je Stück",
          value: euro(businessCase.baugruppenpreis_je_stueck),
        },
        { label: "Jahresstückzahl", value: int(businessCase.jahresstueckzahl) },
        { label: "Jahresumsatz / Umsatzpotenzial", value: euro(businessCase.jahresumsatz) },
        { label: "Investitionen gesamt", value: euro(businessCase.investitionen_gesamt) },
        {
          label: "Amortisationsinvestitionen",
          value: euro(businessCase.amortisationsinvestitionen_gesamt),
        },
        {
          label: "Einmalinvestitionen",
          value: euro(businessCase.einmalinvestitionen_gesamt),
          highlight: true,
        },
        {
          label: "Amortisationsanteil je Stück",
          value: euro(businessCase.amortisationsanteil_je_stueck),
        },
        {
          label: "Preis inkl. Amortisation je Stück",
          value: euro(businessCase.preis_inkl_amortisation_je_stueck),
          bold: true,
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Business Case / Investitionen</h2>
          <p className="mt-1 text-sm text-gray-600">
            Projektbezogene Investitionsplanung für den Business Case – Preise aus gespeicherten
            Kalkulationen, Einmalzahlungen separat ausgewiesen.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={() => loadData()}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Aktualisieren
          </button>
          {canWrite && (
            <button
              type="button"
              onClick={openCreate}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600"
            >
              Neu
            </button>
          )}
        </div>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Projektfilter</h3>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <label className="block text-sm">
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={projectFilter}
              onChange={(e) => {
                setProjectFilter(e.target.value);
                setPositionFilter("");
              }}
            >
              <option value="">Alle</option>
              {projectOptions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Kunde</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
            >
              <option value="">Alle</option>
              {customerOptions.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Zuordnung</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={zuordnungFilter}
              onChange={(e) => {
                setZuordnungFilter(e.target.value as ZuordnungFilter);
                setPositionFilter("");
              }}
            >
              <option value="">Alle</option>
              <option value="einzelteil">Einzelteil</option>
              <option value="baugruppe">Baugruppe</option>
              <option value="projekt">Gesamtprojekt</option>
            </select>
          </label>
          {zuordnungFilter === "einzelteil" && (
            <label className="block text-sm">
              <span className="text-gray-600">Einzelteil</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={positionFilter}
                onChange={(e) => setPositionFilter(e.target.value)}
              >
                <option value="">Alle Einzelteile</option>
                {filteredKalkulationen.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.teilenummer} – {k.teilebezeichnung}
                  </option>
                ))}
              </select>
            </label>
          )}
          {zuordnungFilter === "baugruppe" && (
            <label className="block text-sm">
              <span className="text-gray-600">Baugruppe</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={positionFilter}
                onChange={(e) => setPositionFilter(e.target.value)}
              >
                <option value="">Alle Baugruppen</option>
                {filteredBaugruppen.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.teilenummer} – {b.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <div className="mt-3">
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            Filter zurücksetzen
          </button>
        </div>
      </section>

      {businessCase && (
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">Business-Case-Zusammenfassung</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {kpiItems.map((kpi) => (
              <div
                key={kpi.label}
                className={`rounded-lg border bg-white p-3 ${
                  kpi.highlight ? "border-amber-300 bg-amber-50" : "border-gray-200"
                }`}
              >
                <div className="text-xs text-gray-500">{kpi.label}</div>
                <div
                  className={`mt-1 text-lg ${kpi.bold ? "font-bold text-emerald-800" : "font-semibold text-gray-900"}`}
                >
                  {kpi.value}
                </div>
              </div>
            ))}
          </div>
          {businessCase.einmalinvestitionen.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <h4 className="text-sm font-semibold text-amber-900">Einmalinvestitionen (separat)</h4>
              <ul className="mt-2 space-y-1 text-sm text-amber-900">
                {businessCase.einmalinvestitionen.map((inv) => (
                  <li key={inv.id}>
                    {inv.name}: {euro(inv.amount)} – {inv.hinweis}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {success}
        </div>
      )}

      <section className="ag-theme-quartz rounded-lg border border-gray-200 bg-white p-2">
        {!loading && rows.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-gray-600">
            Keine Investitionspositionen für die aktuelle Auswahl vorhanden. Legen Sie eine neue
            Position an oder passen Sie die Filter an.
          </div>
        )}
        <div style={{ height: rows.length > 0 ? 380 : 0, width: "100%" }}>
          <AgGridReact<Investition>
            rowData={rows}
            columnDefs={columnDefs}
            loading={loading}
            onRowDoubleClicked={(e: RowDoubleClickedEvent<Investition>) => {
              if (e.data) openEdit(e.data);
            }}
            getRowId={(p) => String(p.data.id)}
            defaultColDef={{ sortable: false, filter: false, resizable: true }}
          />
        </div>
      </section>

      {showForm && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-lg font-semibold text-gray-900">
            {formMode === "create" ? "Neue Investitionsposition" : "Investitionsposition bearbeiten"}
          </h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="block text-sm md:col-span-2">
              <span className="text-gray-600">Bezeichnung *</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Investitionsart</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.investment_type}
                onChange={(e) => setField("investment_type", e.target.value)}
              >
                {INVESTMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="md:col-span-3 rounded border border-gray-200 p-3">
              <legend className="px-1 text-sm font-medium text-gray-700">Zahlungsart *</legend>
              <div className="flex flex-wrap gap-4">
                {PAYMENT_TYPES.map((pt) => (
                  <label key={pt} className="inline-flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="payment_type"
                      checked={form.payment_type === pt}
                      onChange={() => setField("payment_type", pt)}
                    />
                    {pt}
                  </label>
                ))}
              </div>
              {form.payment_type === "Einmalzahlung" && (
                <p className="mt-2 text-xs text-amber-800">{EINMALZAHLUNG_HINWEIS}</p>
              )}
            </fieldset>

            <label className="block text-sm">
              <span className="text-gray-600">Investitionsbetrag (€) *</span>
              <input
                type="number"
                min={0}
                step="0.01"
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.amount}
                onChange={(e) => setField("amount", Number(e.target.value))}
              />
            </label>
            {form.payment_type === "Amortisation" && (
              <label className="block text-sm">
                <span className="text-gray-600">Amortisationsvolumen (Stück) *</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                  value={form.amortization_volume ?? ""}
                  onChange={(e) =>
                    setField(
                      "amortization_volume",
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                />
              </label>
            )}

            <label className="block text-sm">
              <span className="text-gray-600">Projekt *</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.project}
                onChange={(e) => setField("project", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Kunde</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.customer}
                onChange={(e) => setField("customer", e.target.value)}
              />
            </label>

            <fieldset className="md:col-span-3 rounded border border-gray-200 p-3">
              <legend className="px-1 text-sm font-medium text-gray-700">Zuordnung im Business Case</legend>
              <div className="flex flex-wrap gap-4">
                {(
                  [
                    ["projekt", "Gesamtprojekt"],
                    ["einzelteil", "Einzelteil"],
                    ["baugruppe", "Baugruppe"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="inline-flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="zuordnung"
                      checked={zuordnungForm === key}
                      onChange={() => {
                        setZuordnungForm(key);
                        if (key === "projekt") {
                          setField("calculation_id", null);
                          setField("baugruppe_id", null);
                        }
                        if (key === "einzelteil") setField("baugruppe_id", null);
                        if (key === "baugruppe") setField("calculation_id", null);
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>

            {zuordnungForm === "einzelteil" && (
              <label className="block text-sm md:col-span-2">
                <span className="text-gray-600">Einzelteil-Kalkulation</span>
                <select
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                  value={form.calculation_id ?? ""}
                  onChange={(e) =>
                    setField("calculation_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">Bitte wählen …</option>
                  {filteredKalkulationen.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.teilenummer} – {k.teilebezeichnung}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {zuordnungForm === "baugruppe" && (
              <label className="block text-sm md:col-span-2">
                <span className="text-gray-600">Baugruppe</span>
                <select
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                  value={form.baugruppe_id ?? ""}
                  onChange={(e) =>
                    setField("baugruppe_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">Bitte wählen …</option>
                  {filteredBaugruppen.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.teilenummer} – {b.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="block text-sm md:col-span-3">
              <span className="text-gray-600">Bemerkung</span>
              <textarea
                rows={2}
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.description}
                onChange={(e) => setField("description", e.target.value)}
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={handleSave}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              Speichern
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setShowForm(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
            >
              Abbrechen
            </button>
            {formMode === "edit" && editingId != null && canWrite && (
              <button
                type="button"
                disabled={busy}
                onClick={() => handleArchive(editingId)}
                className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                Archivieren
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
