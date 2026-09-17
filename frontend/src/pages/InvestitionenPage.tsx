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
import { useActiveProject } from "../context/ActiveProjectContext";
import { useAuth } from "../context/AuthContext";
import type { Customer, Program, Project } from "../types/hierarchy";
import {
  ASSIGNMENT_TYPES,
  emptyInvestitionForm,
  INVESTMENT_TYPES,
  isCapexPayment,
  PAYMENT_TYPES,
  type AssignmentType,
  type Investition,
  type InvestitionPayload,
  type InvestitionTarget,
} from "../types/investition";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";
import { DecimalInputField } from "../components/DecimalInputField";
import { useT } from "../i18n";

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

type TFn = (key: string, params?: Record<string, string | number | null | undefined>) => string;

const ASSIGNMENT_I18N: Record<AssignmentType, string> = {
  einzelteil: "investments.assignmentEinzelteil",
  kaufteil: "investments.assignmentKaufteil",
  baugruppe: "investments.assignmentBaugruppe",
  gesamtprojekt: "investments.assignmentGesamtprojekt",
};

const PAYMENT_I18N: Record<string, string> = {
  Amortisation: "investments.paymentAmortisation",
  Einmalzahlung: "investments.paymentEinmalzahlung",
  CAPEX: "investments.paymentCapex",
  Entwicklung: "investments.paymentEntwicklung",
};

const INVESTMENT_TYPE_I18N: Record<string, string> = {
  Werkzeug: "investments.typeWerkzeug",
  Vorrichtung: "investments.typeVorrichtung",
  Maschine: "investments.typeMaschine",
  Prüfmittel: "investments.typePruefmittel",
  Lehre: "investments.typeLehre",
  Montageanlage: "investments.typeMontageanlage",
  Sonstige: "investments.typeSonstige",
};

function validateForm(
  form: InvestitionPayload,
  hierarchy: HierarchySelection,
  assignmentType: AssignmentType | null,
  t: TFn,
): string | null {
  if (hierarchy.customer_id == null) return t("investments.errCustomer");
  if (hierarchy.program_id == null) return t("investments.errProgram");
  if (hierarchy.project_id == null) return t("investments.errProject");
  if (!assignmentType) return t("investments.errAssignmentType");
  if (!form.name.trim()) return t("investments.errName");
  if (!form.payment_type) return t("investments.errPaymentType");
  if (form.cost_amount < 0) return t("investments.errCostNegative");
  if (form.bottom_price != null && form.bottom_price < 0) {
    return t("investments.errBottomNegative");
  }
  if (form.revenue_amount != null && form.revenue_amount < 0) {
    return t("investments.errRevenueNegative");
  }
  if (form.payment_type === "Amortisation") {
    const vol = form.amortization_volume;
    if (vol == null || !Number.isInteger(vol) || vol < 1) {
      return t("investments.errAmortVolume");
    }
  }
  if (isCapexPayment(form.payment_type)) {
    if (form.cost_amount <= 0) return t("investments.errCapexCost");
    if (form.bottom_price != null || form.revenue_amount != null) {
      return t("investments.errCapexNoBottomRevenue");
    }
  }
  if (form.payment_type === "Entwicklung" && form.cost_amount <= 0) {
    return t("investments.errDevCost");
  }
  if (assignmentType === "einzelteil" && !form.calculation_id) {
    return t("investments.errSelectMolded");
  }
  if (assignmentType === "kaufteil" && !form.kaufteil_id) {
    return t("investments.errSelectPurchased");
  }
  if (assignmentType === "baugruppe" && !form.baugruppe_id) {
    return t("investments.errSelectAssembly");
  }
  return null;
}

