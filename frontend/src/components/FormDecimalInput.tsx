import { DecimalInputField } from "./DecimalInputField";
import { formatDecimalForInputDe } from "../utils/decimalInput";

/** Dezimal-Eingabe mit Rohstring-State (Submit-Parsing erfolgt im Formular). */
export function FormDecimalInput({
  fieldKey,
  label,
  value,
  decimalRaw,
  onDecimalChange,
  className,
}: {
  fieldKey: string;
  label: string;
  value: number | null | undefined;
  decimalRaw: Record<string, string>;
  onDecimalChange: (fieldKey: string, raw: string) => void;
  className?: string;
}) {
  const raw =
    fieldKey in decimalRaw
      ? decimalRaw[fieldKey]
      : formatDecimalForInputDe(value ?? "");
  return (
    <DecimalInputField
      label={label}
      rawValue={raw}
      onRawChange={(next) => onDecimalChange(fieldKey, next)}
      className={className}
    />
  );
}

/** Kompakte Inline-Variante für Tabellen/Zeilen. */
export function InlineDecimalInput({
  fieldKey,
  value,
  decimalRaw,
  onDecimalChange,
  className = "w-24 rounded border px-1 py-0.5",
}: {
  fieldKey: string;
  value: number;
  decimalRaw: Record<string, string>;
  onDecimalChange: (fieldKey: string, raw: string) => void;
  className?: string;
}) {
  const raw =
    fieldKey in decimalRaw
      ? decimalRaw[fieldKey]
      : formatDecimalForInputDe(value);
  return (
    <input
      type="text"
      inputMode="decimal"
      autoComplete="off"
      className={className}
      value={raw}
      onChange={(event) => onDecimalChange(fieldKey, event.target.value)}
    />
  );
}
