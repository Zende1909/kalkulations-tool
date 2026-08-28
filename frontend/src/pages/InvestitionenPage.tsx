import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ICellRendererParams, RowDoubleClickedEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import {
  archiveInvestition,
  createInvestition,
  listInvestitionTargets,
  listInvestitionen,
  updateInvestition,
} from "../api/investitionen";
import { listCustomers, listPrograms, listProjects } from "../api/hierarchy";
import {
  HierarchySelector,
  type HierarchySelection,
} from "../components/hierarchy/HierarchySelector";
import { useAuth } from "../context/AuthContext";
import type { Customer, Program, Project } from "../types/hierarchy";
import {
  ASSIGNMENT_TYPE_LABELS,
  ASSIGNMENT_TYPES,
  emptyInvestitionForm,
  EINMALZAHLUNG_HINWEIS,
  INVESTMENT_TYPES,
  PAYMENT_TYPES,
  type AssignmentType,
  type Investition,
  type InvestitionPayload,
  type InvestitionTarget,
} from "../types/investition";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";
import { DecimalInputField } from "../components/DecimalInputField";

type FormMode = "create" | "edit";

const emptyHierarchy = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
});

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function setObjectIdForType(
  form: InvestitionPayload,
  assignmentType: AssignmentType | null,
  objectId: number | null,
): InvestitionPayload {
  return {
    ...form,
    calculation_id: assignmentType === "einzelteil" ? objectId : null,
    kaufteil_id: assignmentType === "kaufteil" ? objectId : null,
    baugruppe_id: assignmentType === "baugruppe" ? objectId : null,
  };
}

function validateForm(
  form: InvestitionPayload,
  hierarchy: HierarchySelection,
  assignmentType: AssignmentType | null,
): string | null {
  if (hierarchy.customer_id == null) return "Kunde ist erforderlich.";
  if (hierarchy.program_id == null) return "Programm ist erforderlich.";
  if (hierarchy.project_id == null) return "Projekt ist erforderlich.";
  if (!assignmentType) return "Zuordnungstyp ist erforderlich.";
  if (!form.name.trim()) return "Bezeichnung ist erforderlich.";
  if (!form.payment_type) return "Zahlungsart ist erforderlich.";
  if (form.amount < 0) return "Betrag darf nicht negativ sein.";
  if (form.payment_type === "Amortisation") {
    const vol = form.amortization_volume;
    if (vol == null || !Number.isInteger(vol) || vol < 1) {
      return "Amortisationsvolumen muss eine positive ganze Zahl sein.";
    }
  }
  if (assignmentType === "einzelteil" && !form.calculation_id) {
    return "Bitte ein Einzelteil wählen.";
  }
  if (assignmentType === "kaufteil" && !form.kaufteil_id) {
    return "Bitte ein Kaufteil wählen.";
  }
  if (assignmentType === "baugruppe" && !form.baugruppe_id) {
    return "Bitte eine Baugruppe wählen.";
  }
  return null;
}

