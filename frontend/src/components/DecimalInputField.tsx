/** Dezimal-Eingabe mit Rohstring – Zwischenstände wie „1,“ bleiben erhalten. */
export function DecimalInputField({
  label,
  rawValue,
  onRawChange,
  required = false,
  className = "mt-1 w-full rounded-md border border-gray-300 px-3 py-2",
}: {
  label: string;
  rawValue: string;
  onRawChange: (raw: string) => void;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      <input
        type="text"
        inputMode="decimal"
        autoComplete="off"
        required={required}
        value={rawValue}
        onChange={(event) => onRawChange(event.target.value)}
        className={className}
      />
    </label>
  );
}
