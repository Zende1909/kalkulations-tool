import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createCustomer,
  createProgram,
  createProgramVolume,
  createProject,
  deactivateCustomer,
  deactivateProgram,
  deactivateProject,
  deleteProgramVolume,
  getCalculatedProjectVolume,
  listAvailableYears,
  listCustomers,
  listProgramVolumes,
  listPrograms,
  listProjects,
  updateCustomer,
  updateProgram,
  updateProgramVolume,
  updateProject,
} from "../../api/hierarchy";
import { StammdatenFormModal, type FormField } from "../../components/stammdaten/StammdatenFormModal";
import { useAuth } from "../../context/AuthContext";
import {
  COMPONENT_AREAS,
  PROGRAM_STATUSES,
  PROJECT_STATUSES,
  type Customer,
  type Program,
  type ProgramVolume,
  type Project,
  type ProjectVolumeCalculation,
} from "../../types/hierarchy";

type Tab = "customers" | "programs" | "projects";

const customerFields: FormField[] = [
  { name: "customer_number", label: "Kundennummer", type: "text", required: true },
  { name: "name", label: "Name", type: "text", required: true },
  { name: "notes", label: "Notizen", type: "text" },
  { name: "active", label: "Aktiv", type: "checkbox" },
];

const programFields: FormField[] = [
  { name: "program_number", label: "Programmnummer", type: "text", required: true },
  { name: "name", label: "Name", type: "text", required: true },
  { name: "vehicle_series", label: "Fahrzeugserie", type: "text" },
  { name: "sop", label: "SOP", type: "date" },
  { name: "eop", label: "EOP", type: "date" },
  { name: "status", label: "Status", type: "select", required: true, options: [...PROGRAM_STATUSES] },
  { name: "production_plant", label: "Produktionswerk", type: "text" },
  { name: "notes", label: "Notizen", type: "text" },
  { name: "active", label: "Aktiv", type: "checkbox" },
];

const volumeFields: FormField[] = [
  { name: "calendar_year", label: "Kalenderjahr", type: "number", required: true, step: "1" },
  { name: "vehicle_volume", label: "Fahrzeugstückzahl", type: "number", required: true, step: "1" },
];

const projectFields: FormField[] = [
  { name: "project_number", label: "Projektnummer", type: "text", required: true },
  { name: "name", label: "Projektname", type: "text", required: true },
  {
    name: "component_area",
    label: "Bauteilbereich",
    type: "select",
    required: true,
    options: [...COMPONENT_AREAS],
  },
  { name: "quantity_per_vehicle", label: "Anzahl pro Fahrzeug (z. B. 2 bei zwei Teilen pro Fahrzeug)", type: "number", required: true, step: "0.01" },
  { name: "status", label: "Projektstatus", type: "select", required: true, options: [...PROJECT_STATUSES] },
  { name: "notes", label: "Notizen", type: "text" },
  { name: "active", label: "Aktiv", type: "checkbox" },
];

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : "Unbekannter Fehler";
}

