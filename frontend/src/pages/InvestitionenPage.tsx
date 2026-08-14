import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ICellRendererParams, RowDoubleClickedEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import { listProjectOptions } from "../api/businessCase";
import {
  archiveInvestition,
  createInvestition,
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
  type Investition,
  type InvestitionPayload,
} from "../types/investition";

type FormMode = "create" | "edit";
type ZuordnungForm = "projekt" | "einzelteil" | "baugruppe";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function validateForm(form: InvestitionPayload, zuordnung: ZuordnungForm): string | null {
  if (!form.name.trim()) return "Bezeichnung ist erforderlich.";
  if (!form.project.trim()) return "Projekt ist erforderlich.";
  if (!form.payment_type) return "Zahlungsart ist erforderlich.";
  if (form.amount < 0) return "Betrag darf nicht negativ sein.";
  if (form.payment_type === "Amortisation") {
    const vol = form.amortization_volume;
    if (vol == null || !Number.isInteger(vol) || vol < 1) {
      return "Amortisationsvolumen muss eine positive ganze Zahl sein.";
    }
  }
  if (zuordnung === "einzelteil" && !form.calculation_id) return "Bitte ein Einzelteil wählen.";
  if (zuordnung === "baugruppe" && !form.baugruppe_id) return "Bitte eine Baugruppe wählen.";
  return null;
}