export function InvestitionenPage() {
  const t = useT();
  const { canWrite } = useAuth();
  const { selection, isComplete, formDefaults } = useActiveProject();
  const [rows, setRows] = useState<Investition[]>([]);
  const [filterHierarchy, setFilterHierarchy] = useState<HierarchySelection>(() => formDefaults());
  const [appliedHierarchy, setAppliedHierarchy] = useState<HierarchySelection>(emptyHierarchy());
  const [filterLabels, setFilterLabels] = useState({ customer: "", program: "", project: "" });

  const [formHierarchy, setFormHierarchy] = useState<HierarchySelection>(() => formDefaults());
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
  const [costRaw, setCostRaw] = useState("0");
  const [bottomPriceRaw, setBottomPriceRaw] = useState("");
  const [revenueRaw, setRevenueRaw] = useState("");
  const [formWarnings, setFormWarnings] = useState<string[]>([]);

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    listCustomers(undefined, true).then(setCustomers).catch(() => setCustomers([]));
  }, []);

  // Globales aktives Projekt in Filter übernehmen
  useEffect(() => {
    setFilterHierarchy({
      customer_id: selection.customer_id,
      program_id: selection.program_id,
      project_id: selection.project_id,
    });
  }, [selection.customer_id, selection.program_id, selection.project_id]);

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
      setError(t("investments.selectHierarchy"));
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
      setError(err instanceof Error ? err.message : t("investments.loadFailed"));
    } finally {
      setBusy(false);
    }
  }, [filterHierarchy, resolveLabels, t]);

  // Automatisch laden, wenn globales Projekt vollständig ist
  useEffect(() => {
    if (!isComplete || filterHierarchy.project_id == null) return;
    if (
      filterHierarchy.customer_id !== selection.customer_id ||
      filterHierarchy.program_id !== selection.program_id ||
      filterHierarchy.project_id !== selection.project_id
    ) {
      return;
    }
    void loadProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- nur bei Context-Wechsel auto-laden
  }, [isComplete, selection.customer_id, selection.program_id, selection.project_id]);

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
        setError(err instanceof Error ? err.message : t("investments.targetsLoadFailed"));
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
      setError(t("investments.loadProjectFirst"));
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
    setCostRaw("0");
    setBottomPriceRaw("");
    setRevenueRaw("");
    setFormWarnings([]);
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
      cost_amount: item.cost_amount,
      bottom_price: item.bottom_price,
      revenue_amount: item.revenue_amount,
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
    setCostRaw(formatDecimalForInputDe(item.cost_amount));
    setBottomPriceRaw(
      item.bottom_price != null ? formatDecimalForInputDe(item.bottom_price) : "",
    );
    setRevenueRaw(
      item.revenue_amount != null ? formatDecimalForInputDe(item.revenue_amount) : "",
    );
    setFormWarnings(item.amount_warnings ?? []);
    setShowForm(true);
  };

  const handleSave = async () => {
    let costAmount: number;
    let bottomPrice: number | null;
    let revenueAmount: number | null;
    try {
      costAmount = coerceFormDecimal(costRaw, "0,10 oder 0.10") ?? 0;
      bottomPrice = bottomPriceRaw.trim()
        ? coerceFormDecimal(bottomPriceRaw, "0,10 oder 0.10")
        : null;
      revenueAmount = revenueRaw.trim()
        ? coerceFormDecimal(revenueRaw, "0,10 oder 0.10")
        : null;
      if (isCapexPayment(form.payment_type)) {
        bottomPrice = null;
        revenueAmount = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("investments.invalidAmount"));
      return;
    }
    const formWithAmounts = {
      ...form,
      cost_amount: costAmount,
      bottom_price: bottomPrice,
      revenue_amount: revenueAmount,
    };
    const validationError = validateForm(formWithAmounts, formHierarchy, assignmentType, t);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: InvestitionPayload = {
        ...formWithAmounts,
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
      setSuccess(t("investments.saved"));
      setShowForm(false);
      await loadProject();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("investments.saveFailed"));
    } finally {
      setBusy(false);
    }
  };

  const columnDefs = useMemo<ColDef<Investition>[]>(
    () => [
      { field: "customer", headerName: t("investments.colCustomer"), width: 120 },
      { field: "project", headerName: t("investments.colProject"), width: 120 },
      {
        field: "assignment_type",
        headerName: t("investments.colAssignmentType"),
        width: 120,
        valueFormatter: (p) => {
          const key = p.value as AssignmentType | null;
          return key && key in ASSIGNMENT_I18N ? t(ASSIGNMENT_I18N[key]) : (p.data?.assignment_type_label || "");
        },
      },
      {
        headerName: t("investments.colMaterialNo"),
        width: 110,
        valueGetter: (p) =>
          p.data?.assignment_type === "gesamtprojekt"
            ? t("investments.overallProject")
            : p.data?.part_number || t("common.dash"),
      },
      { field: "zuordnung", headerName: t("investments.colTarget"), flex: 1, minWidth: 180 },
      { field: "name", headerName: t("investments.colDesignation"), flex: 1, minWidth: 160 },
      {
        field: "investment_type",
        headerName: t("investments.colType"),
        width: 120,
        valueFormatter: (p) =>
          p.value ? t(INVESTMENT_TYPE_I18N[String(p.value)] ?? String(p.value)) : "",
      },
      {
        field: "payment_type",
        headerName: t("investments.colPaymentType"),
        width: 130,
        valueFormatter: (p) =>
          p.value ? t(PAYMENT_I18N[String(p.value)] ?? String(p.value)) : "",
      },
      { field: "cost_amount", headerName: t("investments.colCost"), width: 110, valueFormatter: (p) => euro(p.value as number) },
      {
        field: "bottom_price",
        headerName: t("investments.colBottomPrice"),
        width: 130,
        valueFormatter: (p) => euro(p.value as number | null),
      },
      {
        field: "revenue_amount",
        headerName: t("investments.colRevenue"),
        width: 110,
        valueFormatter: (p) => euro(p.value as number | null),
      },
      {
        field: "margin_revenue_minus_cost",
        headerName: t("investments.colRevenueMinusCost"),
        width: 120,
        valueFormatter: (p) => euro(p.value as number | null),
      },
      {
        field: "cost_per_piece",
        headerName: t("investments.colCostPc"),
        width: 110,
        valueFormatter: (p) =>
          p.data?.payment_type === "Amortisation" ? euro(p.value as number | null) : t("common.dash"),
      },
      { field: "description", headerName: t("investments.colNote"), flex: 1, minWidth: 140 },
      {
        headerName: t("investments.colHint"),
        width: 220,
        cellRenderer: (p: ICellRendererParams<Investition>) =>
          p.data?.payment_type === "Einmalzahlung" ? (
            <span className="text-amber-800">{t("investments.hintOneTime")}</span>
          ) : (
            ""
          ),
      },
    ],
    [t],
  );

  const filterReady =
    filterHierarchy.customer_id != null &&
    filterHierarchy.program_id != null &&
    filterHierarchy.project_id != null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">{t("nav.investments")}</h2>
        <p className="mt-1 text-sm text-gray-600">{t("investments.intro")}</p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">{t("investments.projectFilter")}</h3>
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
            {t("investments.loadProject")}
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            {t("investments.resetFilters")}
          </button>
          {canWrite && loaded && (
            <button
              type="button"
              onClick={openCreate}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600"
            >
              {t("investments.new")}
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
          {t("investments.emptyState")}
        </div>
      )}

      {loaded && rows.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-600">
          {t("investments.emptyForProject", { customer: filterLabels.customer, project: filterLabels.project })}
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
            {formMode === "create" ? t("investments.createTitle") : t("investments.editTitle")}
          </h3>

          <div className="mb-4 rounded border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-sm font-medium text-slate-800">{t("investments.assignmentRequired")}</p>
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
              <span className="text-gray-600">{t("investments.assignmentType")}</span>
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
                <option value="">{t("investments.pleaseSelect")}</option>
                {ASSIGNMENT_TYPES.map((atype) => (
                  <option key={atype} value={atype}>
                    {t(ASSIGNMENT_I18N[atype])}
                  </option>
                ))}
              </select>
            </label>

            {assignmentType === "gesamtprojekt" && formHierarchy.project_id != null && (
              <p className="mt-3 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                {t("investments.overallProjectLine", {
                  customer: formLabels.customer || t("common.dash"),
                  program: formLabels.program || t("common.dash"),
                  project: formLabels.project || t("common.dash"),
                })}
              </p>
            )}

            {assignmentType &&
              assignmentType !== "gesamtprojekt" &&
              formHierarchy.project_id != null && (
                <label className="mt-3 block text-sm">
                  <span className="text-gray-600">{t("investments.targetObject")}</span>
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
                      {targetsLoading ? t("investments.loading") : t("investments.pleaseSelect")}
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
                      {t("investments.noTargets")}
                    </p>
                  )}
                </label>
              )}
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label className="block text-sm md:col-span-2">
              <span className="text-gray-600">{t("investments.designationRequired")}</span>
              <input
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">{t("investments.investmentType")}</span>
              <select
                className="mt-1 block w-full rounded border px-2 py-1.5"
                value={form.investment_type}
                onChange={(e) => setForm({ ...form, investment_type: e.target.value })}
              >
                {INVESTMENT_TYPES.map((itype) => (
                  <option key={itype} value={itype}>
                    {t(INVESTMENT_TYPE_I18N[itype] ?? itype)}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="md:col-span-3 rounded border p-3">
              <legend className="px-1 text-sm font-medium">{t("investments.paymentType")}</legend>
              <div className="flex flex-wrap gap-4">
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
                          amortization_volume:
                            pt === "Amortisation" ? form.amortization_volume : null,
                          bottom_price: pt === "CAPEX" ? null : form.bottom_price,
                          revenue_amount: pt === "CAPEX" ? null : form.revenue_amount,
                        })
                      }
                    />
                    {t(PAYMENT_I18N[pt] ?? pt)}
                  </label>
                ))}
              </div>
              {form.payment_type === "CAPEX" && (
                <p className="mt-2 text-xs text-gray-600">{t("investments.hintCapex")}</p>
              )}
              {form.payment_type === "Entwicklung" && (
                <p className="mt-2 text-xs text-gray-600">{t("investments.hintDevelopment")}</p>
              )}
              {form.payment_type === "Einmalzahlung" && (
                <p className="mt-2 text-xs text-gray-600">{t("investments.hintOneTime")}</p>
              )}
            </fieldset>
            <DecimalInputField
              label={t("investments.costRequired")}
              rawValue={costRaw}
              onRawChange={setCostRaw}
              className="mt-1 block w-full rounded border px-2 py-1.5"
            />
            {!isCapexPayment(form.payment_type) && (
              <>
                <DecimalInputField
                  label={t("investments.bottomPrice")}
                  rawValue={bottomPriceRaw}
                  onRawChange={setBottomPriceRaw}
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                />
                <DecimalInputField
                  label={t("investments.revenue")}
                  rawValue={revenueRaw}
                  onRawChange={setRevenueRaw}
                  className="mt-1 block w-full rounded border px-2 py-1.5"
                />
              </>
            )}
            {formWarnings.length > 0 && (
              <div className="md:col-span-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <ul className="list-disc pl-5">
                  {formWarnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
            {form.payment_type === "Amortisation" && (
              <label className="block text-sm">
                <span className="text-gray-600">{t("investments.amortVolumeRequired")}</span>
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
              <span className="text-gray-600">{t("investments.note")}</span>
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
              {t("common.save")}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm"
            >
              {t("common.cancel")}
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
                {t("investments.archive")}
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
