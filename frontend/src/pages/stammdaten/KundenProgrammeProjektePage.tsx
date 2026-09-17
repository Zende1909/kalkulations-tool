import { useCallback, useEffect, useMemo, useState } from "react";

import { coerceFormDecimal, formatDecimalForInputDe } from "../../utils/decimalInput";
import {
  bulkSaveProgramVolumes,
  createCustomer,
  createProgram,
  createProject,
  deactivateCustomer,
  deactivateProgram,
  deactivateProject,
  deleteProgramYearVolume,
  generateProgramYears,
  getProgramVolumeProfile,
  getProjectVolumeProfile,
  listCustomers,
  listProgramVolumes,
  listPrograms,
  listProjects,
  updateCustomer,
  updateProgramWithSopConfirm,
  updateProject,
} from "../../api/hierarchy";
import { StammdatenFormModal, type FormField } from "../../components/stammdaten/StammdatenFormModal";
import { useAuth } from "../../context/AuthContext";
import { useT } from "../../i18n";
import {
  COMPONENT_AREAS,
  PROGRAM_STATUSES,
  PROJECT_STATUSES,
  type Customer,
  type Program,
  type ProgramVolume,
  type Project,
  type ProjectVolumeProfile,
} from "../../types/hierarchy";

type Tab = "customers" | "programs" | "projects";