export function InvestitionenPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Investition[]>([]);
  const [filterHierarchy, setFilterHierarchy] = useState<HierarchySelection>(emptyHierarchy());
  const [appliedHierarchy, setAppliedHierarchy] = useState<HierarchySelection>(emptyHierarchy());
  const [filterLabels, setFilterLabels] = useState({ customer: "", program: "", project: "" });

  const [formHierarchy, setFormHierarchy] = useState<HierarchySelection>(emptyHierarchy());
  const [formLabels, setFormLabels] = useState({ customer: "", program: "", project: "" });
  const [assignmentType, setAssignmentType] = useState<AssignmentType | null>(null);
  const [targets, setTargets] = useState<InvestitionTarget[]>([]);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [selectedObjectId, setSelectedObjectId] = useState<number | null>(null);

  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<InvestitionPayload>(emptyInvestitionForm());
  const [amountRaw, setAmountRaw] = useState("0");

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    listCustomers(undefined, true).then(setCustomers).catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    if (filterHierarchy.customer_id == null) {
      setPrograms([]);
      return;
    }
    listPrograms(filterHierarchy.customer_id, undefined, true)
      .then(setPrograms)
      .catch(() => setPrograms([]));
  }, [filterHierarchy.customer_id]);

  useEffect(() => {
    if (filterHierarchy.program_id == null) {
      setProjects([]);
      return;
    }
    listProjects(filterHierarchy.program_id)
      .then(setProjects)
      .catch(() => setProjects([]));
  }, [filterHierarchy.program_id]);

  const resolveLabels = useCallback(
    (h: HierarchySelection) => {
      const customer = customers.find((c) => c.id === h.customer_id)?.name ?? "";
      const program = programs.find((p) => p.id === h.program_id)?.name ?? "";
      const project = projects.find((p) => p.id === h.project_id)?.name ?? "";
      return { customer, program, project };
    },
    [customers, programs, projects],
  );

  const loadProject = useCallback(async () => {
    if (filterHierarchy.project_id == null) {
      setError("Bitte Kunde, Programm und Projekt auswählen.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const labels = resolveLabels(filterHierarchy);
      const items = await listInvestitionen({
        linked_project_id: filterHierarchy.project_id,
        customer_id: filterHierarchy.customer_id ?? undefined,
        program_id: filterHierarchy.program_id ?? undefined,
      });
      setRows(items);
      setAppliedHierarchy({ ...filterHierarchy });
      setFilterLabels(labels);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [filterHierarchy, resolveLabels]);

  const resetFilters = () => {
    setFilterHierarchy(emptyHierarchy());
    setAppliedHierarchy(emptyHierarchy());
    setFilterLabels({ customer: "", program: "", project: "" });
    setRows([]);
    setLoaded(false);
    setShowForm(false);
    setError(null);
    setSuccess(null);
  };

  const resetDependentFormFields = (
    nextHierarchy: HierarchySelection,
    keepAssignment = false,
  ) => {
    setFormHierarchy(nextHierarchy);
    setForm((prev) =>
      setObjectIdForType(
        {
          ...prev,
          customer_id: nextHierarchy.customer_id,
          program_id: nextHierarchy.program_id,
          linked_project_id: nextHierarchy.project_id,
        },
        keepAssignment ? assignmentType : null,
        null,
      ),
    );
    if (!keepAssignment) {
      setAssignmentType(null);
      setSelectedObjectId(null);
      setTargets([]);
    }
  };

  useEffect(() => {
    if (
      !showForm ||
      formHierarchy.customer_id == null ||
      formHierarchy.program_id == null ||
      formHierarchy.project_id == null ||
      !assignmentType ||
      assignmentType === "gesamtprojekt"
    ) {
      setTargets([]);
      return;
    }
    setTargetsLoading(true);
    listInvestitionTargets({
      customer_id: formHierarchy.customer_id,
      program_id: formHierarchy.program_id,
      project_id: formHierarchy.project_id,
      assignment_type: assignmentType,
    })
      .then(setTargets)
      .catch((err) => {
        setTargets([]);
        setError(err instanceof Error ? err.message : "Zielobjekte konnten nicht geladen werden.");
      })
      .finally(() => setTargetsLoading(false));
  }, [showForm, formHierarchy, assignmentType]);

  useEffect(() => {
    if (formHierarchy.customer_id == null) {
      setFormLabels((prev) => ({ ...prev, program: "", project: "" }));
      return;
    }
    listPrograms(formHierarchy.customer_id, undefined, true)
      .then((items) => {
        const program = items.find((p) => p.id === formHierarchy.program_id)?.name ?? "";
        setFormLabels((prev) => ({ ...prev, program }));
      })
      .catch(() => undefined);
  }, [formHierarchy.customer_id, formHierarchy.program_id]);

  useEffect(() => {
    if (formHierarchy.program_id == null) {
      setFormLabels((prev) => ({ ...prev, project: "" }));
      return;
    }
    listProjects(formHierarchy.program_id)
      .then((items) => {
        const project = items.find((p) => p.id === formHierarchy.project_id)?.name ?? "";
        setFormLabels((prev) => ({ ...prev, project }));
      })
      .catch(() => undefined);
  }, [formHierarchy.program_id, formHierarchy.project_id]);

  useEffect(() => {
    const customer = customers.find((c) => c.id === formHierarchy.customer_id)?.name ?? "";
    setFormLabels((prev) => ({ ...prev, customer }));
  }, [formHierarchy.customer_id, customers]);

  const openCreate = () => {
    if (appliedHierarchy.project_id == null) {
      setError("Bitte zuerst ein Projekt laden.");
      return;
    }
    setFormMode("create");
    setEditingId(null);
    setFormHierarchy({ ...appliedHierarchy });
    setFilterLabels((labels) => {
      setFormLabels(labels);
      return labels;
    });
    setAssignmentType(null);
    setSelectedObjectId(null);
    setTargets([]);
    setForm({
      ...emptyInvestitionForm(),
      customer_id: appliedHierarchy.customer_id,
      program_id: appliedHierarchy.program_id,
      linked_project_id: appliedHierarchy.project_id,
      customer: filterLabels.customer,
      project: filterLabels.project,
    });
    setAmountRaw("0");
    setShowForm(true);
    setError(null);
  };

  const openEdit = (item: Investition) => {
    setFormMode("edit");
    setEditingId(item.id);
    const atype = (item.assignment_type as AssignmentType | null) ?? "gesamtprojekt";
    setAssignmentType(atype);
    const hierarchy: HierarchySelection = {
      customer_id: item.customer_id,
      program_id: item.program_id,
      project_id: item.linked_project_id,
    };
    setFormHierarchy(hierarchy);
    setFormLabels({
      customer: item.customer,
      program: "",
      project: item.project,
    });
    const objectId =
      item.calculation_id ?? item.kaufteil_id ?? item.baugruppe_id ?? null;
    setSelectedObjectId(objectId);
    setForm({
      name: item.name,
      investment_type: item.investment_type,
      payment_type: item.payment_type,
      amount: item.amount,
      amortization_volume: item.amortization_volume,
      project: item.project,
      customer: item.customer,
      customer_id: item.customer_id,
      program_id: item.program_id,
      linked_project_id: item.linked_project_id,
      assignment_type: atype,
      calculation_id: item.calculation_id,
      baugruppe_id: item.baugruppe_id,
      kaufteil_id: item.kaufteil_id,
      description: item.description,
    });
    setAmountRaw(formatDecimalForInputDe(item.amount));
    setShowForm(true);
  };

  const handleSave = async () => {
    let amount: number;
    try {
      amount = coerceFormDecimal(amountRaw, "0,10 oder 0.10") ?? 0;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ungültiger Betrag.");
      return;
    }
    const formWithAmount = { ...form, amount };
    const validationError = validateForm(formWithAmount, formHierarchy, assignmentType);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: InvestitionPayload = {
        ...formWithAmount,
        customer_id: formHierarchy.customer_id,
        program_id: formHierarchy.program_id,
        linked_project_id: formHierarchy.project_id,
        assignment_type: assignmentType,
        customer: formLabels.customer,
        project: formLabels.project,
        calculation_id: assignmentType === "einzelteil" ? form.calculation_id : null,
        kaufteil_id: assignmentType === "kaufteil" ? form.kaufteil_id : null,
        baugruppe_id: assignmentType === "baugruppe" ? form.baugruppe_id : null,
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
      { field: "customer", headerName: "Kunde", width: 120 },
      { field: "project", headerName: "Projekt", width: 120 },
      {
        field: "assignment_type_label",
        headerName: "Zuordnungstyp",
        width: 120,
      },
      {
        headerName: "Materialnr.",
        width: 110,
        valueGetter: (p) =>
          p.data?.assignment_type === "gesamtprojekt" ? "Gesamtprojekt" : p.data?.part_number || "–",
      },
      { field: "zuordnung", headerName: "Zielobjekt", flex: 1, minWidth: 180 },
      { field: "name", headerName: "Bezeichnung", flex: 1, minWidth: 160 },
      { field: "investment_type", headerName: "Art", width: 120 },
      { field: "payment_type", headerName: "Zahlungsart", width: 130 },
      { field: "amount", headerName: "Betrag", width: 110, valueFormatter: (p) => euro(p.value as number) },
      {
        field: "cost_per_piece",
        headerName: "Kosten/Stück",
        width: 110,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" ? euro(p.value as number | null) : "–",
      },
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

  const filterReady =
    filterHierarchy.customer_id != null &&
    filterHierarchy.program_id != null &&
    filterHierarchy.project_id != null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Investitionen</h2>
        <p className="mt-1 text-sm text-gray-600">
          Projektbezogene Investitionsplanung mit eindeutiger Zuordnung über Kunde, Programm,
          Projekt und Materialnummer.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Projektfilter</h3>
        <HierarchySelector
          value={filterHierarchy}
          onChange={(next) => setFilterHierarchy(next)}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !filterReady}
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
          Bitte Kunde, Programm und Projekt wählen und „Projekt laden“ klicken.
        </div>
      )}

      {loaded && rows.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-600">
          Für {filterLabels.customer} / {filterLabels.project} sind noch keine Investitionen
          erfasst.
        </div>
      )}

      {loaded && rows.length > 0 && (
        <section className="ag-theme-quartz rounded-lg border border-gray-200 bg-white p-2">
          <div style={{ height: 420, width: "100%" }}>
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

          <div className="mb-4 rounded border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-sm font-medium text-slate-800">Zuordnung (Pflicht)</p>
            <HierarchySelector
              value={formHierarchy}
              onChange={(next) => {
                if (next.customer_id !== formHierarchy.customer_id) {
                  resetDependentFormFields({
                    customer_id: next.customer_id,
                    program_id: null,
                    project_id: null,
                  });
                } else if (next.program_id !== formHierarchy.program_id) {
                  resetDependentFormFields({
                    customer_id: next.customer_id,
                    program_id: next.program_id,
                    project_id: null,
                  });
                } else {
                  resetDependentFormFields(next, true);
                }
              }}
            />
            <label className="mt-3 block text-sm">
              <span className="text-gray-600">Zuordnungstyp *</span>
              <select
                className="mt-1 block w-full max-w-md rounded border px-2 py-1.5 disabled:bg-gray-100"
                disabled={formHierarchy.project_id == null}
                value={assignmentType ?? ""}
                onChange={(e) => {
                  const next = (e.target.value || null) as AssignmentType | null;
                  setAssignmentType(next);
                  setSelectedObjectId(null);
                  setForm((prev) =>
                    setObjectIdForType(
                      { ...prev, assignment_type: next },
                      next,
                      null,
                    ),
                  );
                }}
              >
                <option value="">Bitte wählen …</option>
                {ASSIGNMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {ASSIGNMENT_TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </label>

            {assignmentType === "gesamtprojekt" && formHierarchy.project_id != null && (
              <p className="mt-3 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                Gesamtprojekt: {formLabels.customer || "–"} / {formLabels.program || "–"} /{" "}
                {formLabels.project || "–"}
              </p>
            )}

            {assignmentType &&
              assignmentType !== "gesamtprojekt" &&
              formHierarchy.project_id != null && (
                <label className="mt-3 block text-sm">
                  <span className="text-gray-600">Zielobjekt *</span>
                  <select
                    className="mt-1 block w-full rounded border px-2 py-1.5"
                    disabled={targetsLoading}
                    value={selectedObjectId ?? ""}
                    onChange={(e) => {
                      const id = e.target.value ? Number(e.target.value) : null;
                      setSelectedObjectId(id);
                      setForm((prev) => setObjectIdForType(prev, assignmentType, id));
                    }}
                  >
                    <option value="">
                      {targetsLoading ? "Lade …" : "Bitte wählen …"}
                    </option>
                    {targets.map((t) => (
                      <option key={t.object_id} value={t.object_id}>
                        {t.label}
                        {t.part_price != null ? ` (${euro(t.part_price)})` : ""}
                        {t.supplier ? ` – ${t.supplier}` : ""}
                      </option>
                    ))}
                  </select>
                  {!targetsLoading && targets.length === 0 && (
                    <p className="mt-1 text-xs text-amber-700">
                      Keine passenden Objekte für diese Auswahl vorhanden.
                    </p>
                  )}
                </label>
              )}
          </div>

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
            <DecimalInputField
              label="Betrag (€) *"
              rawValue={amountRaw}
              onRawChange={setAmountRaw}
              className="mt-1 block w-full rounded border px-2 py-1.5"
            />
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
