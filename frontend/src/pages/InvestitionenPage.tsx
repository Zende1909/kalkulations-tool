import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ICellRendererParams, RowDoubleClickedEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import {
  archiveInvestition,
  createInvestition,
  getInvestitionSummary,
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
  INVESTITION_STATUS,
  INVESTMENT_TYPES,
  PAYMENT_TYPES,
  type Investition,
  type InvestitionFilters,
  type InvestitionPayload,
  type InvestitionSummary,
} from "../types/investition";

type FormMode = "create" | "edit";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function dateDe(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("de-DE");
}

function validateForm(form: InvestitionPayload): string | null {
  if (!form.name.trim()) return "Investitionsbezeichnung ist erforderlich.";
  if (form.amount < 0) return "Investitionsbetrag darf nicht negativ sein.";
  if (form.payment_type === "Amortisation") {
    const vol = form.amortization_volume;
    if (vol == null || !Number.isInteger(vol) || vol < 1) {
      return "Amortisationsvolumen muss eine positive ganze Zahl sein.";
    }
  }
  return null;
}

export function InvestitionenPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Investition[]>([]);
  const [summary, setSummary] = useState<InvestitionSummary | null>(null);
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

  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [paymentFilter, setPaymentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const appliedFilters = useMemo<InvestitionFilters>(
    () => ({
      search: search.trim() || undefined,
      project: projectFilter || undefined,
      customer: customerFilter || undefined,
      investment_type: typeFilter || undefined,
      payment_type: paymentFilter || undefined,
      status: statusFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [search, projectFilter, customerFilter, typeFilter, paymentFilter, statusFilter, sortBy, sortDir],
  );

  const projectOptions = useMemo(() => {
    const values = new Set<string>();
    rows.forEach((r) => {
      if (r.project) values.add(r.project);
    });
    kalkulationen.forEach((k) => {
      if (k.projekt) values.add(k.projekt);
    });
    baugruppen.forEach((b) => {
      if (b.projekt) values.add(b.projekt);
    });
    return Array.from(values).sort();
  }, [rows, kalkulationen, baugruppen]);

  const customerOptions = useMemo(() => {
    const values = new Set<string>();
    rows.forEach((r) => {
      if (r.customer) values.add(r.customer);
    });
    kalkulationen.forEach((k) => {
      if (k.kunde) values.add(k.kunde);
    });
    baugruppen.forEach((b) => {
      if (b.kunde) values.add(b.kunde);
    });
    return Array.from(values).sort();
  }, [rows, kalkulationen, baugruppen]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, stats] = await Promise.all([
        listInvestitionen(appliedFilters),
        getInvestitionSummary(appliedFilters),
      ]);
      setRows(items);
      setSummary(stats);
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
    listKalkulationen()
      .then(setKalkulationen)
      .catch(() => undefined);
    listBaugruppen()
      .then(setBaugruppen)
      .catch(() => undefined);
  }, []);

  const openCreate = () => {
    setFormMode("create");
    setEditingId(null);
    setForm(emptyInvestitionForm());
    setShowForm(true);
    setError(null);
    setSuccess(null);
  };

  const openEdit = (item: Investition) => {
    setFormMode("edit");
    setEditingId(item.id);
    setForm({
      name: item.name,
      investment_type: item.investment_type,
      payment_type: item.payment_type as InvestitionPayload["payment_type"],
      amount: item.amount,
      amortization_volume: item.amortization_volume,
      project: item.project,
      customer: item.customer,
      part_name: item.part_name,
      part_number: item.part_number,
      calculation_id: item.calculation_id,
      baugruppe_id: item.baugruppe_id,
      supplier: item.supplier,
      order_date: item.order_date,
      delivery_date: item.delivery_date,
      status: item.status,
      description: item.description,
    });
    setShowForm(true);
    setError(null);
    setSuccess(null);
  };

  const handleSave = async () => {
    const validationError = validateForm(form);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: InvestitionPayload = {
        ...form,
        amortization_volume:
          form.payment_type === "Amortisation" ? form.amortization_volume : null,
      };
      if (formMode === "create") {
        await createInvestition(payload);
        setSuccess("Investition angelegt.");
      } else if (editingId != null) {
        await updateInvestition(editingId, payload);
        setSuccess("Investition gespeichert.");
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
    if (!window.confirm("Investition archivieren?")) return;
    setBusy(true);
    setError(null);
    try {
      await archiveInvestition(id);
      setSuccess("Investition archiviert.");
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
          next.part_name = calc.teilebezeichnung || next.part_name;
          next.part_number = calc.teilenummer || next.part_number;
        }
      }
      if (key === "baugruppe_id" && value) {
        const bg = baugruppen.find((b) => b.id === value);
        if (bg) {
          next.project = bg.projekt || next.project;
          next.customer = bg.kunde || next.customer;
          next.part_name = bg.name || next.part_name;
          next.part_number = bg.teilenummer || next.part_number;
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
        valueFormatter: (p) => (p.value == null ? "–" : String(p.value)),
      },
      {
        field: "cost_per_piece",
        headerName: "Kosten/Stück",
        width: 120,
        valueFormatter: (p) => euro(p.value as number | null),
      },
      { field: "project", headerName: "Projekt", width: 130 },
      { field: "zuordnung", headerName: "Zuordnung", flex: 1, minWidth: 180 },
      { field: "status", headerName: "Status", width: 130 },
      { field: "supplier", headerName: "Lieferant", width: 130 },
      {
        field: "delivery_date",
        headerName: "Liefertermin",
        width: 120,
        valueFormatter: (p) => dateDe(p.value as string | null),
      },
      {
        headerName: "Hinweis",
        width: 220,
        cellRenderer: (p: ICellRendererParams<Investition>) =>
          p.data?.payment_type === "Einmalzahlung" ? (
            <span className="text-amber-800">{EINMALZAHLUNG_HINWEIS}</span>
          ) : (
            ""
          ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Investitionen</h2>
          <p className="mt-1 text-sm text-gray-600">
            Zentrale Erfassung von Werkzeugen, Anlagen und Einmalzahlungen. Einmalzahlungen werden
            separat ausgewiesen und nicht automatisch in den Stückpreis eingerechnet.
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

      {summary && (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {[
            { label: "Gesamtinvestitionen", value: euro(summary.gesamtinvestitionen) },
            { label: "Anzahl", value: String(summary.anzahl_investitionen) },
            { label: "Einmalzahlungen", value: euro(summary.summe_einmalzahlungen) },
            { label: "Amortisiert", value: euro(summary.summe_amortisiert) },
            { label: "In Planung", value: String(summary.in_planung) },
            { label: "Bestellt", value: String(summary.bestellt) },
            { label: "Abgeschlossen", value: String(summary.abgeschlossen) },
          ].map((kpi) => (
            <div key={kpi.label} className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="text-xs text-gray-500">{kpi.label}</div>
              <div className="mt-1 text-lg font-semibold text-gray-900">{kpi.value}</div>
            </div>
          ))}
        </section>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Filter & Suche</h3>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          <label className="block text-sm">
            <span className="text-gray-600">Suche</span>
            <input
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Bezeichnung, Lieferant …"
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={projectFilter}
              onChange={(e) => setProjectFilter(e.target.value)}
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
            <span className="text-gray-600">Art</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="">Alle</option>
              {INVESTMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Zahlungsart</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={paymentFilter}
              onChange={(e) => setPaymentFilter(e.target.value)}
            >
              <option value="">Alle</option>
              {PAYMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Status</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">Alle</option>
              {INVESTITION_STATUS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Sortierung</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="updated_at">Geändert</option>
              <option value="amount">Betrag</option>
              <option value="delivery_date">Liefertermin</option>
              <option value="order_date">Bestelldatum</option>
              <option value="status">Status</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Richtung</span>
            <select
              className="mt-1 block w-full rounded border px-2 py-1.5"
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value as "asc" | "desc")}
            >
              <option value="desc">Absteigend</option>
              <option value="asc">Aufsteigend</option>
            </select>
          </label>
        </div>
      </section>

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
        <div style={{ height: 420, width: "100%" }}>
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
            {formMode === "create" ? "Neue Investition" : "Investition bearbeiten"}
          </h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="block text-sm md:col-span-2">
              <span className="text-gray-600">Investitionsbezeichnung *</span>
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
              <legend className="px-1 text-sm font-medium text-gray-700">Zahlungsart</legend>
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
              <span className="text-gray-600">Projekt</span>
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
            <label className="block text-sm">
              <span className="text-gray-600">Status</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.status}
                onChange={(e) => setField("status", e.target.value)}
              >
                {INVESTITION_STATUS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm">
              <span className="text-gray-600">Einzelteil-Kalkulation (optional)</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.calculation_id ?? ""}
                onChange={(e) =>
                  setField("calculation_id", e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">– keine –</option>
                {kalkulationen.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.teilenummer} – {k.teilebezeichnung}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Baugruppe (optional)</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.baugruppe_id ?? ""}
                onChange={(e) =>
                  setField("baugruppe_id", e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">– keine –</option>
                {baugruppen.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.teilenummer} – {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Teilenummer (optional)</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.part_number}
                onChange={(e) => setField("part_number", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Teilebezeichnung (optional)</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.part_name}
                onChange={(e) => setField("part_name", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Lieferant</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.supplier}
                onChange={(e) => setField("supplier", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Bestelldatum</span>
              <input
                type="date"
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.order_date ?? ""}
                onChange={(e) => setField("order_date", e.target.value || null)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Liefertermin</span>
              <input
                type="date"
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.delivery_date ?? ""}
                onChange={(e) => setField("delivery_date", e.target.value || null)}
              />
            </label>
            <label className="block text-sm md:col-span-3">
              <span className="text-gray-600">Beschreibung / Bemerkung</span>
              <textarea
                rows={3}
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
