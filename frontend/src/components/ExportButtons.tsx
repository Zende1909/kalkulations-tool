import { Button } from "./ui/Button";
import { useT } from "../i18n";

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
  const t = useT();
  const isDisabled = disabled || busy;
  const pdfLabel = compact ? t("export.pdf") : busy ? t("export.exporting") : t("export.pdfExport");
  const xlsxLabel = compact
    ? t("export.excel")
    : busy
      ? t("export.exporting")
      : t("export.excelExport");

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
