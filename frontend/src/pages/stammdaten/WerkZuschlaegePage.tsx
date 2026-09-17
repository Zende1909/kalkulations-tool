import type { ColDef } from "ag-grid-community";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { StammdatenGrid } from "../../components/stammdaten/StammdatenGrid";
import { useT } from "../../i18n";
import type { FormField } from "../../components/stammdaten/StammdatenFormModal";
import type { Werk, WerkZuschlag } from "../../types/stammdaten";
import {
  loadWerkZuschlagFormValues,
  submitWerkZuschlagFormValues,
} from "../../utils/werkZuschlagFormDecimals";

export function WerkZuschlaegePage() {
  const t = useT();
  const [werke, setWerke] = useState<Werk[]>([]);
  const [werkId, setWerkId] = useState<number | "">("");

  useEffect(() => {
    api.get<Werk[]>("/werke").then((rows) => {
      setWerke(rows.filter((w) => w.aktiv));
      if (rows.length > 0) setWerkId(rows[0].id);
    });
  }, []);

  const columnDefs = useMemo(
    (): ColDef<WerkZuschlag>[] => [
      { field: "typ", headerName: t("masterData.type") },
      { field: "bezeichnung", headerName: t("masterData.designation") },
      { field: "satz_prozent", headerName: t("masterData.ratePercentShort") },
      { field: "kostenbasis", headerName: t("masterData.costBase") },
      { field: "aktiv", headerName: t("common.active") },
    ],
    [t],
  );

  const formFields = useMemo(
    (): FormField[] => [
      { name: "typ", label: t("masterData.type"), type: "text", required: true },
      { name: "bezeichnung", label: t("masterData.designation"), type: "text", required: true },
      {
        name: "satz_prozent",
        label: t("masterData.ratePercent"),
        type: "number",
        required: true,
        step: "0.01",
      },
      { name: "kostenbasis", label: t("masterData.costBase"), type: "text", required: true },
      { name: "aktiv", label: t("common.active"), type: "checkbox" },
    ],
    [t],
  );

  if (werkId === "") {
    return <p className="text-sm text-gray-600">{t("masterData.loadingPlants")}</p>;
  }

  return (
    <div className="space-y-3">
      <label className="block max-w-md text-sm">
        <span className="font-medium text-gray-700">{t("masterData.plant")}</span>
        <select
          value={werkId}
          onChange={(e) => setWerkId(Number(e.target.value))}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
        >
          {werke.map((w) => (
            <option key={w.id} value={w.id}>
              {w.code} – {w.name}
            </option>
          ))}
        </select>
      </label>
      <StammdatenGrid<WerkZuschlag>
        key={werkId}
        title={t("nav.plantMarkups")}
        description={t("pages.plantMarkupsDesc")}
        entityLabel={t("masterData.plantMarkup")}
        endpoint={`/werke/${werkId}/zuschlaege`}
        columnDefs={columnDefs}
        formFields={formFields}
        emptyFormValues={{
          werk_id: Number(werkId),
          typ: "handling_oem_kaufteil",
          bezeichnung: "",
          satz_prozent: 0,
          kostenbasis: "einkaufspreis",
          aktiv: true,
        }}
        transformLoadValues={(values) => loadWerkZuschlagFormValues(values)}
        transformSubmitValues={(values) => submitWerkZuschlagFormValues(values)}
      />
    </div>
  );
}