export function InvestitionenPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Investition[]>([]);
  const [customers, setCustomers] = useState<string[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [kalkulationen, setKalkulationen] = useState<SpritzgussListItem[]>([]);
  const [baugruppen, setBaugruppen] = useState<BaugruppeListItem[]>([]);

  const [customerDraft, setCustomerDraft] = useState("");
  const [projectDraft, setProjectDraft] = useState("");
  const [appliedCustomer, setAppliedCustomer] = useState("");
  const [appliedProject, setAppliedProject] = useState("");

  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<InvestitionPayload>(emptyInvestitionForm());
  const [zuordnungForm, setZuordnungForm] = useState<ZuordnungForm>("projekt");

  useEffect(() => {
    listProjectOptions().then(({ customers: c, projects: p }) => {
      setCustomers(c);
      setProjects(p);
    });
    listKalkulationen().then(setKalkulationen).catch(() => undefined);
    listBaugruppen().then(setBaugruppen).catch(() => undefined);
  }, []);

  const filteredKalkulationen = useMemo(
    () =>
      kalkulationen.filter((k) => {
        if (appliedProject && k.projekt !== appliedProject) return false;
        if (appliedCustomer && k.kunde !== appliedCustomer) return false;
        return true;
      }),
    [kalkulationen, appliedProject, appliedCustomer],
  );

  const filteredBaugruppen = useMemo(
    () =>
      baugruppen.filter((b) => {
        if (appliedProject && b.projekt !== appliedProject) return false;
        if (appliedCustomer && b.kunde !== appliedCustomer) return false;
        return true;
      }),
    [baugruppen, appliedProject, appliedCustomer],
  );

  const loadProject = useCallback(async () => {
    if (!projectDraft.trim()) {
      setError("Bitte ein Projekt auswählen.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const items = await listInvestitionen({
        project: projectDraft,
        customer: customerDraft || undefined,
      });
      setRows(items);
      setAppliedCustomer(customerDraft);
      setAppliedProject(projectDraft);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [customerDraft, projectDraft]);

  const resetFilters = () => {
    setCustomerDraft("");
    setProjectDraft("");
    setAppliedCustomer("");
    setAppliedProject("");
    setRows([]);
    setLoaded(false);
    setShowForm(false);
    setError(null);
    setSuccess(null);
  };

  const openCreate = () => {
    if (!appliedProject) {
      setError("Bitte zuerst ein Projekt laden.");
      return;
    }
    setFormMode("create");
    setEditingId(null);
    setZuordnungForm("projekt");
    setForm({
      ...emptyInvestitionForm(),
      project: appliedProject,
      customer: appliedCustomer,
    });
    setShowForm(true);
    setError(null);
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
        project: appliedProject,
        customer: appliedCustomer || form.customer,
        calculation_id: zuordnungForm === "einzelteil" ? form.calculation_id : null,
        baugruppe_id: zuordnungForm === "baugruppe" ? form.baugruppe_id : null,
        amortization_volume:
          form.payment_type === "Amortisation" ? form.amortization_volume : null,
      };
      if (formMode === "create") await createInvestition(payload);
      else if (editingId != null) await updateInvestition(editingId, payload);
      setSuccess("Investition gespeichert.");
      setShowForm(false);
      await loadProject();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const columnDefs = useMemo<ColDef<Investition>[]>(
    () => [
      { field: "name", headerName: "Bezeichnung", flex: 1, minWidth: 160 },
      { field: "investment_type", headerName: "Art", width: 120 },
      { field: "payment_type", headerName: "Zahlungsart", width: 130 },
      { field: "amount", headerName: "Betrag", width: 110, valueFormatter: (p) => euro(p.value as number) },
      {
        field: "amortization_volume",
        headerName: "Amort.-Vol.",
        width: 100,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" && p.value != null ? String(p.value) : "–",
      },
      {
        field: "cost_per_piece",
        headerName: "Kosten/Stück",
        width: 110,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" ? euro(p.value as number | null) : "–",
      },
      { field: "zuordnung", headerName: "Zuordnung", flex: 1, minWidth: 180 },
      { field: "project", headerName: "Projekt", width: 120 },
      { field: "customer", headerName: "Kunde", width: 120 },
      { field: "description", headerName: "Bemerkung", flex: 1, minWidth: 140 },
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
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Investitionen</h2>
        <p className="mt-1 text-sm text-gray-600">
          Projektbezogene Investitionsplanung – Investitionen werden im Business Case ausgewiesen,
          nicht im Einzelteilpreis.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Projektfilter</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">Kunde</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={customerDraft}
              onChange={(e) => setCustomerDraft(e.target.value)}
            >
              <option value="">Alle</option>
              {customers.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={projectDraft}
              onChange={(e) => setProjectDraft(e.target.value)}
            >
              <option value="">Alle</option>
              {projects.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !projectDraft}
            onClick={() => loadProject()}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
          >
            Projekt laden
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            Filter zurücksetzen
          </button>
          {canWrite && loaded && (
            <button
              type="button"
              onClick={openCreate}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600"
            >
              Neu
            </button>
          )}
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

      {!loaded && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
          Bitte Kunde und Projekt wählen und „Projekt laden“ klicken, um die Investitionen des
          Projekts anzuzeigen.
        </div>
      )}

      {loaded && rows.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-600">
          Für {appliedCustomer ? `${appliedCustomer} / ` : ""}
          {appliedProject} sind noch keine Investitionen erfasst.
        </div>
      )}

      {loaded && rows.length > 0 && (
        <section className="ag-theme-quartz rounded-lg border border-gray-200 bg-white p-2">
          <div style={{ height: 380, width: "100%" }}>
            <AgGridReact<Investition>
              rowData={rows}
              columnDefs={columnDefs}
              onRowDoubleClicked={(e: RowDoubleClickedEvent<Investition>) => {
                if (e.data) openEdit(e.data);
              }}
              getRowId={(p) => String(p.data.id)}
            />
          </div>
        </section>
      )}

      {showForm && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-lg font-semibold">
            {formMode === "create" ? "Neue Investition" : "Investition bearbeiten"}
          </h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="block text-sm md:col-span-2">
              <span className="text-gray-600">Bezeichnung *</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Investitionsart</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.investment_type}
                onChange={(e) => setForm({ ...form, investment_type: e.target.value })}
              >
                {INVESTMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="md:col-span-3 rounded border p-3">
              <legend className="px-1 text-sm font-medium">Zahlungsart *</legend>
              <div className="flex gap-4">
                {PAYMENT_TYPES.map((pt) => (
                  <label key={pt} className="inline-flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="payment_type"
                      checked={form.payment_type === pt}
                      onChange={() =>
                        setForm({
                          ...form,
                          payment_type: pt,
                          amortization_volume: pt === "Einmalzahlung" ? null : form.amortization_volume,
                        })
                      }
                    />
                    {pt}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="block text-sm">
              <span className="text-gray-600">Betrag (€) *</span>
              <input
                type="number"
                min={0}
                step="0.01"
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
              />
            </label>
            {form.payment_type === "Amortisation" && (
              <label className="block text-sm">
                <span className="text-gray-600">Amortisationsvolumen *</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                  value={form.amortization_volume ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      amortization_volume: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              </label>
            )}
            <fieldset className="md:col-span-3 rounded border p-3">
              <legend className="px-1 text-sm font-medium">Zuordnung</legend>
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
                      checked={zuordnungForm === key}
                      onChange={() => {
                        setZuordnungForm(key);
                        setForm({
                          ...form,
                          calculation_id: key === "einzelteil" ? form.calculation_id : null,
                          baugruppe_id: key === "baugruppe" ? form.baugruppe_id : null,
                        });
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            {zuordnungForm === "einzelteil" && (
              <label className="block text-sm md:col-span-2">
                <span className="text-gray-600">Einzelteil</span>
                <select
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                  value={form.calculation_id ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      calculation_id: e.target.value ? Number(e.target.value) : null,
                    })
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
                    setForm({
                      ...form,
                      baugruppe_id: e.target.value ? Number(e.target.value) : null,
                    })
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
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={handleSave}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Speichern
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm"
            >
              Abbrechen
            </button>
            {formMode === "edit" && editingId != null && canWrite && (
              <button
                type="button"
                onClick={async () => {
                  await archiveInvestition(editingId);
                  setShowForm(false);
                  await loadProject();
                }}
                className="rounded-md border border-red-300 px-4 py-2 text-sm text-red-700"
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
