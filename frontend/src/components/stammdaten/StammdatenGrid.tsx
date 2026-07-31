import { useCallback, useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef } from "ag-grid-community";

import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

interface StammdatenGridProps<T extends { id: number }> {
  title: string;
  endpoint: string;
  columnDefs: ColDef<T>[];
  defaultRow: Omit<T, "id" | "created_at" | "updated_at">;
}

export function StammdatenGrid<T extends { id: number }>({
  title,
  endpoint,
  columnDefs,
  defaultRow,
}: StammdatenGridProps<T>) {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<T[]>(endpoint);
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Daten konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAdd = async () => {
    try {
      await api.post<T>(endpoint, defaultRow);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eintrag konnte nicht erstellt werden");
    }
  };

  const handleDelete = async () => {
    const selected = rows[0];
    if (!selected) return;
    try {
      await api.delete(`${endpoint}/${selected.id}`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eintrag konnte nicht gelöscht werden");
    }
  };

  const cols = useMemo(() => columnDefs, [columnDefs]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
        {canWrite && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleAdd}
              className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Neu
            </button>
            <button
              type="button"
              onClick={handleDelete}
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
            >
              Ersten Eintrag löschen
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <p className="text-gray-600">Lade Daten...</p>
      ) : (
        <div className="ag-theme-quartz" style={{ height: 500, width: "100%" }}>
          <AgGridReact<T>
            rowData={rows}
            columnDefs={cols}
            defaultColDef={{ flex: 1, minWidth: 120, sortable: true, filter: true }}
            animateRows
          />
        </div>
      )}
    </div>
  );
}
