import { Button } from "./ui/Button";

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

  return (
    <>
      <Button
        variant="secondary"
        size={compact ? "sm" : "md"}
        disabled={isDisabled}
        onClick={onPdf}
      >
        {pdfLabel}
      </Button>
      <Button
        variant="success"
        size={compact ? "sm" : "md"}
        disabled={isDisabled}
        onClick={onExcel}
      >
        {xlsxLabel}
      </Button>
    </>
  );
}