export function KundenProgrammeProjektePage() {
  const { canWrite } = useAuth();
  const [tab, setTab] = useState<Tab>("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | "">("");
  const [selectedProgramId, setSelectedProgramId] = useState<number | "">("");
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [calcYear, setCalcYear] = useState<number | "">("");
  const [calcResult, setCalcResult] = useState<ProjectVolumeCalculation | null>(null);
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
  const [modalVolumes, setModalVolumes] = useState<ProgramVolume[]>([]);
  const [projectPreviewVolumes, setProjectPreviewVolumes] = useState<ProgramVolume[]>([]);

  const filteredCustomers = useMemo(() => {
    if (!search.trim()) return customers;
    const t = search.toLowerCase();
    return customers.filter(
      (c) => c.name.toLowerCase().includes(t) || c.customer_number.toLowerCase().includes(t),
    );
  }, [customers, search]);

  const filteredPrograms = useMemo(() => {
    let rows = programs;
    if (selectedCustomerId !== "") {
      rows = rows.filter((p) => p.customer_id === selectedCustomerId);
    }
    if (search.trim()) {
      const t = search.toLowerCase();
      rows = rows.filter(
        (p) => p.name.toLowerCase().includes(t) || p.program_number.toLowerCase().includes(t),
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
      const t = search.toLowerCase();
      rows = rows.filter(
        (p) => p.name.toLowerCase().includes(t) || p.project_number.toLowerCase().includes(t),
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
      if (selectedProgramId !== "") {
        const years = await listAvailableYears(selectedProgramId);
        setAvailableYears(years);
      } else {
        setAvailableYears([]);
      }
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  }, [selectedCustomerId, selectedProgramId]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  useEffect(() => {
    if (selectedProjectId === "" || calcYear === "") {
      setCalcResult(null);
      return;
    }
    getCalculatedProjectVolume(selectedProjectId, calcYear)
      .then(setCalcResult)
      .catch((err) => setError(errMsg(err)));
  }, [selectedProjectId, calcYear]);

  const openCreate = (kind: typeof formKind) => {
    setFormKind(kind);
    setFormMode("create");
    setEditId(null);
    setFormError(null);
    if (kind === "customer") {
      setFormValues({ customer_number: "", name: "", notes: "", active: true });
    } else if (kind === "program") {
      if (selectedCustomerId === "") {
        setError("Bitte zuerst einen Kunden auswählen.");
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
        setError("Bitte zuerst ein Programm auswählen.");
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
        quantity_per_vehicle: r.quantity_per_vehicle,
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
          await updateProgram(editId, payload);
        } else {
          await createProgram(payload);
        }
      } else if (formKind === "volume") {
        const programId = volumesModalProgram?.id ?? (selectedProgramId as number);
        const payload = {
          program_id: programId,
          calendar_year: Number(formValues.calendar_year),
          vehicle_volume: Number(formValues.vehicle_volume),
        };
        if (formMode === "edit" && editId != null) {
          await updateProgramVolume(editId, payload);
        } else {
          await createProgramVolume(payload);
        }
        setFormOpen(false);
        setSuccess("Erfolgreich gespeichert.");
        await reloadModalVolumes();
        return;
      } else {
        const payload = {
          program_id: selectedProgramId as number,
          project_number: String(formValues.project_number),
          name: String(formValues.name),
          component_area: String(formValues.component_area),
          quantity_per_vehicle: Number(formValues.quantity_per_vehicle),
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
      setSuccess("Erfolgreich gespeichert.");
      await reloadAll();
    } catch (err) {
      setFormError(errMsg(err));
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
      setSuccess("Erfolgreich deaktiviert.");
      await reloadAll();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const openVolumesModal = async (program: Program) => {
    setVolumesModalProgram(program);
    setSelectedProgramId(program.id);
    try {
      const vols = await listProgramVolumes(program.id);
      setModalVolumes(vols);
    } catch {
      setModalVolumes([]);
    }
  };

  const reloadModalVolumes = async () => {
    if (!volumesModalProgram) return;
    const vols = await listProgramVolumes(volumesModalProgram.id);
    setModalVolumes(vols);
    await reloadAll();
  };

  const handleDeleteVolume = async (id: number) => {
    try {
      await deleteProgramVolume(id);
      setSuccess("Jahresstückzahl gelöscht.");
      await reloadModalVolumes();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const formFields =
    formKind === "customer"
      ? customerFields
      : formKind === "program"
        ? programFields
        : formKind === "volume"
          ? volumeFields
          : projectFields;

  const formTitle =
    formMode === "edit"
      ? `${formKind === "customer" ? "Kunde" : formKind === "program" ? "Programm" : formKind === "volume" ? "Jahresstückzahl" : "Projekt"} bearbeiten`
      : `${formKind === "customer" ? "Kunde" : formKind === "program" ? "Programm" : formKind === "volume" ? "Jahresstückzahl" : "Projekt"} anlegen`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Kunden, Programme & Projekte</h2>
        <p className="mt-1 text-sm text-gray-600">
          Zentrale Hierarchie: Kunde → Programm → Projekt. Projektstückzahlen werden aus
          Programmstückzahl × Anzahl pro Fahrzeug berechnet.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Kaskadische Auswahl</h3>
        <div className="flex flex-wrap gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">Kunde</span>
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
              <option value="">Alle</option>
              {customers.filter((c) => c.active).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.customer_number} – {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Programm</span>
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
              <option value="">Alle</option>
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
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block min-w-[200px] rounded border px-2 py-1.5"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : "")}
              disabled={selectedProgramId === ""}
            >
              <option value="">Alle</option>
              {projects
                .filter((p) => p.active && (selectedProgramId === "" || p.program_id === selectedProgramId))
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.project_number} – {p.name}
                  </option>
                ))}
            </select>
          </label>
          {selectedProjectId !== "" && (
            <label className="block text-sm">
              <span className="text-gray-600">Jahr (Berechnung)</span>
              <select
                className="mt-1 block min-w-[120px] rounded border px-2 py-1.5"
                value={calcYear}
                onChange={(e) => setCalcYear(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">–</option>
                {availableYears.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {calcResult && (
          <p className="mt-3 rounded bg-slate-50 px-3 py-2 text-sm text-slate-800">
            Projektstückzahl {calcResult.calendar_year}:{" "}
            <strong>
              {calcResult.project_volume.toLocaleString("de-DE")} Teile
            </strong>{" "}
            ({calcResult.vehicle_volume.toLocaleString("de-DE")} Fahrzeuge ×{" "}
            {calcResult.quantity_per_vehicle} pro Fahrzeug)
          </p>
        )}
      </section>

      <div className="flex flex-wrap items-center gap-2 border-b border-gray-200 pb-2">
        {(
          [
            ["customers", "Kunden"],
            ["programs", "Programme"],
            ["projects", "Projekte"],
          ] as const
        ).map(([key, label]) => (
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
          placeholder="Suchen…"
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
            Neu
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
        <p className="text-gray-600">Lade Daten…</p>
      ) : (
        <>
          {tab === "customers" && (
            <DataTable
              headers={["Nr.", "Name", "Aktiv", "Aktionen"]}
              rows={filteredCustomers.map((c) => [
                c.customer_number,
                c.name,
                c.active ? "Ja" : "Nein",
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
                <div className="px-4 py-10 text-center text-sm text-gray-600">Keine Programme vorhanden.</div>
              ) : (
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50 text-left text-gray-600">
                      <th className="px-4 py-2">Nr.</th>
                      <th className="px-4 py-2">Name</th>
                      <th className="px-4 py-2">Serie</th>
                      <th className="px-4 py-2">Status</th>
                      <th className="px-4 py-2">Aktiv</th>
                      <th className="px-4 py-2">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPrograms.map((p) => (
                      <tr key={p.id} className="border-b border-gray-100">
                        <td className="px-4 py-2">{p.program_number}</td>
                        <td className="px-4 py-2">{p.name}</td>
                        <td className="px-4 py-2">{p.vehicle_series}</td>
                        <td className="px-4 py-2">{p.status}</td>
                        <td className="px-4 py-2">{p.active ? "Ja" : "Nein"}</td>
                        <td className="px-4 py-2 space-x-2">
                          <button
                            type="button"
                            className="text-slate-800 underline"
                            onClick={() => openVolumesModal(p)}
                          >
                            Stückzahlen
                          </button>
                          {canWrite && (
                            <>
                              <button
                                type="button"
                                className="text-blue-700 underline"
                                onClick={() => openEdit("program", p)}
                              >
                                Bearbeiten
                              </button>
                              <button
                                type="button"
                                className="text-amber-800 underline"
                                onClick={() => handleDeactivate("program", p.id)}
                              >
                                Deaktivieren
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
              headers={["Nr.", "Name", "Bauteil", "Anzahl/Fzg.", "Status", "Aktiv", "Aktionen"]}
              rows={filteredProjects.map((p) => [
                p.project_number,
                p.name,
                p.component_area,
                String(p.quantity_per_vehicle),
                p.status,
                p.active ? "Ja" : "Nein",
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
                <h4 className="mb-2 text-sm font-semibold">Mengenübersicht (berechnet)</h4>
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-1 pr-2">Jahr</th>
                      <th className="py-1 pr-2">Fahrzeug-STZ.</th>
                      <th className="py-1 pr-2">Anzahl/Fzg.</th>
                      <th className="py-1">Projekt-STZ.</th>
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
          <div className="w-full max-w-xl rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">
                Fahrzeugstückzahlen – {volumesModalProgram.name}
              </h3>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => setVolumesModalProgram(null)}
              >
                ✕
              </button>
            </div>
            {canWrite && (
              <button
                type="button"
                className="mb-3 rounded border px-3 py-1.5 text-sm hover:bg-gray-50"
                onClick={() => {
                  setVolumesModalProgram(volumesModalProgram);
                  openCreate("volume");
                }}
              >
                Jahr hinzufügen
              </button>
            )}
            {modalVolumes.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Jahresstückzahlen hinterlegt.</p>
            ) : (
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="py-2 pr-4">Kalenderjahr</th>
                    <th className="py-2 pr-4">Fahrzeugstückzahl</th>
                    {canWrite && <th className="py-2">Aktionen</th>}
                  </tr>
                </thead>
                <tbody>
                  {modalVolumes.map((v) => (
                    <tr key={v.id} className="border-b border-gray-100">
                      <td className="py-2 pr-4">{v.calendar_year}</td>
                      <td className="py-2 pr-4">{v.vehicle_volume.toLocaleString("de-DE")}</td>
                      {canWrite && (
                        <td className="py-2 space-x-2">
                          <button
                            type="button"
                            className="text-blue-700 underline"
                            onClick={() => openEdit("volume", v)}
                          >
                            Bearbeiten
                          </button>
                          <button
                            type="button"
                            className="text-red-700 underline"
                            onClick={() => handleDeleteVolume(v.id)}
                          >
                            Löschen
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
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
        Keine Einträge vorhanden.
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
                      Bearbeiten
                    </button>
                    <button
                      type="button"
                      className="text-amber-800 underline"
                      onClick={() => onDeactivate(entity)}
                    >
                      Deaktivieren
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
