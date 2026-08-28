import type { ReactNode } from "react";

export type SelectOption = string | { value: string; label: string };
export { parseDecimalInput } from "../../utils/decimalInput";

export interface FormField {
  name: string;
  label: string;
  type: "text" | "number" | "date" | "checkbox" | "select";
  required?: boolean;
  options?: SelectOption[];
  step?: string;
  /** Schreibgeschützt (z. B. berechneter Stundensatz). */
  readOnly?: boolean;
  hint?: string;
}

function optionValue(option: SelectOption): string {
  return typeof option === "string" ? option : option.value;
}

function optionLabel(option: SelectOption): string {
  return typeof option === "string" ? option : option.label;
}

export function StammdatenFormModal({
  title,
  fields,
  values,
  submitting,
  error,
  banner,
  maxWidthClassName = "max-w-lg",
  onChange,
  onClose,
  onSubmit,
  footerExtra,
  extraContent,
}: {
  title: string;
  fields: FormField[];
  values: Record<string, string | number | boolean>;
  submitting: boolean;
  error: string | null;
  /** Optionaler Hinweis über den Feldern (z. B. Werkparameter). */
  banner?: ReactNode;
  maxWidthClassName?: string;
  onChange: (name: string, value: string | number | boolean) => void;
  onClose: () => void;
  onSubmit: () => void;
  footerExtra?: ReactNode;
  extraContent?: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-2 sm:p-4">
      <div
        className={`flex w-full ${maxWidthClassName} max-h-[min(92dvh,920px)] flex-col overflow-hidden rounded-xl bg-white shadow-xl`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="stammdaten-form-title"
      >
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-gray-100 px-4 py-3 sm:px-6">
          <h3 id="stammdaten-form-title" className="text-lg font-semibold text-gray-900">
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Schließen"
          >
            ✕
          </button>
        </header>

        {error && (
          <div className="shrink-0 border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700 sm:px-6">
            {error}
          </div>
        )}

        {banner && (
          <div className="shrink-0 border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm text-slate-700 sm:px-6">
            {banner}
          </div>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3 sm:px-6">
            <div className="space-y-4 pb-2">
              {fields.map((field) => (
                <div key={field.name}>
                  <label
                    htmlFor={field.name}
                    className="block text-sm font-medium text-gray-700"
                  >
                    {field.label}
                    {field.readOnly ? (
                      <span className="ml-2 text-xs font-normal text-gray-500">
                        (berechnet, nicht editierbar)
                      </span>
                    ) : null}
                  </label>
                  {field.type === "checkbox" ? (
                    <input
                      id={field.name}
                      type="checkbox"
                      checked={Boolean(values[field.name])}
                      disabled={field.readOnly}
                      onChange={(event) => onChange(field.name, event.target.checked)}
                      className="mt-2 h-4 w-4 rounded border-gray-300"
                    />
                  ) : field.type === "select" ? (
                    <select
                      id={field.name}
                      required={field.required}
                      disabled={field.readOnly}
                      value={String(values[field.name] ?? "")}
                      onChange={(event) => {
                        const raw = event.target.value;
                        if (field.name.endsWith("_id") || field.name === "werk_id") {
                          onChange(field.name, raw === "" ? "" : Number(raw));
                        } else {
                          onChange(field.name, raw);
                        }
                      }}
                      className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50"
                    >
                      {(field.options ?? []).map((option) => (
                        <option key={optionValue(option)} value={optionValue(option)}>
                          {optionLabel(option)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={field.name}
                      type={field.type === "number" ? "text" : field.type}
                      inputMode={field.type === "number" ? "decimal" : undefined}
                      autoComplete="off"
                      required={field.required && !field.readOnly}
                      readOnly={field.readOnly}
                      // Rohstring behalten: sofortiges Number()-Parsing verschluckt „0,“ / „0.“
                      value={
                        field.type === "number"
                          ? values[field.name] === "" || values[field.name] == null
                            ? ""
                            : String(values[field.name])
                          : String(values[field.name] ?? "")
                      }
                      onChange={(event) => {
                        const raw = event.target.value;
                        if (field.type === "number") {
                          // Kein Live-Parse zu number – Submit/Transform übernimmt parseDecimalInput
                          onChange(field.name, raw);
                          return;
                        }
                        onChange(field.name, raw);
                      }}
                      className={`mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm ${
                        field.readOnly ? "bg-slate-50 text-slate-700" : ""
                      }`}
                    />
                  )}
                  {field.hint ? (
                    <p className="mt-1 text-xs text-gray-500">{field.hint}</p>
                  ) : null}
                </div>
              ))}
              {extraContent}
            </div>
          </div>

          <footer className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-gray-100 bg-white px-4 py-3 sm:px-6">
            {footerExtra}
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
          </footer>
        </form>
      </div>
    </div>
  );
}
