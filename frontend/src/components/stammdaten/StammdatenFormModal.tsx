export interface FormField {
  name: string;
  label: string;
  type: "text" | "number" | "date" | "checkbox" | "select";
  required?: boolean;
  options?: string[];
  step?: string;
}

export function StammdatenFormModal({
  title,
  fields,
  values,
  submitting,
  error,
  onChange,
  onClose,
  onSubmit,
}: {
  title: string;
  fields: FormField[];
  values: Record<string, string | number | boolean>;
  submitting: boolean;
  error: string | null;
  onChange: (name: string, value: string | number | boolean) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Schließen"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="space-y-4"
        >
          {fields.map((field) => (
            <div key={field.name}>
              <label htmlFor={field.name} className="block text-sm font-medium text-gray-700">
                {field.label}
              </label>
              {field.type === "checkbox" ? (
                <input
                  id={field.name}
                  type="checkbox"
                  checked={Boolean(values[field.name])}
                  onChange={(event) => onChange(field.name, event.target.checked)}
                  className="mt-2 h-4 w-4 rounded border-gray-300"
                />
              ) : field.type === "select" ? (
                <select
                  id={field.name}
                  required={field.required}
                  value={String(values[field.name] ?? "")}
                  onChange={(event) => onChange(field.name, event.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  {(field.options ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={field.name}
                  type={field.type}
                  required={field.required}
                  step={field.step}
                  value={String(values[field.name] ?? "")}
                  onChange={(event) =>
                    onChange(
                      field.name,
                      field.type === "number" ? Number(event.target.value) : event.target.value,
                    )
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              )}
            </div>
          ))}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {submitting ? "Speichern..." : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
