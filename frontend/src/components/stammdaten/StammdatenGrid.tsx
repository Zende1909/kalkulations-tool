import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  ColDef,
  GetRowIdParams,
  ICellRendererParams,
  RowDoubleClickedEvent,
  RowSelectedEvent,
} from "ag-grid-community";
import { PencilSimple, Plus, Trash } from "@phosphor-icons/react";

import { api, getApiBaseUrl, NetworkError } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { PageHeader } from "../ui/PageHeader";
import { ValidationMessage } from "../ui/ValidationMessage";
import { FormField, StammdatenFormModal } from "./StammdatenFormModal";
import { formatDecimalForInput } from "../../utils/decimalInput";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

type FormMode = "create" | "edit";

interface StammdatenGridProps<T extends { id: number }> {
  title: string;
  description?: string;
  /** Singular for form titles, e.g. "Material" → "Material anlegen/bearbeiten" */
  entityLabel: string;
  endpoint: string;
  /** Optional query string (ohne führendes ?), z. B. customer_id=1&program_id=2 */
  listQuery?: string;
  /** Optional toolbar content above the grid (Filter etc.) */
  toolbarExtra?: ReactNode;
  /** Called when the selected row id changes */
  onSelectedIdChange?: (id: number | null) => void;
  columnDefs: ColDef<T>[];
  formFields: FormField[];
  emptyFormValues: Omit<T, "id" | "created_at" | "updated_at">;
  /** Hinweisbanner im Formular (z. B. Werkparameter). */
  formBanner?: ReactNode;
  formMaxWidthClassName?: string;
  formFooterExtra?: ReactNode;
  /** Transformiert Payload vor POST/PUT (z. B. Typ-Coercion). */
  transformSubmitValues?: (
    values: Record<string, string | number | boolean>,
    mode: FormMode,
  ) => Record<string, unknown>;
  /** Mappt API-/Zeilenwerte auf Formularwerte (z. B. Anteil → UI-%). */
  transformLoadValues?: (
    values: Record<string, string | number | boolean>,
    mode: FormMode,
  ) => Record<string, string | number | boolean>;
  /** Zusätzliche Formularschlüssel aus Zeile/emptyFormValues (nicht in formFields). */
  additionalFormKeys?: string[];
  /** Zusätzlicher Inhalt im Formular (z. B. Hierarchie). */
  formExtraContent?: (
    values: Record<string, string | number | boolean>,
    onChange: (name: string, value: string | number | boolean) => void,
  ) => ReactNode;
  /** Wird bei jeder Formularänderung aufgerufen (z. B. Werk-Banner). */
  onFormValuesChange?: (values: Record<string, string | number | boolean>) => void;
  /** Mindesthöhe der Tabelle in Pixel */
  gridHeight?: number;
}