function errMsg(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export function KundenProgrammeProjektePage() {
  const t = useT();
  const { canWrite } = useAuth();
  const [tab, setTab] = useState<Tab>("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | "">("");
  const [selectedProgramId, setSelectedProgramId] = useState<number | "">("");
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [projectVolumeProfile, setProjectVolumeProfile] = useState<ProjectVolumeProfile | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKind, setFormKind] = useState<"customer" | "program" | "volume" | "project">("customer");
  const [editId, setEditId] = useState<number | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string | number | boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [volumesModalProgram, setVolumesModalProgram] = useState<Program | null>(null);
  const [modalVolumeRows, setModalVolumeRows] = useState<{ calendar_year: number; vehicle_volume: number }[]>([]);
  const [volumeModalBusy, setVolumeModalBusy] = useState(false);
  const [volumeModalError, setVolumeModalError] = useState<string | null>(null);
  const [projectPreviewVolumes, setProjectPreviewVolumes] = useState<ProgramVolume[]>([]);
  const [sopEopConfirmPending, setSopEopConfirmPending] = useState<boolean>(false);

  const customerFields = useMemo(
    (): FormField[] => [
      { name: "customer_number", label: t("masterData.customerNumber"), type: "text", required: true },
      { name: "name", label: t("masterData.name"), type: "text", required: true },
      { name: "notes", label: t("masterData.notes"), type: "text" },
      { name: "active", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  const programFields = useMemo(
    (): FormField[] => [
      { name: "program_number", label: t("masterData.programNumber"), type: "text", required: true },
      { name: "name", label: t("masterData.name"), type: "text", required: true },
      { name: "vehicle_series", label: t("masterData.vehicleSeries"), type: "text" },
      { name: "sop", label: t("masterData.sop"), type: "date" },
      { name: "eop", label: t("masterData.eop"), type: "date" },
      {
        name: "status",
        label: t("masterData.statusLabel"),
        type: "select",
        required: true,
        options: [...PROGRAM_STATUSES],
      },
      { name: "production_plant", label: t("masterData.productionPlant"), type: "text" },
      { name: "notes", label: t("masterData.notes"), type: "text" },
      { name: "active", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  const volumeFields = useMemo(
    (): FormField[] => [
      {
        name: "calendar_year",
        label: t("masterData.calendarYear"),
        type: "number",
        required: true,
        step: "1",
      },
      {
        name: "vehicle_volume",
        label: t("masterData.vehicleVolume"),
        type: "number",
        required: true,
        step: "1",
      },
    ],
    [t],
  );

  const projectFields = useMemo(
    (): FormField[] => [
      { name: "project_number", label: t("masterData.projectNumber"), type: "text", required: true },
      { name: "name", label: t("masterData.projectName"), type: "text", required: true },
      {
        name: "component_area",
        label: t("project.componentArea"),
        type: "select",
        required: true,
        options: [...COMPONENT_AREAS],
      },
      {
        name: "quantity_per_vehicle",
        label: t("masterData.quantityPerVehicleLong"),
        type: "number",
        required: true,
        step: "0.01",
      },
      {
        name: "status",
        label: t("masterData.projectStatus"),
        type: "select",
        required: true,
        options: [...PROJECT_STATUSES],
      },
      { name: "notes", label: t("masterData.notes"), type: "text" },
      { name: "active", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  const filteredCustomers = useMemo(() => {
    if (!search.trim()) return customers;
    const q = search.toLowerCase();
    return customers.filter(
      (c) => c.name.toLowerCase().includes(q) || c.customer_number.toLowerCase().includes(q),
    );
  }, [customers, search]);

  const filteredPrograms = useMemo(() => {
    let rows = programs;
    if (selectedCustomerId !== "") {
      rows = rows.filter((p) => p.customer_id === selectedCustomerId);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (p) => p.name.toLowerCase().includes(q) || p.program_number.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [programs, selectedCustomerId, search]);

  const filteredProjects = useMemo(() => {
    let rows = projects;
    if (selectedProgramId !== "") {
      rows = rows.filter((p) => p.program_id === selectedProgramId);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (p) => p.name.toLowerCase().includes(q) || p.project_number.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [projects, selectedProgramId, search]);

  const reloadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [c, p, j] = await Promise.all([
        listCustomers(),
        listPrograms(selectedCustomerId === "" ? undefined : selectedCustomerId),
        listProjects(selectedProgramId === "" ? undefined : selectedProgramId),
      ]);
      setCustomers(c);
      setPrograms(p);
      setProjects(j);
    } catch (err) {
      setError(errMsg(err, t("masterData.unknownError")));
    } finally {
      setLoading(false);
    }
  }, [selectedCustomerId, selectedProgramId, t]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  useEffect(() => {
    if (selectedProjectId === "") {
      setProjectVolumeProfile(null);
      return;
    }
    getProjectVolumeProfile(selectedProjectId)
      .then(setProjectVolumeProfile)
      .catch(() => setProjectVolumeProfile(null));
  }, [selectedProjectId]);

  const openCreate = (kind: typeof formKind) => {
    setFormKind(kind);
    setFormMode("create");
    setEditId(null);
    setFormError(null);
    if (kind === "customer") {
      setFormValues({ customer_number: "", name: "", notes: "", active: true });
    } else if (kind === "program") {
      if (selectedCustomerId === "") {
        setError(t("masterData.selectCustomerFirst"));
        return;
      }
      setFormValues({
        program_number: "",
        name: "",
        vehicle_series: "",
        sop: "",
        eop: "",
        status: "Anfrage",
        production_plant: "",
        notes: "",
        active: true,
      });
    } else if (kind === "volume") {
      if (volumesModalProgram) {
        setSelectedProgramId(volumesModalProgram.id);
      }
      setFormValues({ calendar_year: new Date().getFullYear(), vehicle_volume: 0 });
    } else {
      if (selectedProgramId === "") {
        setError(t("masterData.selectProgramFirst"));
        return;
      }
      setFormValues({
        project_number: "",
        name: "",
        component_area: "Interior",
        quantity_per_vehicle: 1,
        status: "Anfrage",
        notes: "",
        active: true,
      });
      listProgramVolumes(selectedProgramId)
        .then(setProjectPreviewVolumes)
        .catch(() => setProjectPreviewVolumes([]));
    }
    setFormOpen(true);
  };

  const openEdit = (
    kind: typeof formKind,
    row: Customer | Program | ProgramVolume | Project,
  ) => {
    setFormKind(kind);
    setFormMode("edit");
    setEditId(row.id);
    setFormError(null);
    if (kind === "customer") {
      const r = row as Customer;
      setFormValues({
        customer_number: r.customer_number,
        name: r.name,
        notes: r.notes,
        active: r.active,
      });
    } else if (kind === "program") {
      const r = row as Program;
      setFormValues({
        program_number: r.program_number,
        name: r.name,
        vehicle_series: r.vehicle_series,
        sop: r.sop?.slice(0, 10) ?? "",
        eop: r.eop?.slice(0, 10) ?? "",
        status: r.status,
        production_plant: r.production_plant,
        notes: r.notes,
        active: r.active,
      });
    } else if (kind === "volume") {
      const r = row as ProgramVolume;
      setFormValues({ calendar_year: r.calendar_year, vehicle_volume: r.vehicle_volume });
    } else {
      const r = row as Project;
      const area = COMPONENT_AREAS.includes(r.component_area as (typeof COMPONENT_AREAS)[number])
        ? r.component_area
        : "Interior";
      setFormValues({
        project_number: r.project_number,
        name: r.name,
        component_area: area,
        quantity_per_vehicle: formatDecimalForInputDe(r.quantity_per_vehicle),
        status: r.status,
        notes: r.notes,
        active: r.active,
      });
      listProgramVolumes(r.program_id).then(setProjectPreviewVolumes).catch(() => setProjectPreviewVolumes([]));
    }
    setFormOpen(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setFormError(null);
    try {
      if (formKind === "customer") {
        const payload = {
          customer_number: String(formValues.customer_number),
          name: String(formValues.name),
          notes: String(formValues.notes ?? ""),
          active: Boolean(formValues.active),
        };
        if (formMode === "edit" && editId != null) {
          await updateCustomer(editId, payload);
        } else {
          await createCustomer(payload);
        }
      } else if (formKind === "program") {
        const payload = {
          customer_id: selectedCustomerId as number,
          program_number: String(formValues.program_number),
          name: String(formValues.name),
          vehicle_series: String(formValues.vehicle_series ?? ""),
          sop: String(formValues.sop ?? "") || null,
          eop: String(formValues.eop ?? "") || null,
          status: String(formValues.status),
          production_plant: String(formValues.production_plant ?? ""),
          notes: String(formValues.notes ?? ""),
          active: Boolean(formValues.active),
        };
        if (formMode === "edit" && editId != null) {
          try {
            await updateProgramWithSopConfirm(editId, payload, sopEopConfirmPending);
          } catch (err) {
            const msg = errMsg(err, t("masterData.unknownError"));
            if (msg.includes("sop_eop_shrink") || msg.includes("außerhalb des neuen")) {
              setSopEopConfirmPending(true);
              setFormError(t("masterData.sopEopConfirmRetry", { msg }));
              setSubmitting(false);
              return;
            }
            throw err;
          }
          setSopEopConfirmPending(false);
        } else {
          await createProgram(payload);
        }
      } else if (formKind === "volume") {
        setFormError(t("masterData.saveVolumesInProgramDialog"));
        setSubmitting(false);
        return;
      } else {
        const payload = {
          program_id: selectedProgramId as number,
          project_number: String(formValues.project_number),
          name: String(formValues.name),
          component_area: String(formValues.component_area),
          quantity_per_vehicle: coerceFormDecimal(
            formValues.quantity_per_vehicle,
            "1,5 oder 1.5",
          ) ?? 1,
          status: String(formValues.status),
          notes: String(formValues.notes ?? ""),
          active: Boolean(formValues.active),
        };
        if (formMode === "edit" && editId != null) {
          await updateProject(editId, payload);
        } else {
          await createProject(payload);
        }
      }
      setFormOpen(false);
      setSuccess(t("masterData.savedSuccess"));
      await reloadAll();
    } catch (err) {
      setFormError(errMsg(err, t("masterData.unknownError")));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (kind: "customer" | "program" | "project", id: number) => {
    setError(null);
    try {
      if (kind === "customer") await deactivateCustomer(id);
      else if (kind === "program") await deactivateProgram(id);
      else await deactivateProject(id);
      setSuccess(t("masterData.deactivatedSuccess"));
      await reloadAll();
    } catch (err) {
      setError(errMsg(err, t("masterData.unknownError")));
    }
  };

  const openVolumesModal = async (program: Program) => {
    setVolumesModalProgram(program);
    setSelectedProgramId(program.id);
    setVolumeModalError(null);
    try {
      const profile = await getProgramVolumeProfile(program.id);
      setModalVolumeRows(
        profile.rows.map((r) => ({
          calendar_year: r.calendar_year,
          vehicle_volume: r.vehicle_volume,
        })),
      );
    } catch {
      setModalVolumeRows([]);
    }
  };

  const reloadModalVolumes = async () => {
    if (!volumesModalProgram) return;
    const profile = await getProgramVolumeProfile(volumesModalProgram.id);
    setModalVolumeRows(
      profile.rows.map((r) => ({
        calendar_year: r.calendar_year,
        vehicle_volume: r.vehicle_volume,
      })),
    );
    await reloadAll();
  };

  const handleGenerateYears = async () => {
    if (!volumesModalProgram) return;
    setVolumeModalBusy(true);
    setVolumeModalError(null);
    try {
      const profile = await generateProgramYears(volumesModalProgram.id);
      setModalVolumeRows(
        profile.rows.map((r) => ({
          calendar_year: r.calendar_year,
          vehicle_volume: r.vehicle_volume,
        })),
      );
      setSuccess(t("masterData.yearsGenerated"));
    } catch (err) {
      setVolumeModalError(errMsg(err, t("masterData.unknownError")));
    } finally {
      setVolumeModalBusy(false);
    }
  };

  const handleBulkSaveVolumes = async () => {
    if (!volumesModalProgram) return;
    setVolumeModalBusy(true);
    setVolumeModalError(null);
    try {
      const years = modalVolumeRows.map((r) => r.calendar_year);
      if (new Set(years).size !== years.length) {
        throw new Error(t("masterData.duplicateYears"));
      }
      for (const row of modalVolumeRows) {
        if (row.vehicle_volume < 0) {
          throw new Error(t("masterData.volumesNegative"));
        }
      }
      await bulkSaveProgramVolumes(volumesModalProgram.id, modalVolumeRows);
      setSuccess(t("masterData.volumesSaved"));
      await reloadModalVolumes();
    } catch (err) {
      setVolumeModalError(errMsg(err, t("masterData.unknownError")));
    } finally {
      setVolumeModalBusy(false);
    }
  };

  const handleAddVolumeYear = () => {
    const nextYear =
      modalVolumeRows.length > 0
        ? Math.max(...modalVolumeRows.map((r) => r.calendar_year)) + 1
        : new Date().getFullYear();
    if (modalVolumeRows.some((r) => r.calendar_year === nextYear)) return;
    setModalVolumeRows((rows) => [...rows, { calendar_year: nextYear, vehicle_volume: 0 }]);
  };

  const formFields =
    formKind === "customer"
      ? customerFields
      : formKind === "program"
        ? programFields
        : formKind === "volume"
          ? volumeFields
          : projectFields;

  const entityLabel =
    formKind === "customer"
      ? t("masterData.entityCustomer")
      : formKind === "program"
        ? t("masterData.entityProgram")
        : formKind === "volume"
          ? t("masterData.entityAnnualVolume")
          : t("masterData.entityProject");

  const formTitle =
    formMode === "edit"
      ? t("masterData.editEntity", { entity: entityLabel })
      : t("masterData.createEntity", { entity: entityLabel });

  const tabItems = [
    ["customers", t("masterData.tabCustomers")],
    ["programs", t("masterData.tabPrograms")],
    ["projects", t("masterData.tabProjects")],
  ] as const;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">{t("nav.hierarchy")}</h2>
        <p className="mt-1 text-sm text-gray-600">{t("masterData.hierarchyIntro")}</p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">{t("masterData.cascadeSelection")}</h3>
        <div className="flex flex-wrap gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">{t("project.customer")}</span>
            <select
              className="mt-1 block min-w-[200px] rounded border px-2 py-1.5"
              value={selectedCustomerId}
              onChange={(e) => {
                const v = e.target.value ? Number(e.target.value) : "";
                setSelectedCustomerId(v);
                setSelectedProgramId("");
                setSelectedProjectId("");
              }}
            >
              <option value="">{t("common.all")}</option>
              {customers.filter((c) => c.active).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.customer_number} – {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("project.program")}</span>
            <select
              className="mt-1 block min-w-[200px] rounded border px-2 py-1.5"
              value={selectedProgramId}
              onChange={(e) => {
                const v = e.target.value ? Number(e.target.value) : "";
                setSelectedProgramId(v);
                setSelectedProjectId("");
              }}
              disabled={selectedCustomerId === ""}
            >
              <option value="">{t("common.all")}</option>
              {programs
                .filter((p) => p.active && (selectedCustomerId === "" || p.customer_id === selectedCustomerId))
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.program_number} – {p.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("project.project")}</span>
            <select
              className="mt-1 block min-w-[200px] rounded border px-2 py-1.5"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : "")}
              disabled={selectedProgramId === ""}
            >
              <option value="">{t("common.all")}</option>
              {projects
                .filter((p) => p.active && (selectedProgramId === "" || p.program_id === selectedProgramId))
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.project_number} – {p.name}
                  </option>
                ))}
            </select>
          </label>
          {selectedProjectId !== "" && projectVolumeProfile && projectVolumeProfile.rows.length > 0 && (
            <div className="mt-4 w-full overflow-x-auto">
              <h4 className="mb-2 text-sm font-semibold text-gray-700">
                {t("project.volumeOverLifetime")}
              </h4>
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="py-1 pr-3">{t("project.year")}</th>
                    <th className="py-1 pr-3">{t("masterData.programVehicles")}</th>
                    <th className="py-1 pr-3">{t("project.quantityPerVehicle")}</th>
                    <th className="py-1">{t("masterData.projectVolume")}</th>
                  </tr>
                </thead>
                <tbody>
                  {projectVolumeProfile.rows.map((row) => (
                    <tr key={row.calendar_year} className="border-b border-gray-100">
                      <td className="py-1 pr-3">{row.calendar_year}</td>
                      <td className="py-1 pr-3">{row.vehicle_volume.toLocaleString("de-DE")}</td>
                      <td className="py-1 pr-3">{row.quantity_per_vehicle}</td>
                      <td className="py-1">{row.project_volume.toLocaleString("de-DE")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2 border-b border-gray-200 pb-2">
        {tabItems.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              tab === key ? "bg-slate-800 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
        <input
          type="search"
          placeholder={t("common.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto rounded border px-3 py-1.5 text-sm"
        />
        {canWrite && (
          <button
            type="button"
            onClick={() =>
              openCreate(tab === "customers" ? "customer" : tab === "programs" ? "program" : "project")
            }
            className="rounded-md bg-slate-700 px-3 py-1.5 text-sm text-white hover:bg-slate-600"
          >
            {t("masterData.new")}
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
          {success}
        </div>
      )}

      {loading ? (
        <p className="text-gray-600">{t("masterData.loadingData")}</p>
      ) : (
        <>
          {tab === "customers" && (
            <DataTable
              headers={[
                t("masterData.numberCol"),
                t("masterData.name"),
                t("common.active"),
                t("common.actions"),
              ]}
              rows={filteredCustomers.map((c) => [
                c.customer_number,
                c.name,
                c.active ? t("common.yes") : t("common.no"),
                c,
              ])}
              canWrite={canWrite}
              onEdit={(row) => openEdit("customer", row as Customer)}
              onDeactivate={(row) => handleDeactivate("customer", (row as Customer).id)}
            />
          )}

          {tab === "programs" && (
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              {filteredPrograms.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-gray-600">
                  {t("masterData.noPrograms")}
                </div>
              ) : (
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50 text-left text-gray-600">
                      <th className="px-4 py-2">{t("masterData.numberCol")}</th>
                      <th className="px-4 py-2">{t("masterData.name")}</th>
                      <th className="px-4 py-2">{t("masterData.series")}</th>
                      <th className="px-4 py-2">{t("masterData.statusLabel")}</th>
                      <th className="px-4 py-2">{t("common.active")}</th>
                      <th className="px-4 py-2">{t("common.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPrograms.map((p) => (
                      <tr key={p.id} className="border-b border-gray-100">
                        <td className="px-4 py-2">{p.program_number}</td>
                        <td className="px-4 py-2">{p.name}</td>
                        <td className="px-4 py-2">{p.vehicle_series}</td>
                        <td className="px-4 py-2">{p.status}</td>
                        <td className="px-4 py-2">{p.active ? t("common.yes") : t("common.no")}</td>
                        <td className="px-4 py-2 space-x-2">
                          <button
                            type="button"
                            className="text-slate-800 underline"
                            onClick={() => openVolumesModal(p)}
                          >
                            {t("masterData.volumes")}
                          </button>
                          {canWrite && (
                            <>
                              <button
                                type="button"
                                className="text-blue-700 underline"
                                onClick={() => openEdit("program", p)}
                              >
                                {t("common.edit")}
                              </button>
                              <button
                                type="button"
                                className="text-amber-800 underline"
                                onClick={() => handleDeactivate("program", p.id)}
                              >
                                {t("masterData.deactivate")}
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === "projects" && (
            <DataTable
              headers={[
                t("masterData.numberCol"),
                t("masterData.name"),
                t("masterData.partArea"),
                t("masterData.qtyPerVehicleShort"),
                t("masterData.statusLabel"),
                t("common.active"),
                t("common.actions"),
              ]}
              rows={filteredProjects.map((p) => [
                p.project_number,
                p.name,
                p.component_area,
                String(p.quantity_per_vehicle),
                p.status,
                p.active ? t("common.yes") : t("common.no"),
                p,
              ])}
              canWrite={canWrite}
              onEdit={(row) => openEdit("project", row as Project)}
              onDeactivate={(row) => handleDeactivate("project", (row as Project).id)}
            />
          )}
        </>
      )}

      {formOpen && (
        <>
          <StammdatenFormModal
            title={formTitle}
            fields={formFields}
            values={formValues}
            submitting={submitting}
            error={formError}
            onChange={(name, value) => setFormValues((c) => ({ ...c, [name]: value }))}
            onClose={() => {
              setFormOpen(false);
              setProjectPreviewVolumes([]);
            }}
            onSubmit={handleSubmit}
          />
          {formKind === "project" && projectPreviewVolumes.length > 0 && (
            <div className="fixed inset-0 z-40 flex items-end justify-center pointer-events-none">
              <div className="pointer-events-auto mb-8 w-full max-w-lg rounded-lg border bg-white p-4 shadow-lg">
                <h4 className="mb-2 text-sm font-semibold">{t("masterData.volumeOverviewCalculated")}</h4>
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-1 pr-2">{t("project.year")}</th>
                      <th className="py-1 pr-2">{t("masterData.vehicleStz")}</th>
                      <th className="py-1 pr-2">{t("masterData.qtyPerVehicleShort")}</th>
                      <th className="py-1">{t("masterData.projectStz")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projectPreviewVolumes.map((v) => (
                      <tr key={v.id} className="border-b border-gray-100">
                        <td className="py-1 pr-2">{v.calendar_year}</td>
                        <td className="py-1 pr-2">{v.vehicle_volume.toLocaleString("de-DE")}</td>
                        <td className="py-1 pr-2">{Number(formValues.quantity_per_vehicle ?? 0)}</td>
                        <td className="py-1">
                          {(v.vehicle_volume * Number(formValues.quantity_per_vehicle ?? 0)).toLocaleString(
                            "de-DE",
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {volumesModalProgram && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">{t("masterData.volumesByYear")}</h3>
                <p className="text-sm text-gray-600">{volumesModalProgram.name}</p>
                <p className="text-xs text-gray-500">
                  {t("masterData.sop")}: {volumesModalProgram.sop?.slice(0, 10) ?? t("common.dash")} ·{" "}
                  {t("masterData.eop")}: {volumesModalProgram.eop?.slice(0, 10) ?? t("common.dash")}
                </p>
              </div>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => setVolumesModalProgram(null)}
                aria-label={t("common.close")}
              >
                ✕
              </button>
            </div>

            {volumeModalError && (
              <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                {volumeModalError}
              </div>
            )}

            <div className="mb-3 flex flex-wrap gap-2">
              {canWrite && (
                <>
                  <button
                    type="button"
                    disabled={volumeModalBusy}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
                    onClick={handleGenerateYears}
                  >
                    {t("masterData.generateYearsFromSopEop")}
                  </button>
                  <button
                    type="button"
                    disabled={volumeModalBusy}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
                    onClick={handleAddVolumeYear}
                  >
                    {t("masterData.addYear")}
                  </button>
                  <button
                    type="button"
                    disabled={volumeModalBusy}
                    className="rounded bg-slate-700 px-3 py-1.5 text-sm text-white hover:bg-slate-600 disabled:opacity-50"
                    onClick={handleBulkSaveVolumes}
                  >
                    {t("masterData.saveVolumes")}
                  </button>
                </>
              )}
            </div>

            {modalVolumeRows.length === 0 ? (
              <p className="text-sm text-gray-600">{t("masterData.noYearRows")}</p>
            ) : (
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="py-2 pr-4">{t("masterData.calendarYear")}</th>
                    <th className="py-2 pr-4">{t("masterData.vehicleVolume")}</th>
                    {canWrite && <th className="py-2">{t("common.delete")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {modalVolumeRows.map((row, index) => (
                    <tr key={`${row.calendar_year}-${index}`} className="border-b border-gray-100">
                      <td className="py-2 pr-4">
                        {canWrite ? (
                          <input
                            type="number"
                            className="w-24 rounded border px-2 py-1"
                            value={row.calendar_year}
                            onChange={(e) => {
                              const year = Number(e.target.value);
                              setModalVolumeRows((rows) =>
                                rows.map((r, i) => (i === index ? { ...r, calendar_year: year } : r)),
                              );
                            }}
                          />
                        ) : (
                          row.calendar_year
                        )}
                      </td>
                      <td className="py-2 pr-4">
                        {canWrite ? (
                          <input
                            type="number"
                            min={0}
                            className="w-32 rounded border px-2 py-1"
                            value={row.vehicle_volume}
                            onChange={(e) => {
                              const vol = Number(e.target.value);
                              setModalVolumeRows((rows) =>
                                rows.map((r, i) => (i === index ? { ...r, vehicle_volume: vol } : r)),
                              );
                            }}
                          />
                        ) : (
                          row.vehicle_volume.toLocaleString("de-DE")
                        )}
                      </td>
                      {canWrite && (
                        <td className="py-2">
                          <button
                            type="button"
                            className="text-red-700 underline"
                            onClick={async () => {
                              if (!volumesModalProgram) return;
                              try {
                                await deleteProgramYearVolume(
                                  volumesModalProgram.id,
                                  row.calendar_year,
                                );
                                await reloadModalVolumes();
                              } catch {
                                setModalVolumeRows((rows) => rows.filter((_, i) => i !== index));
                              }
                            }}
                          >
                            {t("common.delete")}
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DataTable({
  headers,
  rows,
  canWrite,
  onEdit,
  onDeactivate,
}: {
  headers: string[];
  rows: (string | Customer | Program | Project)[][];
  canWrite: boolean;
  onEdit: (row: Customer | Program | Project) => void;
  onDeactivate: (row: Customer | Program | Project) => void;
}) {
  const t = useT();
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
        {t("masterData.noEntries")}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50 text-left text-gray-600">
            {headers.map((h) => (
              <th key={h} className="px-4 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const entity = row[row.length - 1] as Customer | Program | Project;
            const cells = row.slice(0, -1) as string[];
            return (
              <tr key={idx} className="border-b border-gray-100">
                {cells.map((cell, i) => (
                  <td key={i} className="px-4 py-2">
                    {cell}
                  </td>
                ))}
                {canWrite && (
                  <td className="px-4 py-2 space-x-2">
                    <button type="button" className="text-blue-700 underline" onClick={() => onEdit(entity)}>
                      {t("common.edit")}
                    </button>
                    <button
                      type="button"
                      className="text-amber-800 underline"
                      onClick={() => onDeactivate(entity)}
                    >
                      {t("masterData.deactivate")}
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
