interface ExportButtonsProps {
  onPdf: () => void;
  onExcel: () => void;
  busy?: boolean;
  disabled?: boolean;
  compact?: boolean;
}

export function ExportButtons({
  onPdf,
  onExcel,
  busy = false,
  disabled = false,
  compact = false,
}: ExportButtonsProps) {
  const isDisabled = disabled || busy;
  const pdfLabel = compact ? "PDF" : busy ? "Export …" : "PDF exportieren";
  const xlsxLabel = compact ? "Excel" : busy ? "Export …" : "Excel exportieren";
  const pad = compact ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";
  return (
    <>
      <button
        type="button"
        disabled={isDisabled}
        onClick={onPdf}
        className={`rounded-md border border-slate-400 ${pad} font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50`}
      >
        {pdfLabel}
      </button>
      <button
        type="button"
        disabled={isDisabled}
        onClick={onExcel}
        className={`rounded-md border border-emerald-600 ${pad} font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50`}
      >
        {xlsxLabel}
      </button>
    </>
  );
}
