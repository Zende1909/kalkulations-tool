interface ExportButtonsProps {
  onPdf: () => void;
  onExcel: () => void;
  busy?: boolean;
  disabled?: boolean;
}

export function ExportButtons({ onPdf, onExcel, busy = false, disabled = false }: ExportButtonsProps) {
  const isDisabled = disabled || busy;
  return (
    <>
      <button
        type="button"
        disabled={isDisabled}
        onClick={onPdf}
        className="rounded-md border border-slate-400 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
      >
        {busy ? "Export …" : "PDF exportieren"}
      </button>
      <button
        type="button"
        disabled={isDisabled}
        onClick={onExcel}
        className="rounded-md border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50"
      >
        {busy ? "Export …" : "Excel exportieren"}
      </button>
    </>
  );
}