function formatFetchError(err: unknown, method: string, url: string): string {
  if (err instanceof NetworkError) {
    return err.message;
  }
  if (err instanceof TypeError) {
    return (
      `Netzwerkfehler bei ${method} ${url}. ` +
      "Backend unter http://127.0.0.1:8000 erreichbar?"
    );
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Unbekannter Fehler";
}

function rowToFormValues<T extends { id: number }>(
  row: T,
  fields: FormField[],
  extraKeys: string[] = [],
): Record<string, string | number | boolean> {
  const values: Record<string, string | number | boolean> = {};
  for (const field of fields) {
    const raw = (row as unknown as Record<string, unknown>)[field.name];
    if (field.type === "checkbox") {
      values[field.name] = Boolean(raw);
    } else if (field.type === "number") {
      if (raw == null || raw === "") {
        values[field.name] = "";
      } else {
        const num = typeof raw === "number" ? raw : Number(raw);
        values[field.name] = Number.isFinite(num) ? formatDecimalForInput(num) : "";
      }
    } else if (field.type === "date" && typeof raw === "string") {
      values[field.name] = raw.slice(0, 10);
    } else {
      values[field.name] = raw == null ? "" : String(raw);
    }
  }
  for (const key of extraKeys) {
    const raw = (row as unknown as Record<string, unknown>)[key];
    if (raw == null || raw === "") {
      values[key] = "";
    } else if (typeof raw === "number") {
      values[key] = raw;
    } else if (typeof raw === "boolean") {
      values[key] = raw;
    } else {
      values[key] = String(raw);
    }
  }
  return values;
}

export function StammdatenGrid<T extends { id: number }>({
  title,
  description,
  entityLabel,
  endpoint,
  listQuery = "",
  toolbarExtra,
  onSelectedIdChange,
  columnDefs,
  formFields,
  emptyFormValues,
  formBanner,
  formMaxWidthClassName,
  formFooterExtra,
  additionalFormKeys = [],
  formExtraContent,
  transformSubmitValues,
  transformLoadValues,
  onFormValuesChange,
  gridHeight = 560,
}: StammdatenGridProps<T>) {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<T[]>([]);
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
  const [formValues, setFormValues] = useState<Record<string, string | number | boolean>>({});

  const listPath = useMemo(() => {
    const q = listQuery.trim();
    return q ? `${endpoint}?${q}` : endpoint;
  }, [endpoint, listQuery]);

  const apiUrl = useMemo(() => `${getApiBaseUrl()}${listPath}`, [listPath]);

  const loadData = useCallback(
    async (options?: { initial?: boolean }) => {
      const isInitial = options?.initial === true;
      if (isInitial) {
        setInitialLoading(true);
      } else {
        setRefreshing(true);
      }

      try {
        setError(null);
        const data = await api.get<T[]>(listPath);
        const list = Array.isArray(data) ? data : [];
        setRows(list);
        return list;
      } catch (err) {
        setError(formatFetchError(err, "GET", apiUrl));
        throw err;
      } finally {
        if (isInitial) {
          setInitialLoading(false);
        } else {
          setRefreshing(false);
        }
      }
    },
    [apiUrl, listPath],
  );

  useEffect(() => {
    loadData({ initial: true }).catch(() => {
      // error already set in loadData
    });
  }, [loadData]);

  const openCreateForm = () => {
    setFormMode("create");
    setEditingId(null);
    const initial = { ...(emptyFormValues as Record<string, string | number | boolean>) };
    const mapped = transformLoadValues ? transformLoadValues(initial, "create") : initial;
    setFormValues(mapped);
    onFormValuesChange?.(mapped);
    setFormError(null);
    setSuccess(null);
    setShowForm(true);
  };

  const openEditForm = useCallback(
    (row: T) => {
      if (!canWrite) return;
      setFormMode("edit");
      setEditingId(row.id);
      setSelectedId(row.id);
      const values = rowToFormValues(row, formFields, additionalFormKeys);
      const mapped = transformLoadValues ? transformLoadValues(values, "edit") : values;
      setFormValues(mapped);
      onFormValuesChange?.(mapped);
      setFormError(null);
      setSuccess(null);
      setShowForm(true);
    },
    [canWrite, formFields, additionalFormKeys, onFormValuesChange, transformLoadValues],
  );

  const closeForm = () => {
    setShowForm(false);
    setFormError(null);
    setSubmitting(false);
    setEditingId(null);
    setFormMode("create");
    onFormValuesChange?.({});
  };

  const handleFormChange = (name: string, value: string | number | boolean) => {
    setFormValues((current) => {
      const next = { ...current, [name]: value };
      onFormValuesChange?.(next);
      return next;
    });
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setFormError(null);
    setError(null);
    setSuccess(null);
    try {
      const payload = transformSubmitValues
        ? transformSubmitValues(formValues, formMode)
        : formValues;
      if (formMode === "edit" && editingId != null) {
        await api.put<T>(`${endpoint}/${editingId}`, payload);
        setShowForm(false);
        setEditingId(null);
        setFormMode("create");
        setSuccess(`${entityLabel} erfolgreich aktualisiert.`);
      } else {
        await api.post<T>(endpoint, payload);
        setShowForm(false);
        setSuccess(`${entityLabel} erfolgreich angelegt.`);
      }

      try {
        await loadData();
      } catch {
        // Erfolg bleibt sichtbar; GET-Fehler steht in error
      }
    } catch (err) {
      const method = formMode === "edit" ? "PUT" : "POST";
      const url =
        formMode === "edit" && editingId != null
          ? `${getApiBaseUrl()}${endpoint}/${editingId}`
          : `${getApiBaseUrl()}${endpoint}`;
      setFormError(formatFetchError(err, method, url));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (selectedId === null) {
      setError("Bitte zuerst eine Zeile in der Tabelle auswählen.");
      return;
    }

    setError(null);
    setSuccess(null);
    try {
      await api.delete(`${endpoint}/${selectedId}`);
      setSelectedId(null);
      await loadData();
      setSuccess("Eintrag erfolgreich gelöscht.");
    } catch (err) {
      setError(
        formatFetchError(err, "DELETE", `${getApiBaseUrl()}${endpoint}/${selectedId}`),
      );
    }
  };

  const getRowId = useCallback((params: GetRowIdParams<T>) => String(params.data?.id ?? ""), []);

  const cols = useMemo(() => {
    const base = [...columnDefs];
    if (canWrite) {
      base.push({
        headerName: "Aktion",
        colId: "actions",
        width: 130,
        maxWidth: 140,
        pinned: "right",
        sortable: false,
        filter: false,
        resizable: false,
        cellRenderer: (params: ICellRendererParams<T>) => {
          if (!params.data) return null;
          return (
            <Button
              variant="secondary"
              size="sm"
              className="gap-1.5"
              onClick={(event) => {
                event.stopPropagation();
                openEditForm(params.data as T);
              }}
            >
              <PencilSimple className="size-3.5" weight="bold" aria-hidden />
              Bearbeiten
            </Button>
          );
        },
      } as ColDef<T>);
    }
    return base;
  }, [canWrite, columnDefs, openEditForm]);

  const formTitle =
    formMode === "edit" ? `${entityLabel} bearbeiten` : `${entityLabel} anlegen`;

  const meta = (
    <>
      {rows.length} {rows.length === 1 ? "Eintrag" : "Einträge"}
      {refreshing ? " · Aktualisiere…" : ""}
    </>
  );

  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        meta={meta}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                loadData().catch(() => undefined);
              }}
            >
              Aktualisieren
            </Button>
            {canWrite && (
              <>
                <Button onClick={openCreateForm}>
                  <Plus className="size-4" weight="bold" aria-hidden />
                  Neu
                </Button>
                <Button variant="danger" onClick={handleDelete}>
                  <Trash className="size-4" weight="bold" aria-hidden />
                  Ausgewählte löschen
                </Button>
              </>
            )}
          </>
        }
      />

      {toolbarExtra ? <div className="mb-4">{toolbarExtra}</div> : null}

      {error ? (
        <ValidationMessage variant="error" className="mb-4">
          {error}
        </ValidationMessage>
      ) : null}
      {success ? (
        <ValidationMessage variant="success" className="mb-4">
          {success}
        </ValidationMessage>
      ) : null}

      {initialLoading ? (
        <div className="app-card px-6 py-10 text-body-lg text-app-muted">Lade Daten…</div>
      ) : rows.length === 0 ? (
        <EmptyState
          title={`Keine ${title.toLowerCase()} vorhanden`}
          description={`Legen Sie den ersten Datensatz an, um ${entityLabel.toLowerCase()}-Stammdaten zu pflegen.`}
          action={
            canWrite ? (
              <Button onClick={openCreateForm}>
                <Plus className="size-4" weight="bold" aria-hidden />
                {entityLabel} anlegen
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="app-card overflow-hidden p-1">
          <div
            className="ag-theme-quartz ag-theme-kalkulation w-full"
            style={{ height: gridHeight, minWidth: 0 }}
          >
            <AgGridReact<T>
              rowData={rows}
              columnDefs={cols}
              getRowId={getRowId}
              rowSelection="single"
              onRowSelected={(event: RowSelectedEvent<T>) => {
                if (event.node.isSelected()) {
                  const id = event.data?.id ?? null;
                  setSelectedId(id);
                  onSelectedIdChange?.(id);
                }
              }}
              onRowDoubleClicked={(event: RowDoubleClickedEvent<T>) => {
                if (event.data) {
                  openEditForm(event.data);
                }
              }}
              defaultColDef={{
                flex: 1,
                minWidth: 120,
                sortable: true,
                filter: true,
                resizable: true,
              }}
              animateRows
              suppressCellFocus={false}
            />
          </div>
        </div>
      )}

      {showForm && (
        <StammdatenFormModal
          title={formTitle}
          fields={formFields}
          values={formValues}
          submitting={submitting}
          error={formError}
          banner={formBanner}
          maxWidthClassName={formMaxWidthClassName}
          footerExtra={formFooterExtra}
          extraContent={formExtraContent?.(formValues, handleFormChange)}
          onChange={handleFormChange}
          onClose={closeForm}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
