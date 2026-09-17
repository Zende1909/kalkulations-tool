import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import {
  berechnen,
  berechneMaschinenGroesse,
  berechneZykluszeit,
  createKalkulation,
  deleteKalkulation,
  getKalkulation,
  updateKalkulation,
} from "../api/spritzguss";
import {
  downloadReport,
  spritzgussPdfUrl,
  spritzgussXlsxUrl,
} from "../api/reports";
import { listVeredelungsschritte } from "../api/veredelung";
import { getAverageJahresstueckzahl, getProgram } from "../api/hierarchy";
import { ExportButtons } from "../components/ExportButtons";
import { SpritzgussSavedList } from "../components/spritzguss/SpritzgussSavedList";
import { TeilbildField } from "../components/spritzguss/TeilbildField";
import {
  HierarchySelector,
  type HierarchySelection,
} from "../components/hierarchy/HierarchySelector";
import { useAuth } from "../context/AuthContext";
import { useActiveProject } from "../context/ActiveProjectContext";
import { useT } from "../i18n";
import {
  DETAIL_BLOCK_ORDER,
  ERGEBNISUEBERSICHT_DEF,
  blockLabel,
  entnahmeDesc,
  entnahmeLabel,
  fieldLabel,
  sizeClassLabel,
  veredelungDetailLabel,
} from "../i18n/spritzgussLabels";
import type { Lohnkosten, Land, Maschine, Material, Werk } from "../types/stammdaten";
import type { Veredelungsschritt } from "../types/veredelung";
import {
  emptySpritzgussForm,
  entnahmeartNormalisiert,
  ZYKLUSZEIT_DEFAULT_GROESSENKLASSE,
  ZYKLUSZEIT_ENTNAHMEARTEN,
  ZYKLUSZEIT_GROESSENKLASSE_AUTO,
  ZYKLUSZEIT_GROESSENKLASSEN,
  ZYKLUSZEIT_PROZESSAUFWAND_ZUSCHLAG_S,
  type SpritzgussBloecke,
  type SpritzgussFormData,
  type MaschinenGroesseResult,
  type VeredelungZuordnung,
  type VeredelungZuordnungInput,
  type WerkzeugAbrechnungsart,
  type ZykluszeitEntnahmeart,
  type ZykluszeitGroessenklasse,
  type ZykluszeitProzessaufwand,
  type ZykluszeitVorschlag,
} from "../types/spritzguss";
import { FormDecimalInput } from "../components/FormDecimalInput";
import {
  formatPercentPoints,
  PercentPointsParseError,
  formatDecimalForInputDe,
} from "../utils/decimalInput";
import {
  loadSpritzgussDecimalRaw,
  parseSpritzgussDecimalFields,
} from "../utils/spritzgussFormDecimals";
import {
  buildMaschinenGroessePreviewPayload,
  readKavitaeten,
} from "../utils/maschinenGroessePreview";
import { buildZykluszeitPreviewPayload } from "../utils/zykluszeitPreview";
import {
  berechneAutomatischeLosgroesse,
  inferLegacyLosgroesseModus,
  werkProduktionsintervall,
} from "../utils/losgroesseBerechnung";
import { teilbildSrc } from "../utils/teilbild";

interface SelectedVeredelung extends VeredelungZuordnungInput {
  bezeichnung: string;
  veredelungsart: string;
  kosten_inkl_ausschuss: number;
  kosten_gesamt?: number;
}

function gespeicherteGroessenklasse(wert: unknown): ZykluszeitGroessenklasse {
  if (wert === ZYKLUSZEIT_GROESSENKLASSE_AUTO) return ZYKLUSZEIT_GROESSENKLASSE_AUTO;
  return ZYKLUSZEIT_GROESSENKLASSEN.some((k) => k.key === wert)
    ? (wert as ZykluszeitGroessenklasse)
    : ZYKLUSZEIT_DEFAULT_GROESSENKLASSE;
}

function formatSekunden(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Ganze Sekunden ohne Nachkommastellen, sonst zwei Nachkommastellen. */
function formatZykluszeitFeld(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "–";
  return formatSekunden(value, Number.isInteger(value) ? 0 : 2);
}

function euro(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const PCT_DETAIL_FIELDS = new Set([
  "mgk_pct",
  "fgk_pct",
  "vvgk_pct",
  "gewinn_pct",
  "skonto_pct",
  "ausschussquote_pct",
  "applied_mgk_pct",
  "applied_fgk_pct",
  "applied_vvgk_pct",
  "applied_gewinn_pct",
  "applied_skonto_pct",
]);

function formatDetailValue(field: string, value: unknown): string {
  if (typeof value === "string") return value || "–";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return "–";
  if (PCT_DETAIL_FIELDS.has(field) || field.endsWith("_pct")) {
    return formatPercentPoints(num, 4);
  }
  return euro(num);
}

/** @deprecated labels live in spritzgussLabels; kept name for UI-test key order scans */
const ERGEBNISUEBERSICHT = ERGEBNISUEBERSICHT_DEF;

function ergebnisUebersichtRowClass(emphasis?: "primary" | "secondary"): string {
  if (emphasis === "primary") {
    return "border-slate-400 bg-white px-2 -mx-2 rounded-md font-semibold shadow-sm ring-1 ring-slate-200";
  }
  if (emphasis === "secondary") {
    return "border-slate-200 bg-slate-50/80 px-2 -mx-2 rounded font-medium";
  }
  return "border-gray-100";
}

function ergebnisUebersichtLabelClass(emphasis?: "primary" | "secondary"): string {
  if (emphasis === "primary") return "text-slate-900 font-semibold";
  if (emphasis === "secondary") return "text-slate-800 font-medium";
  return "text-gray-600";
}

function ergebnisUebersichtValueClass(emphasis?: "primary" | "secondary"): string {
  if (emphasis === "primary") return "text-lg font-bold tabular-nums text-slate-900";
  if (emphasis === "secondary") return "text-base font-semibold tabular-nums text-slate-900";
  return "font-medium tabular-nums text-gray-900";
}

function NumberInput({
  label,
  fieldKey,
  value,
  decimalRaw,
  onDecimalChange,
}: {
  label: string;
  fieldKey: string;
  value: number;
  decimalRaw: Record<string, string>;
  onDecimalChange: (fieldKey: string, raw: string) => void;
}) {
  return (
    <FormDecimalInput
      fieldKey={fieldKey}
      label={label}
      value={value}
      decimalRaw={decimalRaw}
      onDecimalChange={onDecimalChange}
    />
  );
}

function TextInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
      />
    </label>
  );
}

function isSpritzgussMachine(machine: Maschine): boolean {
  const typ = (machine.maschinentyp ?? "").toLowerCase();
  return !["montage", "veredelung", "assembly", "finish", "finishing"].some((token) =>
    typ.includes(token),
  );
}

function formatSizingNumber(value: number | null | undefined, fractionDigits = 6): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  });
}

