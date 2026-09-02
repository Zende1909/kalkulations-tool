import type { ReactNode } from "react";

import { Button } from "../ui/Button";
import { ValidationMessage } from "../ui/ValidationMessage";
import { parseDecimalInput } from "../../utils/decimalInput";

export type SelectOption = string | { value: string; label: string };
export { parseDecimalInput };

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-2 sm:p-4">
      <div
        className={`flex w-full ${maxWidthClassName} max-h-[min(92dvh,920px)] flex-col overflow-hidden rounded-app bg-white shadow-modal`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="stammdaten-form-title"
      >
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-app-border px-5 py-4">
          <h3 id="stammdaten-form-title" className="text-section-title text-app-heading">
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-app p-2 text-app-muted transition-colors hover:bg-slate-100 hover:text-app-heading"
            aria-label="Schließen"
          >
            ✕
          </button>
        </header>

        {error ? (
          <ValidationMessage variant="error" className="mx-5 mt-4 shrink-0 rounded-app">
            {error}
          </ValidationMessage>
        ) : null}

        {banner ? (
          <div className="shrink-0 border-b border-app-border bg-slate-50 px-5 py-3 text-body-lg text-app-body">
            {banner}
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">
            <div className="space-y-5 pb-2">
              {fields.map((field) => (
                <div key={field.name}>
                  {field.type === "checkbox" ? (
                    <label htmlFor={field.name} className="flex items-start gap-3">
                      <input
                        id={field.name}
                        type="checkbox"
                        checked={Boolean(values[field.name])}
                        disabled={field.readOnly}
                        onChange={(event) => onChange(field.name, event.target.checked)}
                        className="mt-1 size-4 rounded border-app-border-strong text-brand focus:ring-brand"
                      />
                      <span>
                        <span className="block text-body-lg font-medium text-app-heading">
                          {field.label}
                        </span>
                        {field.hint ? (
                          <span className="mt-1 block text-sm text-app-muted">{field.hint}</span>
                        ) : null}
                      </span>
                    </label>
                  ) : (
                    <>
                      <label htmlFor={field.name} className="block text-body-lg font-medium text-app-heading">
                        {field.label}
                        {field.readOnly ? (
                          <span className="ml-2 text-sm font-normal text-app-muted">
                            (berechnet, nicht editierbar)
                          </span>
                        ) : null}
                      </label>
                      {field.type === "select" ? (
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
                          className="app-input"
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
                          className={`app-input ${field.readOnly ? "bg-slate-50 text-app-muted" : ""}`}
                        />
                      )}
                      {field.hint ? (
                        <p className="mt-1.5 text-sm text-app-muted">{field.hint}</p>
                      ) : null}
                    </>
                  )}
                </div>
              ))}
              {extraContent}
            </div>
          </div>

          <footer className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-app-border bg-slate-50 px-5 py-4">
            {footerExtra}
            <Button variant="secondary" onClick={onClose}>
              Abbrechen
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Speichern…" : "Speichern"}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}
