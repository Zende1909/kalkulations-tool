import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";

import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Land } from "../../types/stammdaten";

export function LaenderPage() {
  const t = useT();

  const columnDefs = useMemo(
    (): ColDef<Land>[] => [
      { field: "code", headerName: t("masterData.code") },
      { field: "name", headerName: t("masterData.name") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "code", label: t("masterData.code"), type: "text", required: true },
      { name: "name", label: t("masterData.name"), type: "text", required: true },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  return (
    <StammdatenGrid<Land>
      title={t("nav.countries")}
      description={t("pages.countriesDesc")}
      entityLabel={t("masterData.country")}
      endpoint="/laender"
      columnDefs={columnDefs}
      formFields={formFields}
      emptyFormValues={{ code: "", name: "", aktiv: true }}
    />
  );
}