export function SpritzgussPage() {
  const t = useT();
  const { canWrite } = useAuth();
  const { selection, formDefaults } = useActiveProject();
  const [form, setForm] = useState<SpritzgussFormData>(emptySpritzgussForm());
  const [decimalRaw, setDecimalRaw] = useState<Record<string, string>>(() =>
    loadSpritzgussDecimalRaw(emptySpritzgussForm()),
  );
  const [hierarchy, setHierarchy] = useState<HierarchySelection>(() => formDefaults());
  const [legacyHierarchy, setLegacyHierarchy] = useState<{
    kunde: string;
    projekt: string;
    jahresstueckzahl: number;
    calculation_year?: number | null;
  } | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [bloecke, setBloecke] = useState<SpritzgussBloecke | null>(null);
  const [savedListRefreshKey, setSavedListRefreshKey] = useState(0);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [machines, setMachines] = useState<Maschine[]>([]);
  const [lohns, setLohns] = useState<Lohnkosten[]>([]);
  const [laender, setLaender] = useState<Land[]>([]);
  const [werke, setWerke] = useState<Werk[]>([]);
  const [selectedLandId, setSelectedLandId] = useState<number | null>(null);
  const [veredelungPool, setVeredelungPool] = useState<Veredelungsschritt[]>([]);
  const [selectedVeredelung, setSelectedVeredelung] = useState<SelectedVeredelung[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [jahresbedarf, setJahresbedarf] = useState<number | null>(null);
  const [jahresbedarfHint, setJahresbedarfHint] = useState<string | null>(null);
  const [jahresbedarfLoading, setJahresbedarfLoading] = useState(false);
  const [maschinenGroesse, setMaschinenGroesse] = useState<MaschinenGroesseResult | null>(null);
  const [maschineManuell, setMaschineManuell] = useState(false);
  const [zykluszeitVorschlag, setZykluszeitVorschlag] = useState<ZykluszeitVorschlag | null>(
    null,
  );

  // Globales aktives Projekt auf neue Formulare übernehmen (geladenen Datensatz nicht überschreiben)
  useEffect(() => {
    if (editId != null) return;
    setHierarchy({
      customer_id: selection.customer_id,
      program_id: selection.program_id,
      project_id: selection.project_id,
    });
  }, [selection.customer_id, selection.program_id, selection.project_id, editId]);

  const setField = <K extends keyof SpritzgussFormData>(key: K, value: SpritzgussFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const handleDecimalChange = (fieldKey: string, raw: string) => {
    setDecimalRaw((current) => ({ ...current, [fieldKey]: raw }));
    if (fieldKey === "kavitaeten") {
      const parsed = readKavitaeten({ kavitaeten: raw }, form.kavitaeten);
      if (raw.trim() === "" || parsed >= 1) {
        setForm((current) => ({ ...current, kavitaeten: parsed }));
      }
    }
    if (fieldKey === "zykluszeit_s") {
      setForm((current) => ({ ...current, zykluszeit_quelle: "manuell" }));
    }
  };

  const resolveParsedForm = (): SpritzgussFormData =>
    parseSpritzgussDecimalFields(decimalRaw, form);

  const loadStammdaten = useCallback(async () => {
    const [mats, masch, lohn, veredelung, lands, plants] = await Promise.all([
      api.get<Material[]>("/materialien"),
      api.get<Maschine[]>("/maschinen"),
      api.get<Lohnkosten[]>("/lohnkosten"),
      listVeredelungsschritte(),
      api.get<Land[]>("/laender"),
      api.get<Werk[]>("/werke"),
    ]);
    setMaterials(mats.filter((m) => m.aktiv));
    setMachines(masch.filter((m) => m.aktiv));
    setLohns(lohn.filter((l) => l.aktiv));
    setVeredelungPool(veredelung.filter((v) => v.aktiv));
    setLaender(lands.filter((l) => l.aktiv));
    setWerke(plants.filter((w) => w.aktiv));
  }, []);

  useEffect(() => {
    loadStammdaten().catch((err) => {
      setError(err instanceof Error ? err.message : t("spritzguss.masterDataLoadFailed"));
    });
  }, [loadStammdaten, t]);

  const veredelungZuordnungen = useMemo<VeredelungZuordnungInput[]>(
    () =>
      selectedVeredelung.map((s) => ({
        veredelungsschritt_id: s.veredelungsschritt_id,
        reihenfolge: s.reihenfolge,
        aktiv: s.aktiv,
        mengenfaktor: s.mengenfaktor,
      })),
    [selectedVeredelung],
  );

  useEffect(() => {
    let cancelled = false;
    const projectId = hierarchy.project_id ?? form.project_id;
    if (projectId == null) {
      setJahresbedarf(null);
      setJahresbedarfHint(
        hierarchy.customer_id != null || hierarchy.program_id != null
          ? t("spritzguss.annualDemandAfterProject")
          : null,
      );
      setJahresbedarfLoading(false);
      return;
    }
    setJahresbedarfLoading(true);
    setJahresbedarfHint(null);
    getAverageJahresstueckzahl(projectId)
      .then((avg) => {
        if (cancelled) return;
        if (!avg.has_volumes || avg.jahresstueckzahl == null) {
          setJahresbedarf(null);
          setJahresbedarfHint(
            t("spritzguss.annualDemandMissing"),
          );
          return;
        }
        setJahresbedarf(avg.jahresstueckzahl);
        setJahresbedarfHint(
          t("spritzguss.annualDemandSummary", {
            years: avg.year_count,
            pieces: avg.jahresstueckzahl.toLocaleString("de-DE"),
          }),
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setJahresbedarf(null);
          setJahresbedarfHint(
            err instanceof Error ? err.message : t("spritzguss.annualDemandLoadFailed"),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setJahresbedarfLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hierarchy.project_id, hierarchy.customer_id, hierarchy.program_id, form.project_id, t]);

  const selectedWerk = useMemo(
    () => werke.find((w) => w.id === form.werk_id) ?? null,
    [werke, form.werk_id],
  );

  const losgroessePreview = useMemo(() => {
    const arbeitstage = selectedWerk?.arbeitstage_pro_jahr ?? null;
    const intervall = werkProduktionsintervall(selectedWerk);
    const auto =
      jahresbedarf != null && arbeitstage != null
        ? berechneAutomatischeLosgroesse(jahresbedarf, intervall, arbeitstage)
        : null;
    if (form.losgroesse_modus === "manuell") {
      return {
        auto,
        aktiv: form.losgroesse_manuell,
        quelle: "manuell" as const,
        intervall,
        arbeitstage,
      };
    }
    return {
      auto,
      aktiv: auto,
      quelle: "automatisch" as const,
      intervall,
      arbeitstage,
    };
  }, [selectedWerk, jahresbedarf, form.losgroesse_modus, form.losgroesse_manuell]);

  const effectiveKavitaeten = useMemo(
    () => readKavitaeten(decimalRaw, form.kavitaeten),
    [decimalRaw, form.kavitaeten],
  );

  const maschinenGroessePreviewPayload = useMemo(
    () => buildMaschinenGroessePreviewPayload(form, decimalRaw),
    [form, decimalRaw],
  );

  useEffect(() => {
    if (maschinenGroessePreviewPayload == null) {
      setMaschinenGroesse(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      berechneMaschinenGroesse(maschinenGroessePreviewPayload)
        .then((result) => {
          if (!cancelled) setMaschinenGroesse(result);
        })
        .catch(() => {
          if (!cancelled) setMaschinenGroesse(null);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [maschinenGroessePreviewPayload]);

  const zuhaltekraftT = maschinenGroesse?.zuhaltekraft_erforderlich_t ?? null;

  /** Ersatzwert, wenn keine erforderliche Zuhaltekraft berechnet werden kann. */
  const maschinenZuhaltekraftT = useMemo(() => {
    const maschine = machines.find((m) => m.id === form.maschine_id);
    const kraft = maschine?.schliesskraft_t ?? null;
    return kraft != null && Number.isFinite(kraft) && kraft > 0 ? kraft : null;
  }, [machines, form.maschine_id]);

  const zykluszeitPreviewPayload = useMemo(
    () =>
      buildZykluszeitPreviewPayload(form, decimalRaw, zuhaltekraftT, maschinenZuhaltekraftT),
    [form, decimalRaw, zuhaltekraftT, maschinenZuhaltekraftT],
  );

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      berechneZykluszeit(zykluszeitPreviewPayload)
        .then((result) => {
          if (!cancelled) setZykluszeitVorschlag(result);
        })
        .catch(() => {
          if (!cancelled) setZykluszeitVorschlag(null);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [zykluszeitPreviewPayload]);

  const uebernehmeZykluszeit = () => {
    if (!zykluszeitVorschlag?.kann_uebernommen_werden) return;
    // `gesamtzykluszeit_s` ist bereits auf eine volle Sekunde gerundet.
    const wert = zykluszeitVorschlag.gesamtzykluszeit_s;
    if (wert == null || !Number.isFinite(wert)) return;
    setForm((current) => ({ ...current, zykluszeit_s: wert, zykluszeit_quelle: "vorschlag" }));
    setDecimalRaw((current) => ({
      ...current,
      zykluszeit_s: formatDecimalForInputDe(wert),
    }));
    setSuccess(
      t("spritzguss.cycleTimeApplied", { seconds: formatSekunden(wert, 0) }),
    );
  };

  const selectedMaterial = useMemo(
    () => materials.find((m) => m.id === form.material_id) ?? null,
    [materials, form.material_id],
  );

  const calcPayloadBase = useMemo(
    () => ({
      teilegewicht_netto_g: form.teilegewicht_netto_g,
      schussgewicht_g: form.schussgewicht_g,
      materialpreis_pro_kg: form.materialpreis_pro_kg,
      material_id: form.material_id,
      mgk_pct: form.mgk_pct,
      material_nominierung: form.material_nominierung,
      zykluszeit_s: form.zykluszeit_s,
      maschinenstundensatz: form.maschinenstundensatz,
      kavitaeten: form.kavitaeten,
      lohnstundensatz: form.lohnstundensatz,
      fgk_pct: form.fgk_pct,
      werkzeugkosten_eur: 0,
      werkzeug_abrechnungsart: "einmalzahlung" as const,
      amortisationsvolumen: null,
      vvgk_pct: form.vvgk_pct,
      gewinn_pct: form.gewinn_pct,
      skonto_pct: form.skonto_pct,
      veredelung_zuordnungen: veredelungZuordnungen,
      werk_id: form.werk_id,
      project_id: hierarchy.project_id ?? form.project_id,
      losgroesse_modus: form.losgroesse_modus,
      losgroesse_manuell:
        form.losgroesse_modus === "manuell" ? form.losgroesse_manuell : null,
      setup_zeit_min: form.setup_zeit_min,
      setup_maschinenstundensatz: form.setup_maschinenstundensatz || form.maschinenstundensatz,
      setup_lohnstundensatz: form.setup_lohnstundensatz,
      setup_mitarbeiter: form.setup_mitarbeiter,
      setup_aktiv: form.setup_aktiv || form.setup_zeit_min > 0,
      maschinen_groesse_modus: form.maschinen_groesse_modus,
      maschinen_groesse_breite_mm: form.maschinen_groesse_breite_mm,
      maschinen_groesse_laenge_mm: form.maschinen_groesse_laenge_mm,
      maschinen_groesse_oeffnungen_pct: form.maschinen_groesse_oeffnungen_pct,
      maschinen_groesse_proj_flaeche_mm2: form.maschinen_groesse_proj_flaeche_mm2,
      zykluszeit_quelle: form.zykluszeit_quelle,
      zykluszeit_wandstaerke_mm: form.zykluszeit_wandstaerke_mm,
      zykluszeit_groessenklasse: form.zykluszeit_groessenklasse,
      zykluszeit_prozessaufwand: form.zykluszeit_prozessaufwand,
      zykluszeit_entnahmeart: form.zykluszeit_entnahmeart,
      zykluszeit_nebenzeiten_gesamt_s: form.zykluszeit_nebenzeiten_gesamt_s,
    }),
    [form, veredelungZuordnungen, hierarchy.project_id],
  );

  const filteredWerke = useMemo(
    () =>
      selectedLandId == null
        ? werke
        : werke.filter((w) => w.land_id === selectedLandId),
    [werke, selectedLandId],
  );

  const filteredMachines = useMemo(() => {
    const base =
      form.werk_id == null
        ? machines.filter((m) => m.werk_id == null || !m.werk_id)
        : machines.filter((m) => m.werk_id === form.werk_id);
    return base.filter(isSpritzgussMachine);
  }, [machines, form.werk_id]);

  const filteredLohns = useMemo(() => {
    if (form.werk_id == null) return lohns;
    return lohns.filter((l) => l.werk_id === form.werk_id || l.werk_id == null);
  }, [lohns, form.werk_id]);

  const applyPlantLohnDefaults = (werkId: number) => {
    const prod = lohns.find((l) => l.werk_id === werkId && l.rolle === "produktion");
    const setup = lohns.find((l) => l.werk_id === werkId && l.rolle === "setup");
    setForm((current) => ({
      ...current,
      lohnkosten_id: prod?.id ?? null,
      lohnstundensatz: prod?.kosten_pro_stunde ?? current.lohnstundensatz,
      setup_lohnstundensatz: setup?.kosten_pro_stunde ?? current.setup_lohnstundensatz,
    }));
    setDecimalRaw((current) => ({
      ...current,
      ...(prod
        ? { lohnstundensatz: formatDecimalForInputDe(prod.kosten_pro_stunde) }
        : {}),
      ...(setup
        ? { setup_lohnstundensatz: formatDecimalForInputDe(setup.kosten_pro_stunde) }
        : {}),
    }));
  };

  const handleWerkChange = (id: string) => {
    if (!id) {
      setForm((current) => ({
        ...current,
        werk_id: null,
        maschine_id: null,
        lohnkosten_id: null,
      }));
      setMaschineManuell(false);
      return;
    }
    const wid = Number(id);
    const plant = werke.find((w) => w.id === wid);
    setForm((current) => ({
      ...current,
      werk_id: wid,
      maschine_id: null,
    }));
    setMaschineManuell(false);
    applyPlantLohnDefaults(wid);
    if (plant) {
      setSelectedLandId(plant.land_id);
    }
  };

  // Automatische Vorbelegung von Werk/Land aus der Projekt-Programm-Vorgabe.
  // Wir überschreiben nur, wenn der Nutzer noch keine Werk-Auswahl getroffen hat.
  useEffect(() => {
    if (form.werk_id != null) return;
    if (selectedLandId != null) return;

    const programId = hierarchy.program_id ?? null;
    if (programId == null) return;
    if (!lohns.length || !werke.length) return;

    let cancelled = false;
    (async () => {
      try {
        const program = await getProgram(programId);
        const productionPlant = (program.production_plant ?? "").trim();
        if (!productionPlant || cancelled) return;

        const werk =
          werke.find((w) => w.code === productionPlant) ??
          werke.find((w) => w.name === productionPlant) ??
          werke.find((w) => (w.code ?? "").toLowerCase() === productionPlant.toLowerCase());
        if (!werk || cancelled) return;

        setSelectedLandId(werk.land_id);
        setForm((current) => ({ ...current, werk_id: werk.id, maschine_id: null }));
        setMaschineManuell(false);
        applyPlantLohnDefaults(werk.id);
      } catch {
        // Fallback: ohne Zuordnung bleibt die manuelle Auswahl aktiv.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [hierarchy.program_id, form.werk_id, selectedLandId, werke, lohns]);

  const veredelungGesamtAktiv = useMemo(
    () =>
      selectedVeredelung
        .filter((s) => s.aktiv)
        .reduce((sum, s) => sum + (s.kosten_gesamt ?? s.kosten_inkl_ausschuss * s.mengenfaktor), 0),
    [selectedVeredelung],
  );

  const addVeredelungSchritt = (schritt: Veredelungsschritt) => {
    if (selectedVeredelung.some((s) => s.veredelungsschritt_id === schritt.id)) return;
    const nextOrder =
      selectedVeredelung.length === 0
        ? 1
        : Math.max(...selectedVeredelung.map((s) => s.reihenfolge)) + 1;
    setSelectedVeredelung((current) => [
      ...current,
      {
        veredelungsschritt_id: schritt.id,
        bezeichnung: schritt.bezeichnung,
        veredelungsart: schritt.veredelungsart,
        reihenfolge: nextOrder,
        aktiv: true,
        mengenfaktor: 1,
        kosten_inkl_ausschuss: schritt.kosten_inkl_ausschuss,
      },
    ]);
  };

  const removeVeredelungSchritt = (id: number) => {
    setSelectedVeredelung((current) => {
      const filtered = current.filter((s) => s.veredelungsschritt_id !== id);
      return filtered
        .sort((a, b) => a.reihenfolge - b.reihenfolge)
        .map((s, index) => ({ ...s, reihenfolge: index + 1 }));
    });
  };

  const moveVeredelung = (id: number, direction: "up" | "down") => {
    setSelectedVeredelung((current) => {
      const sorted = [...current].sort((a, b) => a.reihenfolge - b.reihenfolge);
      const index = sorted.findIndex((s) => s.veredelungsschritt_id === id);
      if (index < 0) return current;
      const swapWith = direction === "up" ? index - 1 : index + 1;
      if (swapWith < 0 || swapWith >= sorted.length) return current;
      const tmp = sorted[index].reihenfolge;
      sorted[index] = { ...sorted[index], reihenfolge: sorted[swapWith].reihenfolge };
      sorted[swapWith] = { ...sorted[swapWith], reihenfolge: tmp };
      return sorted;
    });
  };

  const updateSelectedFromResponse = (
    zuordnungen: VeredelungZuordnung[] | undefined,
  ) => {
    if (!zuordnungen?.length) return;
    setSelectedVeredelung(
      zuordnungen
        .map((z) => ({
          veredelungsschritt_id: z.veredelungsschritt_id,
          bezeichnung: z.snapshot_bezeichnung,
          veredelungsart: z.snapshot_veredelungsart,
          reihenfolge: z.reihenfolge,
          aktiv: z.aktiv,
          mengenfaktor: z.mengenfaktor,
          kosten_inkl_ausschuss: z.snapshot_kosten_inkl_ausschuss,
          kosten_gesamt: z.kosten_gesamt,
        }))
        .sort((a, b) => a.reihenfolge - b.reihenfolge),
    );
  };

  const loadVeredelungFromSaved = (zuordnungen: VeredelungZuordnung[] | undefined) => {
    if (!zuordnungen?.length) {
      setSelectedVeredelung([]);
      return;
    }
    updateSelectedFromResponse(zuordnungen);
  };

  const handleMaterialChange = (id: string) => {
    if (!id) {
      setField("material_id", null);
      return;
    }
    const mat = materials.find((m) => m.id === Number(id));
    if (!mat) return;
    setForm((current) => ({
      ...current,
      material_id: mat.id,
      materialpreis_pro_kg: mat.preis_pro_kg,
    }));
    setDecimalRaw((current) => ({
      ...current,
      materialpreis_pro_kg: formatDecimalForInputDe(mat.preis_pro_kg),
    }));
  };

  const handleMaschineChange = (id: string, opts?: { manual?: boolean }) => {
    if (!id) {
      setField("maschine_id", null);
      setMaschineManuell(false);
      return;
    }
    const manual = opts?.manual ?? true;
    if (manual) setMaschineManuell(true);
    const maschine = machines.find((m) => m.id === Number(id));
    if (!maschine) return;
    setForm((current) => ({
      ...current,
      maschine_id: maschine.id,
      maschinenstundensatz: maschine.stundensatz,
      setup_maschinenstundensatz: maschine.stundensatz,
      setup_zeit_min: maschine.setup_zeit_min ?? current.setup_zeit_min,
      setup_mitarbeiter: maschine.setup_mitarbeiter ?? current.setup_mitarbeiter,
      setup_aktiv: (maschine.setup_zeit_min ?? 0) > 0,
      werk_id: maschine.werk_id ?? current.werk_id,
    }));
    setDecimalRaw((current) => ({
      ...current,
      maschinenstundensatz: formatDecimalForInputDe(maschine.stundensatz),
      setup_maschinenstundensatz: formatDecimalForInputDe(maschine.stundensatz),
      setup_zeit_min: formatDecimalForInputDe(maschine.setup_zeit_min ?? 0),
      setup_mitarbeiter: formatDecimalForInputDe(maschine.setup_mitarbeiter ?? 0),
    }));
    const werkId = maschine.werk_id ?? form.werk_id;
    if (werkId != null) {
      applyPlantLohnDefaults(werkId);
    }
  };

  const handleLohnChange = (id: string) => {
    if (!id) {
      setField("lohnkosten_id", null);
      return;
    }
    const lohn = lohns.find((l) => l.id === Number(id));
    if (!lohn) return;
    setForm((current) => ({
      ...current,
      lohnkosten_id: lohn.id,
      lohnstundensatz: lohn.kosten_pro_stunde,
    }));
    setDecimalRaw((current) => ({
      ...current,
      lohnstundensatz: formatDecimalForInputDe(lohn.kosten_pro_stunde),
    }));
  };

  const applyMaschinenGroesseResponse = (result: MaschinenGroesseResult | null | undefined) => {
    setMaschinenGroesse(result ?? null);
  };

  // Automatische Maschinen-Auswahl aus der Maschinengrößenberechnung,
  // solange der Nutzer noch nichts manuell geändert hat.
  useEffect(() => {
    if (maschineManuell) return;
    if (maschinenGroesse?.empfohlene_maschine_id == null) return;

    const empfohleneId = maschinenGroesse.empfohlene_maschine_id;
    const maschine = machines.find((m) => m.id === empfohleneId);
    if (!maschine) return;
    if (form.maschine_id === maschine.id) return;

    // `manual: false` heißt: wir übernehmen die Empfehlung, markieren die
    // Auswahl aber noch nicht als Nutzer-Änderung.
    handleMaschineChange(String(maschine.id), { manual: false });
  }, [maschineManuell, maschinenGroesse?.empfohlene_maschine_id, form.maschine_id, machines]);

  const handleBerechnen = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      // Dezimalfelder leben in decimalRaw; form kann noch null sein (Vorschau liest Raw).
      const parsedForm = resolveParsedForm();
      setForm(parsedForm);
      const result = await berechnen({
        ...calcPayloadBase,
        teilegewicht_netto_g: parsedForm.teilegewicht_netto_g,
        schussgewicht_g: parsedForm.schussgewicht_g,
        materialpreis_pro_kg: parsedForm.materialpreis_pro_kg,
        ausschussquote_pct: parsedForm.ausschussquote_pct,
        zykluszeit_s: parsedForm.zykluszeit_s,
        maschinenstundensatz: parsedForm.maschinenstundensatz,
        kavitaeten: parsedForm.kavitaeten,
        lohnstundensatz: parsedForm.lohnstundensatz,
        setup_zeit_min: parsedForm.setup_zeit_min,
        setup_maschinenstundensatz:
          parsedForm.setup_maschinenstundensatz || parsedForm.maschinenstundensatz,
        setup_lohnstundensatz: parsedForm.setup_lohnstundensatz,
        setup_mitarbeiter: parsedForm.setup_mitarbeiter,
        setup_aktiv: parsedForm.setup_aktiv || parsedForm.setup_zeit_min > 0,
        losgroesse_modus: parsedForm.losgroesse_modus,
        losgroesse_manuell:
          parsedForm.losgroesse_modus === "manuell" ? parsedForm.losgroesse_manuell : null,
        maschinen_groesse_modus: parsedForm.maschinen_groesse_modus,
        maschinen_groesse_breite_mm: parsedForm.maschinen_groesse_breite_mm,
        maschinen_groesse_laenge_mm: parsedForm.maschinen_groesse_laenge_mm,
        maschinen_groesse_oeffnungen_pct: parsedForm.maschinen_groesse_oeffnungen_pct,
        maschinen_groesse_proj_flaeche_mm2: parsedForm.maschinen_groesse_proj_flaeche_mm2,
        zykluszeit_quelle: parsedForm.zykluszeit_quelle,
        zykluszeit_wandstaerke_mm: parsedForm.zykluszeit_wandstaerke_mm,
        zykluszeit_groessenklasse: parsedForm.zykluszeit_groessenklasse,
        zykluszeit_prozessaufwand: parsedForm.zykluszeit_prozessaufwand,
        zykluszeit_entnahmeart: parsedForm.zykluszeit_entnahmeart,
        zykluszeit_nebenzeiten_gesamt_s: parsedForm.zykluszeit_nebenzeiten_gesamt_s,
      });
      setBloecke(result.bloecke);
      applyMaschinenGroesseResponse(result.maschinen_groesse);
      updateSelectedFromResponse(result.veredelung_zuordnungen);
      setSuccess(t("spritzguss.calcSuccess"));
    } catch (err) {
      setError(
        err instanceof PercentPointsParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : t("spritzguss.calcFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    if (!canWrite) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const parsedForm = resolveParsedForm();
      if (!parsedForm.teilebezeichnung.trim()) {
        throw new Error(t("spritzguss.partNameRequired"));
      }
      if (!parsedForm.teilenummer.trim()) {
        throw new Error(t("spritzguss.partNumberRequired"));
      }
      if (!legacyHierarchy && hierarchy.project_id == null) {
        throw new Error(t("spritzguss.hierarchyRequired"));
      }
      const payload = {
        ...parsedForm,
        customer_id: hierarchy.customer_id,
        program_id: hierarchy.program_id,
        project_id: hierarchy.project_id,
        jahresstueckzahl: legacyHierarchy?.jahresstueckzahl ?? 0,
        kunde: form.kunde,
        projekt: form.projekt,
        werkzeugkosten_eur: 0,
        werkzeug_abrechnungsart: "einmalzahlung" as const,
        amortisationsvolumen: null,
        veredelung_zuordnungen: veredelungZuordnungen,
      };
      const wasNew = editId == null;
      const saved =
        editId == null
          ? await createKalkulation(payload)
          : await updateKalkulation(editId, payload);
      setEditId(saved.id);
      setBloecke((saved.ergebnis_bloecke as SpritzgussBloecke) ?? null);
      const savedSizing =
        (saved.ergebnis as { maschinen_groesse?: MaschinenGroesseResult } | null)?.maschinen_groesse ??
        null;
      setMaschinenGroesse(savedSizing);
      setZykluszeitVorschlag(
        (saved.ergebnis as { zykluszeit_vorschlag?: ZykluszeitVorschlag } | null)
          ?.zykluszeit_vorschlag ?? null,
      );
      if (saved.maschine_id != null) {
        setField("maschine_id", saved.maschine_id);
      }
      loadVeredelungFromSaved(saved.veredelung_zuordnungen);
      setSuccess(
        wasNew
          ? t("spritzguss.calcSaved", { id: saved.id })
          : t("spritzguss.calcUpdated", { id: saved.id }),
      );
      setSavedListRefreshKey((value) => value + 1);
    } catch (err) {
      setError(
        err instanceof PercentPointsParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : t("spritzguss.saveFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const handleLoad = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      const item = await getKalkulation(id);
      setEditId(item.id);
      const hasHierarchy = item.project_id != null && item.customer_id != null;
      if (hasHierarchy) {
        setLegacyHierarchy(null);
        setHierarchy({
          customer_id: item.customer_id ?? null,
          program_id: item.program_id ?? null,
          project_id: item.project_id ?? null,
        });
      } else {
        setLegacyHierarchy({
          kunde: item.kunde,
          projekt: item.projekt,
          jahresstueckzahl: item.jahresstueckzahl,
          calculation_year: item.calculation_year,
        });
        setHierarchy({
          customer_id: null,
          program_id: null,
          project_id: null,
        });
      }
      setForm({
        teilebezeichnung: item.teilebezeichnung,
        teilenummer: item.teilenummer,
        kunde: item.kunde,
        projekt: item.projekt,
        jahresstueckzahl: item.jahresstueckzahl,
        customer_id: item.customer_id ?? null,
        program_id: item.program_id ?? null,
        project_id: item.project_id ?? null,
        calculation_year: item.calculation_year ?? null,
        project_volume: item.project_volume ?? null,
        material_id: item.material_id,
        schussgewicht_g: item.schussgewicht_g,
        teilegewicht_netto_g: item.teilegewicht_netto_g,
        ausschussquote_pct: item.ausschussquote_pct,
        materialpreis_pro_kg: item.materialpreis_pro_kg,
        material_nominierung: item.material_nominierung ?? null,
        maschinen_groesse_modus: item.maschinen_groesse_modus ?? null,
        maschinen_groesse_breite_mm: item.maschinen_groesse_breite_mm ?? null,
        maschinen_groesse_laenge_mm: item.maschinen_groesse_laenge_mm ?? null,
        maschinen_groesse_oeffnungen_pct: item.maschinen_groesse_oeffnungen_pct ?? null,
        // Backend persistiert bei Bestandsdaten ggf. nur die Nettofläche.
        // Für den `flaeche`-Modus akzeptieren wir die Nettofläche als Eingabewert.
        maschinen_groesse_proj_flaeche_mm2:
          item.maschinen_groesse_proj_flaeche_mm2 ??
          item.maschinen_groesse_proj_flaeche_netto_mm2 ??
          null,
        werk_id: item.werk_id ?? null,
        losgroesse: item.losgroesse ?? null,
        losgroesse_modus: inferLegacyLosgroesseModus(item.losgroesse_modus, item.losgroesse),
        losgroesse_manuell:
          item.losgroesse_manuell ??
          (inferLegacyLosgroesseModus(item.losgroesse_modus, item.losgroesse) === "manuell"
            ? item.losgroesse
            : null),
        setup_zeit_min: item.setup_zeit_min ?? 0,
        setup_maschinenstundensatz: item.setup_maschinenstundensatz ?? 0,
        setup_lohnstundensatz: item.setup_lohnstundensatz ?? 0,
        setup_mitarbeiter: item.setup_mitarbeiter ?? 0,
        setup_aktiv: item.setup_aktiv ?? false,
        maschine_id: item.maschine_id,
        zykluszeit_s: item.zykluszeit_s,
        kavitaeten: item.kavitaeten,
        maschinenstundensatz: item.maschinenstundensatz,
        zykluszeit_quelle: item.zykluszeit_quelle ?? "manuell",
        zykluszeit_wandstaerke_mm: item.zykluszeit_wandstaerke_mm ?? null,
        zykluszeit_groessenklasse: gespeicherteGroessenklasse(item.zykluszeit_groessenklasse),
        zykluszeit_prozessaufwand:
          item.zykluszeit_prozessaufwand === "aufwendig" ? "aufwendig" : "normal",
        zykluszeit_entnahmeart: entnahmeartNormalisiert(item.zykluszeit_entnahmeart),
        zykluszeit_nebenzeiten_gesamt_s: item.zykluszeit_nebenzeiten_gesamt_s ?? null,
        lohnkosten_id: item.lohnkosten_id,
        lohnstundensatz: item.lohnstundensatz,
        werkzeugkosten_eur: item.werkzeugkosten_eur,
        werkzeug_abrechnungsart:
          (item.werkzeug_abrechnungsart as WerkzeugAbrechnungsart) || "amortisation",
        amortisationsvolumen:
          item.werkzeug_abrechnungsart === "einmalzahlung"
            ? null
            : item.amortisationsvolumen != null
              ? Math.round(Number(item.amortisationsvolumen))
              : 1,
        mgk_pct: item.mgk_pct,
        fgk_pct: item.fgk_pct,
        vvgk_pct: item.vvgk_pct,
        gewinn_pct: item.gewinn_pct,
        skonto_pct: item.skonto_pct,
        notizen: item.notizen,
        aktiv: item.aktiv,
        teilbild_mime: item.teilbild_mime ?? null,
        teilbild_data: item.teilbild_data ?? null,
      });
      if (item.werk_id != null) {
        const plant = werke.find((w) => w.id === item.werk_id);
        if (plant) setSelectedLandId(plant.land_id);
      } else {
        setSelectedLandId(null);
      }
      setMaschineManuell(item.maschine_id != null);
      setDecimalRaw(
        loadSpritzgussDecimalRaw({
          ...emptySpritzgussForm(),
          schussgewicht_g: item.schussgewicht_g,
          teilegewicht_netto_g: item.teilegewicht_netto_g,
          materialpreis_pro_kg: item.materialpreis_pro_kg,
          ausschussquote_pct: item.ausschussquote_pct,
          zykluszeit_s: item.zykluszeit_s,
          kavitaeten: item.kavitaeten,
          maschinenstundensatz: item.maschinenstundensatz,
          lohnstundensatz: item.lohnstundensatz,
          setup_zeit_min: item.setup_zeit_min ?? 0,
          setup_maschinenstundensatz: item.setup_maschinenstundensatz ?? 0,
          setup_lohnstundensatz: item.setup_lohnstundensatz ?? 0,
          setup_mitarbeiter: item.setup_mitarbeiter ?? 0,
          losgroesse_manuell:
            item.losgroesse_manuell ??
            (inferLegacyLosgroesseModus(item.losgroesse_modus, item.losgroesse) === "manuell"
              ? item.losgroesse
              : null),
          maschinen_groesse_breite_mm: item.maschinen_groesse_breite_mm ?? null,
          maschinen_groesse_laenge_mm: item.maschinen_groesse_laenge_mm ?? null,
          maschinen_groesse_oeffnungen_pct: item.maschinen_groesse_oeffnungen_pct ?? null,
          maschinen_groesse_proj_flaeche_mm2:
            item.maschinen_groesse_proj_flaeche_mm2 ??
            item.maschinen_groesse_proj_flaeche_netto_mm2 ??
            null,
          zykluszeit_wandstaerke_mm: item.zykluszeit_wandstaerke_mm ?? null,
          zykluszeit_nebenzeiten_gesamt_s: item.zykluszeit_nebenzeiten_gesamt_s ?? null,
        }),
      );
      setMaschinenGroesse(
        (item.ergebnis as { maschinen_groesse?: MaschinenGroesseResult } | null)?.maschinen_groesse ??
          null,
      );
      setZykluszeitVorschlag(
        (item.ergebnis as { zykluszeit_vorschlag?: ZykluszeitVorschlag } | null)
          ?.zykluszeit_vorschlag ?? null,
      );
      setBloecke((item.ergebnis_bloecke as SpritzgussBloecke) ?? null);
      loadVeredelungFromSaved(item.veredelung_zuordnungen);
      setSuccess(t("spritzguss.calcLoaded", { id: item.id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("spritzguss.loadFailed"));
    } finally {
      setBusy(false);
    }
  };

  const handleNew = () => {
    const defaults = formDefaults();
    setEditId(null);
    setForm({
      ...emptySpritzgussForm(),
      customer_id: defaults.customer_id,
      program_id: defaults.program_id,
      project_id: defaults.project_id,
    });
    setDecimalRaw(loadSpritzgussDecimalRaw(emptySpritzgussForm()));
    setHierarchy(defaults);
    setLegacyHierarchy(null);
    setSelectedVeredelung([]);
    setBloecke(null);
    setMaschinenGroesse(null);
    setMaschineManuell(false);
    setZykluszeitVorschlag(null);
    setSuccess(null);
    setError(null);
  };

  const ergebnisUebersicht = useMemo(() => {
    if (!bloecke) return null;
    if (bloecke.zusammenfassung) return bloecke.zusammenfassung;
    const g = bloecke.gemeinkosten;
    const v = bloecke.verkaufspreis;
    const f = bloecke.fertigung;
    const m = bloecke.material;
    if (!g || !v) return null;
    const hk = Number(g.herstellkosten ?? 0);
    return {
      materialkosten_gesamt: Number(m?.materialkosten_gesamt ?? 0),
      maschinenkosten: Number(f?.maschinenkosten ?? 0),
      fertigungslohn: Number(f?.fertigungslohn ?? 0),
      setup_kosten_je_teil: Number(f?.setup_kosten_je_teil ?? 0),
      veredelung_gesamt: Number(bloecke.veredelung?.veredelung_gesamt ?? 0),
      fgk_basis: Number(f?.fgk_basis ?? 0),
      fertigungsgemeinkosten: Number(f?.fertigungsgemeinkosten ?? 0),
      gesamte_herstellkosten: hk,
      vvgk: Number(g.vvgk ?? 0),
      selbstkosten: Number(g.selbstkosten ?? 0),
      gewinn: Number(g.gewinn ?? 0),
      nettoverkaufspreis_gesamt: Number(v.nettoverkaufspreis ?? 0),
      skonto: Number(v.skonto ?? 0),
      endpreis_je_stueck: Number(v.verkaufspreis ?? 0),
    };
  }, [bloecke]);

  const handleExport = async (format: "pdf" | "xlsx") => {
    if (editId == null) return;
    setExportBusy(true);
    setError(null);
    try {
      const nummer = form.teilenummer.trim() || String(editId);
      const filename = `einzelteil_${nummer}.${format === "pdf" ? "pdf" : "xlsx"}`;
      const path = format === "pdf" ? spritzgussPdfUrl(editId) : spritzgussXlsxUrl(editId);
      await downloadReport(path, filename);
      setSuccess(t("spritzguss.exportSuccess", { format: format.toUpperCase() }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.exportFailed"));
    } finally {
      setExportBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!canWrite) return;
    setBusy(true);
    setError(null);
    try {
      await deleteKalkulation(id);
      if (editId === id) handleNew();
      setSavedListRefreshKey((value) => value + 1);
      setSuccess(t("spritzguss.calcDeleted"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("spritzguss.deleteFailed"));
    } finally {
      setBusy(false);
    }
  };

  const teilbildPreview = useMemo(
    () => teilbildSrc(form.teilbild_mime, form.teilbild_data),
    [form.teilbild_mime, form.teilbild_data],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t("spritzguss.title")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("spritzguss.intro")}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleNew}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            {t("spritzguss.newCalculation")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleBerechnen}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
          >
            {t("spritzguss.calculate")}
          </button>
          {canWrite && (
            <button
              type="button"
              disabled={busy}
              onClick={handleSave}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {t("spritzguss.saveCalculation")}
            </button>
          )}
          {editId != null && (
            <ExportButtons
              busy={exportBusy}
              disabled={editId == null}
              onPdf={() => handleExport("pdf")}
              onExcel={() => handleExport("xlsx")}
            />
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{success}</div>
      )}
      {editId != null && (
        <p className="text-sm text-slate-600">
          {t("spritzguss.editingSaved")} <strong>#{editId}</strong>
        </p>
      )}

      <SpritzgussSavedList
        activeId={editId}
        canWrite={canWrite}
        refreshKey={savedListRefreshKey}
        onOpen={(id) => void handleLoad(id)}
        onDelete={(id) => void handleDelete(id)}
      />

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <form id="spritzguss-form" className="space-y-6" onSubmit={(e) => e.preventDefault()}>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.generalData")}</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <TextInput
                label={t("spritzguss.partName")}
                value={form.teilebezeichnung}
                onChange={(v) => setField("teilebezeichnung", v)}
              />
              <TextInput
                label={t("spritzguss.partNumber")}
                value={form.teilenummer}
                onChange={(v) => setField("teilenummer", v)}
              />
            </div>
            <div className="mt-4">
              <HierarchySelector
                value={hierarchy}
                legacyText={legacyHierarchy}
                onChange={(next) => {
                  setHierarchy(next);
                  setForm((f) => ({
                    ...f,
                    customer_id: next.customer_id,
                    program_id: next.program_id,
                    project_id: next.project_id,
                  }));
                }}
              />
            </div>
            <div className="mt-4">
              <TeilbildField
                mime={form.teilbild_mime}
                data={form.teilbild_data}
                disabled={!canWrite}
                onChange={({ mime, data }) => {
                  setForm((current) => ({
                    ...current,
                    teilbild_mime: mime,
                    teilbild_data: data,
                  }));
                }}
              />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.materialSection")}</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("spritzguss.materialMaster")}</span>
                <select
                  value={form.material_id ?? ""}
                  onChange={(e) => handleMaterialChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("project.selectOption")}</option>
                  {materials.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.material_nr} – {m.bezeichnung} ({euro(m.preis_pro_kg)} €/kg)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                fieldKey="schussgewicht_g"
                label={t("spritzguss.shotWeightGross")}
                value={form.schussgewicht_g}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="teilegewicht_netto_g"
                label={t("spritzguss.netPartWeight")}
                value={form.teilegewicht_netto_g}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="ausschussquote_pct"
                label={t("spritzguss.scrapRate")}
                value={form.ausschussquote_pct}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="materialpreis_pro_kg"
                label={t("spritzguss.materialPrice")}
                value={form.materialpreis_pro_kg}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("spritzguss.materialNomination")}</span>
                <select
                  value={form.material_nominierung ?? ""}
                  onChange={(e) =>
                    setField(
                      "material_nominierung",
                      e.target.value
                        ? (e.target.value as "selbstnominiert" | "oem_nominiert")
                        : null,
                    )
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("common.pleaseSelect")}</option>
                  <option value="selbstnominiert">{t("spritzguss.selfNominated")}</option>
                  <option value="oem_nominiert">{t("spritzguss.oemNominated")}</option>
                </select>
                {!form.material_nominierung && (
                  <p className="mt-1 text-xs text-amber-800">{t("spritzguss.nominationRequired")}</p>
                )}
              </label>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.machineSizeSection")}</h3>
            <p className="mb-3 text-xs text-gray-600">{t("spritzguss.machineSizeHint")}</p>
            <div className="mb-4 flex flex-wrap gap-4 text-sm">
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  name="maschinen_groesse_modus"
                  checked={form.maschinen_groesse_modus === "masse"}
                  onChange={() => setField("maschinen_groesse_modus", "masse")}
                />
                {t("spritzguss.dimensions")}
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  name="maschinen_groesse_modus"
                  checked={form.maschinen_groesse_modus === "flaeche"}
                  onChange={() => setField("maschinen_groesse_modus", "flaeche")}
                />
                {t("spritzguss.projectedArea")}
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  name="maschinen_groesse_modus"
                  checked={form.maschinen_groesse_modus == null}
                  onChange={() => setField("maschinen_groesse_modus", null)}
                />
                {t("spritzguss.noCalculation")}
              </label>
            </div>
            {form.maschinen_groesse_modus != null && (
              <div className="grid gap-3 md:grid-cols-2">
                {form.maschinen_groesse_modus === "masse" ? (
                  <>
                    <NumberInput
                      fieldKey="maschinen_groesse_breite_mm"
                      label={t("spritzguss.widthMm")}
                      value={form.maschinen_groesse_breite_mm ?? 0}
                      decimalRaw={decimalRaw}
                      onDecimalChange={handleDecimalChange}
                    />
                    <NumberInput
                      fieldKey="maschinen_groesse_laenge_mm"
                      label={t("spritzguss.lengthMm")}
                      value={form.maschinen_groesse_laenge_mm ?? 0}
                      decimalRaw={decimalRaw}
                      onDecimalChange={handleDecimalChange}
                    />
                    <NumberInput
                      fieldKey="maschinen_groesse_oeffnungen_pct"
                      label={t("spritzguss.openingsPct")}
                      value={form.maschinen_groesse_oeffnungen_pct ?? 0}
                      decimalRaw={decimalRaw}
                      onDecimalChange={handleDecimalChange}
                    />
                  </>
                ) : (
                  <NumberInput
                    fieldKey="maschinen_groesse_proj_flaeche_mm2"
                    label={t("spritzguss.projectedAreaMm2")}
                    value={form.maschinen_groesse_proj_flaeche_mm2 ?? 0}
                    decimalRaw={decimalRaw}
                    onDecimalChange={handleDecimalChange}
                  />
                )}
                <div className="text-sm md:col-span-2 rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="font-medium text-gray-800">{t("spritzguss.materialData")}</div>
                  <div className="mt-1 text-gray-700">
                    {selectedMaterial
                      ? `${selectedMaterial.bezeichnung} (${selectedMaterial.material_nr})`
                      : t("spritzguss.noMaterialSelected")}
                  </div>
                  <div className="mt-1 text-gray-600">
                    {t("spritzguss.injectionPressure")}:{" "}
                    {selectedMaterial
                      ? `${formatSizingNumber(selectedMaterial.injection_pressure_kg_cm2, 2)} kg/cm²`
                      : "–"}
                  </div>
                  <div className="text-gray-600">
                    {t("spritzguss.cavities")}: {effectiveKavitaeten}
                  </div>
                  {maschinenGroesse && (
                    <>
                      <div className="text-gray-600">
                        {t("spritzguss.projectedAreaNet")}:{" "}
                        {formatSizingNumber(maschinenGroesse.proj_flaeche_netto_mm2, 2)} mm²
                      </div>
                      <div className="text-gray-600">
                        {t("spritzguss.clampingForceWithoutSafety")}:{" "}
                        {formatSizingNumber(maschinenGroesse.zuhaltekraft_ohne_sicherheit_t)} t
                      </div>
                      <div className="text-gray-600">
                        {t("spritzguss.requiredClampingForce")}:{" "}
                        {formatSizingNumber(maschinenGroesse.zuhaltekraft_erforderlich_t)} t
                      </div>
                      <div className="text-gray-600">
                        {t("spritzguss.recommendedMachine")}:{" "}
                        {maschinenGroesse.empfohlene_maschine_name ?? t("spritzguss.noMatchingMachine")}
                      </div>
                      <div className="text-gray-600">
                        {t("spritzguss.machineClampingForce")}:{" "}
                        {formatSizingNumber(
                          maschinenGroesse.empfohlene_maschine_schliesskraft_t,
                          2,
                        )}{" "}
                        t
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
            {maschinenGroesse?.warnung && (
              <p className="mt-3 text-sm text-amber-800">{maschinenGroesse.warnung}</p>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-1 font-semibold text-gray-900">{t("spritzguss.cycleTimeSection")}</h3>
            <p className="mb-3 text-xs text-gray-600">{t("spritzguss.cycleTimeIntro")}</p>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <NumberInput
                  fieldKey="zykluszeit_wandstaerke_mm"
                  label={t("spritzguss.coolingWallThickness")}
                  value={form.zykluszeit_wandstaerke_mm ?? 0}
                  decimalRaw={decimalRaw}
                  onDecimalChange={handleDecimalChange}
                />
                <p className="mt-1 text-xs text-gray-500">
                  {t("spritzguss.coolingWallThicknessHint")}
                </p>
              </div>
              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("spritzguss.demoldingType")}</span>
                <select
                  value={form.zykluszeit_entnahmeart}
                  onChange={(e) =>
                    setField("zykluszeit_entnahmeart", e.target.value as ZykluszeitEntnahmeart)
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  {ZYKLUSZEIT_ENTNAHMEARTEN.map(({ key }) => (
                    <option key={key} value={key}>
                      {entnahmeLabel(t, key)}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {entnahmeDesc(t, form.zykluszeit_entnahmeart)}
                </p>
              </label>
              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("spritzguss.processEffort")}</span>
                <select
                  value={form.zykluszeit_prozessaufwand}
                  onChange={(e) =>
                    setField(
                      "zykluszeit_prozessaufwand",
                      e.target.value as ZykluszeitProzessaufwand,
                    )
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="normal">{t("spritzguss.processNormal")}</option>
                  <option value="aufwendig">{t("spritzguss.processComplex")}</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {form.zykluszeit_prozessaufwand === "aufwendig"
                    ? t("spritzguss.processComplexHint", {
                        seconds: ZYKLUSZEIT_PROZESSAUFWAND_ZUSCHLAG_S,
                      })
                    : t("spritzguss.processNormalHint")}
                </p>
              </label>
              <div>
                <NumberInput
                  fieldKey="zykluszeit_nebenzeiten_gesamt_s"
                  label={t("spritzguss.ancillaryTimeTotal")}
                  value={
                    form.zykluszeit_nebenzeiten_gesamt_s ??
                    zykluszeitVorschlag?.nebenzeiten_automatisch_s ??
                    0
                  }
                  decimalRaw={decimalRaw}
                  onDecimalChange={handleDecimalChange}
                />
                <p className="mt-1 text-xs text-gray-500">
                  {t("spritzguss.ancillaryTimeHint")}
                </p>
              </div>
            </div>

            <div
              className={
                zykluszeitVorschlag?.status === "nicht_plausibel"
                  ? "mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm"
                  : "mt-4 rounded-md border border-gray-100 bg-gray-50 p-3 text-sm"
              }
              role={zykluszeitVorschlag?.status === "nicht_plausibel" ? "alert" : undefined}
            >
              {zykluszeitVorschlag?.berechenbar ? (
                zykluszeitVorschlag.status === "nicht_plausibel" ? (
                <>
                  <div className="font-medium text-amber-950">
                    {t("spritzguss.suggestionNotPlausible")}
                  </div>
                  <p className="mt-1 text-sm text-amber-950">
                    {t("spritzguss.suggestionNotPlausibleBody")}
                  </p>
                  <dl className="mt-2 grid gap-x-6 gap-y-1 text-amber-950 sm:grid-cols-2">
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.calculatedDosingTime")}</dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.nebenzeit_dosierzeit_s)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.coolingTimeForCalc")}</dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.kuehlzeit_s)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.plasticizingRate")}</dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.plastifizierleistung_kg_h, 0)} kg/h
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.shotWeight")}</dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.schussgewicht_g, 0)} g ·{" "}
                        {zykluszeitVorschlag.kavitaeten ?? 1} Kav.
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.decisiveClampingForce")}</dt>
                      <dd>
                        {zykluszeitVorschlag.zuhaltekraft_t == null
                          ? "–"
                          : `${formatSizingNumber(zykluszeitVorschlag.zuhaltekraft_t)} t`}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.dosingOverrun")}</dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.nebenzeit_dosier_ueberhang_s)} s
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.calculatedTotalNotApplicable")}</dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.gesamtzykluszeit_s, 0)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.currentlyUsedCycleTime")}</dt>
                      <dd>
                        {formatZykluszeitFeld(form.zykluszeit_s)} s (
                        {form.zykluszeit_quelle === "vorschlag"
                          ? t("spritzguss.fromSuggestion")
                          : t("spritzguss.enteredManually")}
                        )
                      </dd>
                    </div>
                  </dl>
                  <p className="mt-2 text-xs text-amber-900">
                    {t("spritzguss.checkInputsHint")}
                  </p>
                  {(zykluszeitVorschlag.warnungen ?? []).map((warnung) => (
                    <p key={warnung} className="mt-2 text-xs text-amber-900">
                      {warnung}
                    </p>
                  ))}
                </>
                ) : (
                <>
                  <div className="font-medium text-gray-900">
                    {t("spritzguss.suggestionLabel", {
                      seconds: formatSekunden(zykluszeitVorschlag.gesamtzykluszeit_s, 0),
                    })}
                    <span className="ml-2 text-xs font-normal text-gray-500">
                      {t("spritzguss.suggestionValid")}
                    </span>
                  </div>
                  <dl className="mt-2 grid gap-x-6 gap-y-1 text-gray-700 sm:grid-cols-2">
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.moldMovement")}</dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.nebenzeit_werkzeugbewegung_s)} s
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.injectionAndHold")}</dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.nebenzeit_einspritz_nachdruck_s)} s
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>
                        {t("spritzguss.dosingOverrun")}
                        <span className="ml-1 text-xs text-gray-500">
                          {t("spritzguss.dosingTimeAtRate", {
                            dosing: formatSekunden(zykluszeitVorschlag.nebenzeit_dosierzeit_s),
                            rate: formatSekunden(zykluszeitVorschlag.plastifizierleistung_kg_h, 0),
                          })}
                        </span>
                      </dt>
                      <dd>
                        {formatSekunden(zykluszeitVorschlag.nebenzeit_dosier_ueberhang_s)} s
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>
                        {t("spritzguss.demolding")}
                        <span className="ml-1 text-xs text-gray-500">
                          (
                          {zykluszeitVorschlag.entnahmeart
                            ? entnahmeLabel(t, zykluszeitVorschlag.entnahmeart)
                            : "–"}
                          )
                        </span>
                      </dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.nebenzeit_entnahme_s)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>
                        {t("spritzguss.processEffort")}
                        <span className="ml-1 text-xs text-gray-500">
                          (
                          {zykluszeitVorschlag.prozessaufwand === "aufwendig"
                            ? t("spritzguss.processComplex")
                            : t("spritzguss.processNormal")}
                          )
                        </span>
                      </dt>
                      <dd>
                        {formatSekunden(
                          zykluszeitVorschlag.nebenzeit_prozessaufwand_zuschlag_s,
                        )}{" "}
                        s
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2 font-medium text-gray-900">
                      <dt>
                        {t("spritzguss.ancillaryTotal")}
                        <span className="ml-1 text-xs font-normal text-gray-500">
                          (
                          {zykluszeitVorschlag.nebenzeit_quelle === "manuell"
                            ? t("spritzguss.manual")
                            : t("spritzguss.automatic")}
                          )
                        </span>
                      </dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.nebenzeiten_gesamt_s)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.coolingTimeForCalc")}</dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.kuehlzeit_s)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2 font-medium text-gray-900">
                      <dt>
                        {t("spritzguss.suggestedTotalCycleTime")}
                        <span className="ml-1 text-xs font-normal text-gray-500">
                          {t("spritzguss.unrounded", {
                            seconds: formatSekunden(zykluszeitVorschlag.gesamtzykluszeit_exakt_s),
                          })}
                        </span>
                      </dt>
                      <dd>{formatSekunden(zykluszeitVorschlag.gesamtzykluszeit_s, 0)} s</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>{t("spritzguss.currentlyUsedCycleTime")}</dt>
                      <dd>
                        {formatZykluszeitFeld(form.zykluszeit_s)} s (
                        {form.zykluszeit_quelle === "vorschlag"
                          ? t("spritzguss.fromSuggestion")
                          : t("spritzguss.enteredManually")}
                        )
                      </dd>
                    </div>
                  </dl>
                  {zykluszeitVorschlag.nebenzeit_quelle === "manuell" ? (
                    <p className="mt-2 text-xs text-gray-500">
                      {t("spritzguss.manualAncillaryPriority", {
                        manual: formatSekunden(zykluszeitVorschlag.nebenzeiten_gesamt_s),
                        auto: formatSekunden(zykluszeitVorschlag.nebenzeiten_automatisch_s),
                      })}
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-gray-500">
                    {t("spritzguss.experienceValuesNote")}
                  </p>
                  {zykluszeitVorschlag.zuhaltekraft_fallback ? (
                    <p className="mt-1 text-xs text-amber-800">
                      {t("spritzguss.noClampingFallback")}
                    </p>
                  ) : null}
                  {zykluszeitVorschlag.schussgewicht_fallback ? (
                    <p className="mt-1 text-xs text-amber-800">
                      {t("spritzguss.noShotWeightFallback", {
                        seconds: formatSekunden(
                          zykluszeitVorschlag.nebenzeit_einspritz_nachdruck_s,
                        ),
                      })}
                    </p>
                  ) : null}
                  <div className="mt-2 text-xs text-gray-500">
                    {t("spritzguss.materialTempsSummary", {
                      group: zykluszeitVorschlag.materialgruppe ?? "",
                      material: zykluszeitVorschlag.material_bezeichnung ?? "",
                      classSuffix: zykluszeitVorschlag.materialklasse
                        ? `, ${zykluszeitVorschlag.materialklasse}`
                        : "",
                      mold: formatSekunden(zykluszeitVorschlag.werkzeugtemperatur_c, 0),
                      melt: formatSekunden(zykluszeitVorschlag.schmelzetemperatur_c, 0),
                      demold: formatSekunden(zykluszeitVorschlag.entformungstemperatur_c, 0),
                      theo: formatSekunden(zykluszeitVorschlag.optimale_kuehlzeit_s),
                      factor: formatSekunden(zykluszeitVorschlag.kuehlfaktor, 1),
                      wall: formatSekunden(zykluszeitVorschlag.wandstaerke_mm),
                      clamp:
                        zykluszeitVorschlag.zuhaltekraft_t == null
                          ? "–"
                          : `${formatSizingNumber(zykluszeitVorschlag.zuhaltekraft_t)} t`,
                      sizeClass: zykluszeitVorschlag.groessenklasse
                        ? sizeClassLabel(t, zykluszeitVorschlag.groessenklasse)
                        : "–",
                    })}
                  </div>
                  {zykluszeitVorschlag.hinweis ? (
                    <p className="mt-2 text-xs text-amber-800">{zykluszeitVorschlag.hinweis}</p>
                  ) : null}
                  {(zykluszeitVorschlag.warnungen ?? []).map((warnung) => (
                    <p key={warnung} className="mt-2 text-xs text-amber-800">
                      {warnung}
                    </p>
                  ))}
                </>
                )
              ) : (
                <>
                  <p className="text-amber-800">
                    {zykluszeitVorschlag?.hinweis ?? t("spritzguss.estimateAppearsWhen")}
                  </p>
                  {(zykluszeitVorschlag?.warnungen ?? []).map((warnung) => (
                    <p key={warnung} className="mt-2 text-xs text-amber-800">
                      {warnung}
                    </p>
                  ))}
                </>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={uebernehmeZykluszeit}
                disabled={!zykluszeitVorschlag?.kann_uebernommen_werden}
                aria-disabled={!zykluszeitVorschlag?.kann_uebernommen_werden}
                title={
                  zykluszeitVorschlag?.kann_uebernommen_werden
                    ? t("spritzguss.applySuggestionTitle")
                    : t("spritzguss.applySuggestionDisabledTitle")
                }
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {t("spritzguss.apply")}
              </button>
              <span className="text-sm text-gray-600">
                {t("spritzguss.currentCycleTime", {
                  seconds: formatZykluszeitFeld(form.zykluszeit_s),
                  source:
                    form.zykluszeit_quelle === "vorschlag"
                      ? t("spritzguss.fromSuggestion")
                      : t("spritzguss.enteredManually"),
                })}
              </span>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.machineLaborSection")}</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("spritzguss.countryRegion")}</span>
                <select
                  value={selectedLandId ?? ""}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : null;
                    setSelectedLandId(v);
                    setForm((c) => ({ ...c, werk_id: null, maschine_id: null }));
                  }}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("spritzguss.optionalLegacy")}</option>
                  {laender.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.code} – {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="font-medium text-gray-700">{t("spritzguss.plantSite")}</span>
                <select
                  value={form.werk_id ?? ""}
                  onChange={(e) => handleWerkChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("spritzguss.optionalLegacy")}</option>
                  {filteredWerke.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} – {w.name} ({w.currency}, FX {w.fx_to_eur})
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("spritzguss.machineMaster")}</span>
                <select
                  value={form.maschine_id ?? ""}
                  onChange={(e) => handleMaschineChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("project.selectOption")}</option>
                  {filteredMachines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.maschinen_nr} – {m.bezeichnung} ({euro(m.stundensatz)} €/h)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                fieldKey="zykluszeit_s"
                label={t("spritzguss.cycleTimeS")}
                value={form.zykluszeit_s}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="kavitaeten"
                label={t("spritzguss.cavities")}
                value={form.kavitaeten}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="maschinenstundensatz"
                label={t("spritzguss.machineHourlyRate")}
                value={form.maschinenstundensatz}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">{t("spritzguss.productionLabor")}</span>
                <select
                  value={form.lohnkosten_id ?? ""}
                  onChange={(e) => handleLohnChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">{t("project.selectOption")}</option>
                  {filteredLohns.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.bezeichnung}
                      {l.rolle ? ` [${l.rolle}]` : ""} ({euro(l.kosten_pro_stunde)} €/h)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                fieldKey="lohnstundensatz"
                label={t("spritzguss.productionLaborRate")}
                value={form.lohnstundensatz}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="setup_lohnstundensatz"
                label={t("spritzguss.setupLaborRate")}
                value={form.setup_lohnstundensatz}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="setup_zeit_min"
                label={t("spritzguss.setupTimeMin")}
                value={form.setup_zeit_min}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <NumberInput
                fieldKey="setup_mitarbeiter"
                label={t("spritzguss.setupOperators")}
                value={form.setup_mitarbeiter}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
              <div className="md:col-span-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-slate-900">{t("spritzguss.lotSizeForSetup")}</span>
                  <label className="inline-flex items-center gap-2 text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.losgroesse_modus === "manuell"}
                      onChange={(e) =>
                        setForm((current) => ({
                          ...current,
                          losgroesse_modus: e.target.checked ? "manuell" : "automatisch",
                          losgroesse_manuell:
                            e.target.checked && current.losgroesse_manuell == null
                              ? current.losgroesse
                              : current.losgroesse_manuell,
                        }))
                      }
                    />
                    {t("spritzguss.overrideLotSizeManual")}
                  </label>
                </div>
                {form.losgroesse_modus === "automatisch" ? (
                  <p className="text-slate-600">
                    {t("spritzguss.modeAutomatic")}
                    {losgroessePreview.aktiv != null ? (
                      <>
                        {" "}
                        {t("spritzguss.calculatedLotSize", {
                          pieces: losgroessePreview.aktiv.toLocaleString("de-DE"),
                        })}
                      </>
                    ) : (
                      t("spritzguss.notYetCalculable")
                    )}
                  </p>
                ) : (
                  <NumberInput
                    fieldKey="losgroesse_manuell"
                    label={t("spritzguss.manualLotSize")}
                    value={form.losgroesse_manuell ?? 0}
                    decimalRaw={decimalRaw}
                    onDecimalChange={handleDecimalChange}
                  />
                )}
                <dl className="mt-2 space-y-1 text-xs text-slate-600">
                  <div className="flex justify-between gap-3">
                    <dt>{t("spritzguss.avgAnnualDemand")}</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {jahresbedarfLoading
                        ? "…"
                        : jahresbedarf != null
                          ? jahresbedarf.toLocaleString("de-DE")
                          : "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>{t("spritzguss.productionInterval")}</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {t("spritzguss.workdays", { days: losgroessePreview.intervall })}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>{t("spritzguss.workdaysPerYear")}</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {losgroessePreview.arbeitstage ?? "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>{t("spritzguss.automaticLotSize")}</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {losgroessePreview.auto != null
                        ? losgroessePreview.auto.toLocaleString("de-DE")
                        : "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>{t("spritzguss.activeLotSize")}</dt>
                    <dd className="tabular-nums font-semibold text-slate-900">
                      {losgroessePreview.aktiv != null
                        ? losgroessePreview.aktiv.toLocaleString("de-DE")
                        : "–"}{" "}
                      ({losgroessePreview.quelle === "manuell"
                        ? t("spritzguss.manual")
                        : t("spritzguss.automatic")}
                      )
                    </dd>
                  </div>
                </dl>
                {jahresbedarfHint ? (
                  <p className="mt-2 text-xs text-slate-500">{jahresbedarfHint}</p>
                ) : null}
                <p className="mt-2 text-xs text-slate-500">
                  {t("spritzguss.noEoqNote")}
                </p>
              </div>
              <NumberInput
                fieldKey="setup_maschinenstundensatz"
                label={t("spritzguss.setupMachineRate")}
                value={form.setup_maschinenstundensatz}
                decimalRaw={decimalRaw}
                onDecimalChange={handleDecimalChange}
              />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.finishingSteps")}</h3>
            <p className="mb-3 text-sm text-gray-600">
              {t("spritzguss.finishingIntro")}
            </p>

            {veredelungPool.length === 0 ? (
              <p className="text-sm text-gray-500">
                {t("spritzguss.noActiveFinishing")}
              </p>
            ) : (
              <div className="mb-4 flex flex-wrap gap-2">
                {veredelungPool
                  .filter(
                    (s) =>
                      !selectedVeredelung.some((sel) => sel.veredelungsschritt_id === s.id),
                  )
                  .map((schritt) => (
                    <button
                      key={schritt.id}
                      type="button"
                      disabled={!canWrite}
                      onClick={() => addVeredelungSchritt(schritt)}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      + {schritt.bezeichnung} ({schritt.veredelungsart})
                    </button>
                  ))}
              </div>
            )}

            {selectedVeredelung.length === 0 ? (
              <p className="text-sm text-gray-500">{t("spritzguss.noFinishingSelected")}</p>
            ) : (
              <ul className="space-y-2">
                {[...selectedVeredelung]
                  .sort((a, b) => a.reihenfolge - b.reihenfolge)
                  .map((schritt) => (
                    <li
                      key={schritt.veredelungsschritt_id}
                      className="flex flex-wrap items-center gap-3 rounded border border-gray-100 bg-gray-50 px-3 py-2 text-sm"
                    >
                      <span className="font-medium text-gray-500">#{schritt.reihenfolge}</span>
                      <span className="font-medium text-gray-900">{schritt.bezeichnung}</span>
                      <span className="text-gray-500">{schritt.veredelungsart}</span>
                      <span className="tabular-nums text-gray-700">
                        {euro(schritt.kosten_gesamt ?? schritt.kosten_inkl_ausschuss * schritt.mengenfaktor)} €
                      </span>
                      <label className="inline-flex items-center gap-1 text-xs">
                        <input
                          type="checkbox"
                          checked={schritt.aktiv}
                          disabled={!canWrite}
                          onChange={(e) =>
                            setSelectedVeredelung((current) =>
                              current.map((s) =>
                                s.veredelungsschritt_id === schritt.veredelungsschritt_id
                                  ? { ...s, aktiv: e.target.checked }
                                  : s,
                              ),
                            )
                          }
                        />
                        {t("common.active")}
                      </label>
                      <label className="inline-flex items-center gap-1 text-xs">
                        {t("spritzguss.factor")}
                        <input
                          type="number"
                          min={0}
                          step="0.01"
                          disabled={!canWrite}
                          value={schritt.mengenfaktor}
                          onChange={(e) =>
                            setSelectedVeredelung((current) =>
                              current.map((s) =>
                                s.veredelungsschritt_id === schritt.veredelungsschritt_id
                                  ? { ...s, mengenfaktor: Number(e.target.value) }
                                  : s,
                              ),
                            )
                          }
                          className="w-16 rounded border border-gray-300 px-1 py-0.5"
                        />
                      </label>
                      {canWrite && (
                        <>
                          <button
                            type="button"
                            onClick={() => moveVeredelung(schritt.veredelungsschritt_id, "up")}
                            className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            onClick={() => moveVeredelung(schritt.veredelungsschritt_id, "down")}
                            className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            onClick={() => removeVeredelungSchritt(schritt.veredelungsschritt_id)}
                            className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700"
                          >
                            {t("common.remove")}
                          </button>
                        </>
                      )}
                    </li>
                  ))}
              </ul>
            )}

            <p className="mt-3 text-sm">
              <span className="text-gray-600">{t("spritzguss.finishingCostActiveTotal")} </span>
              <span className="font-semibold tabular-nums">{euro(veredelungGesamtAktiv)} €</span>
            </p>
          </section>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.markupsAuto")}</h3>
            <p className="text-sm text-gray-600">
              {t("spritzguss.markupsBody", { source: t("spritzguss.markupsSource") })}
            </p>
          </section>
        </form>

        <aside className="space-y-4">
          {teilbildPreview ? (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.partImage")}</h3>
              <div className="flex justify-center overflow-hidden rounded-md border border-gray-200 bg-slate-50 p-2">
                <img
                  src={teilbildPreview}
                  alt={t("spritzguss.partImageAlt", {
                    name: form.teilenummer || form.teilebezeichnung || "",
                  }).trim()}
                  className="max-h-48 max-w-full object-contain"
                />
              </div>
            </section>
          ) : null}
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">{t("spritzguss.result")}</h3>
            {!bloecke ? (
              <p className="text-sm text-gray-500">{t("spritzguss.noResultYet")}</p>
            ) : (
              <div className="space-y-4">
                {ergebnisUebersicht && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                      {t("spritzguss.resultOverview")}
                    </h4>
                    <p className="mb-3 text-xs text-slate-500">
                      {t("spritzguss.resultOverviewHint")}
                    </p>
                    <dl className="space-y-1 text-sm">
                      {ERGEBNISUEBERSICHT.map(({ key, labelKey, emphasis, hideZero }) => {
                        const value = ergebnisUebersicht[key];
                        if (value == null) return null;
                        const num = typeof value === "number" ? value : Number(value);
                        if (hideZero && (!Number.isFinite(num) || num === 0)) return null;
                        return (
                          <div
                            key={key}
                            className={`flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-b py-1.5 ${ergebnisUebersichtRowClass(emphasis)}`}
                          >
                            <dt
                              className={`min-w-0 flex-1 basis-[55%] sm:basis-auto ${ergebnisUebersichtLabelClass(emphasis)}`}
                            >
                              {t(labelKey)}
                            </dt>
                            <dd
                              className={`shrink-0 text-right ${ergebnisUebersichtValueClass(emphasis)}`}
                            >
                              {euro(Number.isFinite(num) ? num : Number(value))}
                            </dd>
                          </div>
                        );
                      })}
                    </dl>
                  </div>
                )}

                <div className="border-t border-gray-200 pt-4">
                  <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("spritzguss.detailSections")}
                  </h4>
                  {DETAIL_BLOCK_ORDER.filter((blockKey) => bloecke[blockKey]).map((blockKey) => {
                    const fields = bloecke[blockKey];
                    if (!fields) return null;
                    return (
                      <div key={blockKey} className="mb-4">
                        <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                          {blockLabel(t, blockKey)}
                        </h4>
                        <dl className="space-y-1 text-sm">
                          {Object.entries(fields).map(([field, value]) => {
                            const label =
                              blockKey === "veredelung"
                                ? veredelungDetailLabel(t, field, selectedVeredelung)
                                : fieldLabel(t, field);
                            return (
                              <div
                                key={field}
                                className="flex justify-between gap-3 border-b border-gray-100 py-1"
                              >
                                <dt className="text-gray-600">{label}</dt>
                                <dd className="font-medium tabular-nums text-gray-900">
                                  {formatDetailValue(field, value)}
                                </dd>
                              </div>
                            );
                          })}
                        </dl>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
