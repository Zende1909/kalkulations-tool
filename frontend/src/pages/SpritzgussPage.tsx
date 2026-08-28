import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import {
  berechnen,
  createKalkulation,
  deleteKalkulation,
  getKalkulation,
  listKalkulationen,
  updateKalkulation,
} from "../api/spritzguss";
import {
  downloadReport,
  spritzgussPdfUrl,
  spritzgussXlsxUrl,
} from "../api/reports";
import { listVeredelungsschritte } from "../api/veredelung";
import { getAverageJahresstueckzahl } from "../api/hierarchy";
import { ExportButtons } from "../components/ExportButtons";
import {
  HierarchySelector,
  type HierarchySelection,
} from "../components/hierarchy/HierarchySelector";
import { useAuth } from "../context/AuthContext";
import type { Lohnkosten, Land, Maschine, Material, Werk } from "../types/stammdaten";
import type { Veredelungsschritt } from "../types/veredelung";
import {
  emptySpritzgussForm,
  type SpritzgussBloecke,
  type SpritzgussFormData,
  type SpritzgussListItem,
  type VeredelungZuordnung,
  type VeredelungZuordnungInput,
  type WerkzeugAbrechnungsart,
} from "../types/spritzguss";
import { DecimalInputField } from "../components/DecimalInputField";
import {
  formatDecimalForInputDe,
  formatPercentPoints,
  parseDecimalInput,
  parsePercentPointsInput,
  PercentPointsParseError,
} from "../utils/decimalInput";
import {
  berechneAutomatischeLosgroesse,
  inferLegacyLosgroesseModus,
  werkProduktionsintervall,
} from "../utils/losgroesseBerechnung";

interface SelectedVeredelung extends VeredelungZuordnungInput {
  bezeichnung: string;
  veredelungsart: string;
  kosten_inkl_ausschuss: number;
  kosten_gesamt?: number;
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

const BLOCK_LABELS: Record<string, string> = {
  material: "Material",
  fertigung: "Fertigung",
  veredelung: "Veredelung",
  gemeinkosten: "Gemeinkosten / Selbstkosten",
  verkaufspreis: "Verkaufspreis",
};

const DETAIL_BLOCK_ORDER = [
  "material",
  "fertigung",
  "veredelung",
  "gemeinkosten",
  "verkaufspreis",
] as const;

const ERGEBNISUEBERSICHT: Array<{
  key: string;
  label: string;
  /** primary = zentrale Kostenbasis (Selbstkosten); secondary = finales Ergebnis (Endpreis) */
  emphasis?: "primary" | "secondary";
  /** Zeile ausblenden, wenn Wert 0 / fehlend (keine Null-Zeilen für Setup/Veredelung). */
  hideZero?: boolean;
}> = [
  // Additive Aufbauzeilen – FGK nur einmal vor den Herstellkosten
  { key: "materialkosten_gesamt", label: "Material inkl. Ausschuss + MGK (€)" },
  { key: "maschinenkosten", label: "Maschinenkosten je Gutteil (€)" },
  { key: "fertigungslohn", label: "Fertigungslohn je Gutteil (€)" },
  { key: "setup_kosten_je_teil", label: "Setup-Kosten je Teil (€)", hideZero: true },
  { key: "veredelung_gesamt", label: "Veredelungskosten direkt (€)", hideZero: true },
  {
    key: "fgk_basis",
    label: "FGK-Basis (Maschine + Lohn + Setup + Veredelung) (€)",
  },
  { key: "fertigungsgemeinkosten", label: "FGK-Betrag (einmal) (€)" },
  {
    key: "gesamte_herstellkosten",
    label: "Herstellkosten (= Summe inkl. FGK) (€)",
  },
  { key: "vvgk", label: "SG&A / VVGK (€)" },
  { key: "selbstkosten", label: "Selbstkosten (€)", emphasis: "primary" },
  { key: "gewinn", label: "Profit / Gewinn (€)" },
  { key: "nettoverkaufspreis_gesamt", label: "Nettoverkaufspreis (€)" },
  { key: "skonto", label: "Skonto (€)", hideZero: true },
  { key: "endpreis_je_stueck", label: "Endpreis je Stück (€)", emphasis: "secondary" },
  // Nur bei Veredelung: Spritzguss-HK enthält bereits anteilige FGK – kein Summand
  {
    key: "spritzguss_herstellkosten",
    label: "davon Spritzguss-HK inkl. FGK (ohne Veredelung) (€)",
  },
];

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

const FIELD_LABELS: Record<string, string> = {
  materialgewicht_kg: "Materialgewicht aus Schussgewicht (kg)",
  materialkosten: "Materialkosten aus Schussgewicht (€)",
  materialkosten_inkl_ausschuss: "Materialkosten inkl. Prozessausschuss / MGK-Basis (€)",
  materialausschuss_betrag: "Materialausschuss (€)",
  materialgemeinkosten: "Materialgemeinkosten MGK (€)",
  materialkosten_gesamt: "Materialkosten inkl. MGK (€)",
  mgk_basis: "MGK-Basis (Material inkl. Ausschuss) (€)",
  mgk_pct: "MGK-Satz (%)",
  material_nominierung: "Material-Nominierung",
  maschinenkosten: "Maschinenkosten je Gutteil (€)",
  fertigungslohn: "Fertigungslohn je Gutteil (€)",
  fertigungsgemeinkosten: "Fertigungsgemeinkosten FGK (einmal) (€)",
  fgk_basis: "FGK-Basis (Maschine + Lohn + Setup + Veredelung) (€)",
  fgk_pct: "FGK-Satz (%)",
  bruttokapazitaet_exakt: "Bruttokapazität exakt (Stück/h)",
  bruttokapazitaet: "Bruttokapazität kalkulatorisch ROUND (Stück/h)",
  nettokapazitaet: "Nettokapazität nach Ausschuss (Stück/h)",
  setup_maschinenkosten_je_teil: "Setup-Maschinenkosten je Teil (Anteil, gerundet) (€)",
  setup_lohnkosten_je_teil: "Setup-Lohnkosten je Teil (Anteil, gerundet) (€)",
  setup_kosten_je_teil: "Setup-Gesamtkosten je Teil (€)",
  losgroesse: "Aktive Losgröße (Stück)",
  losgroesse_modus: "Losgrößen-Quelle",
  losgroesse_automatisch: "Automatische Losgröße (Stück)",
  losgroesse_aktiv: "Aktive Losgröße (Stück)",
  losgroesse_jahresbedarf: "Durchschnittlicher Jahresbedarf (Stück)",
  produktionsintervall_arbeitstage: "Produktionsintervall (Arbeitstage)",
  arbeitstage_pro_jahr: "Arbeitstage pro Jahr",
  losgroesse_hinweis: "Losgrößen-Hinweis",
  vvgk_pct: "VVGK-Satz (%)",
  gewinn_pct: "Gewinn-Satz (%)",
  skonto_pct: "Skonto-Satz (%)",
  vvgk_basis: "VVGK-Basis / Herstellkosten (€)",
  gewinn_basis: "Gewinn-Basis / Selbstkosten (€)",
  werkzeugkostenanteil: "Werkzeugkostenanteil je Stück (€)",
  werkzeug_einmalzahlung: "Einmalzahlung / Investition (€)",
  herstellkosten: "Herstellkosten inkl. FGK (€)",
  vvgk: "VVGK / SG&A (€)",
  selbstkosten: "Selbstkosten (€)",
  gewinn: "Gewinn (€)",
  nettoverkaufspreis: "Nettoverkaufspreis (€)",
  skonto: "Skonto (€)",
  verkaufspreis: "Endpreis je Stück (€)",
};

function veredelungDetailLabel(
  field: string,
  selectedVeredelung: SelectedVeredelung[],
): string {
  if (field === "veredelung_gesamt") return "Veredelungskosten gesamt (€)";
  const match = /^schritt_(\d+)$/.exec(field);
  if (!match) return field;
  const schritt = selectedVeredelung.find((s) => s.reihenfolge === Number(match[1]));
  return schritt ? `${schritt.bezeichnung} (€)` : `Veredelungsschritt ${match[1]} (€)`;
}

function NumberInput({
  label,
  value,
  onChange,
  step = "0.01",
  min,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: string;
  min?: number;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      <input
        type="text"
        inputMode="decimal"
        step={step}
        min={min}
        value={Number.isFinite(value) ? String(value) : ""}
        onChange={(e) => {
          const parsed = parseDecimalInput(e.target.value);
          if (parsed === "") {
            onChange(0);
            return;
          }
          if (typeof parsed === "number" && Number.isFinite(parsed)) {
            onChange(parsed);
          }
        }}
        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
      />
    </label>
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

export function SpritzgussPage() {
  const { canWrite } = useAuth();
  const [form, setForm] = useState<SpritzgussFormData>(emptySpritzgussForm());
  const [ausschussquoteRaw, setAusschussquoteRaw] = useState("0");
  const [hierarchy, setHierarchy] = useState<HierarchySelection>({
    customer_id: null,
    program_id: null,
    project_id: null,
  });
  const [legacyHierarchy, setLegacyHierarchy] = useState<{
    kunde: string;
    projekt: string;
    jahresstueckzahl: number;
    calculation_year?: number | null;
  } | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [bloecke, setBloecke] = useState<SpritzgussBloecke | null>(null);
  const [list, setList] = useState<SpritzgussListItem[]>([]);
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

  const setField = <K extends keyof SpritzgussFormData>(key: K, value: SpritzgussFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

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

  const loadList = useCallback(async () => {
    const items = await listKalkulationen();
    setList(items);
  }, []);

  useEffect(() => {
    Promise.all([loadStammdaten(), loadList()]).catch((err) => {
      setError(err instanceof Error ? err.message : "Stammdaten konnten nicht geladen werden");
    });
  }, [loadList, loadStammdaten]);

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
          ? "Jahresbedarf wird nach Projektauswahl aus den Projektstückzahlen berechnet."
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
            "Für dieses Projekt sind keine Jahresstückzahlen hinterlegt – automatische Losgröße nicht berechenbar.",
          );
          return;
        }
        setJahresbedarf(avg.jahresstueckzahl);
        setJahresbedarfHint(
          `Durchschnittlicher Jahresbedarf: ⌈Summe / ${avg.year_count} Jahre⌉ = ${avg.jahresstueckzahl.toLocaleString("de-DE")} Stück`,
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setJahresbedarf(null);
          setJahresbedarfHint(
            err instanceof Error ? err.message : "Jahresbedarf konnte nicht geladen werden.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setJahresbedarfLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hierarchy.project_id, hierarchy.customer_id, hierarchy.program_id, form.project_id]);

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

  const calcPayloadBase = useMemo(
    () => ({
      teilegewicht_netto_g: form.teilegewicht_netto_g,
      schussgewicht_g: form.schussgewicht_g,
      materialpreis_pro_kg: form.materialpreis_pro_kg,
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
    if (form.werk_id == null) return machines.filter((m) => m.werk_id == null || !m.werk_id);
    return machines.filter((m) => m.werk_id === form.werk_id);
  }, [machines, form.werk_id]);

  const filteredLohns = useMemo(() => {
    if (form.werk_id == null) return lohns;
    return lohns.filter((l) => l.werk_id === form.werk_id || l.werk_id == null);
  }, [lohns, form.werk_id]);

  const handleWerkChange = (id: string) => {
    if (!id) {
      setForm((current) => ({
        ...current,
        werk_id: null,
        maschine_id: null,
        lohnkosten_id: null,
      }));
      return;
    }
    const wid = Number(id);
    const plant = werke.find((w) => w.id === wid);
    const prod = lohns.find((l) => l.werk_id === wid && l.rolle === "produktion");
    const setup = lohns.find((l) => l.werk_id === wid && l.rolle === "setup");
    setForm((current) => ({
      ...current,
      werk_id: wid,
      maschine_id: null,
      lohnkosten_id: prod?.id ?? null,
      lohnstundensatz: prod?.kosten_pro_stunde ?? current.lohnstundensatz,
      setup_lohnstundensatz: setup?.kosten_pro_stunde ?? current.setup_lohnstundensatz,
    }));
    if (plant) {
      setSelectedLandId(plant.land_id);
    }
  };

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
  };

  const handleMaschineChange = (id: string) => {
    if (!id) {
      setField("maschine_id", null);
      return;
    }
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
  };

  const resolveAusschussquotePct = (): number => parsePercentPointsInput(ausschussquoteRaw);

  const handleBerechnen = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const ausschussquote_pct = resolveAusschussquotePct();
      const result = await berechnen({ ...calcPayloadBase, ausschussquote_pct });
      setBloecke(result.bloecke);
      updateSelectedFromResponse(result.veredelung_zuordnungen);
      setSuccess("Berechnung erfolgreich.");
    } catch (err) {
      setError(
        err instanceof PercentPointsParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Berechnung fehlgeschlagen",
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
      const ausschussquote_pct = resolveAusschussquotePct();
      if (!form.teilebezeichnung.trim()) {
        throw new Error("Teilebezeichnung ist für das Speichern erforderlich.");
      }
      if (!form.teilenummer.trim()) {
        throw new Error("Teilenummer ist für das Speichern erforderlich.");
      }
      if (!legacyHierarchy && hierarchy.project_id == null) {
        throw new Error("Bitte Kunde, Programm und Projekt auswählen.");
      }
      const payload = {
        ...form,
        ausschussquote_pct,
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
      loadVeredelungFromSaved(saved.veredelung_zuordnungen);
      setSuccess(
        wasNew
          ? `Kalkulation #${saved.id} gespeichert.`
          : `Kalkulation #${saved.id} aktualisiert.`,
      );
      await loadList();
    } catch (err) {
      setError(
        err instanceof PercentPointsParseError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Speichern fehlgeschlagen",
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
      });
      if (item.werk_id != null) {
        const plant = werke.find((w) => w.id === item.werk_id);
        if (plant) setSelectedLandId(plant.land_id);
      } else {
        setSelectedLandId(null);
      }
      setAusschussquoteRaw(formatDecimalForInputDe(item.ausschussquote_pct));
      setBloecke((item.ergebnis_bloecke as SpritzgussBloecke) ?? null);
      loadVeredelungFromSaved(item.veredelung_zuordnungen);
      setSuccess(`Kalkulation #${item.id} geladen.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleNew = () => {
    setEditId(null);
    setForm(emptySpritzgussForm());
    setAusschussquoteRaw("0");
    setHierarchy({
      customer_id: null,
      program_id: null,
      project_id: null,
    });
    setLegacyHierarchy(null);
    setSelectedVeredelung([]);
    setBloecke(null);
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
      setSuccess(`Export ${format.toUpperCase()} erfolgreich.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
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
      await loadList();
      setSuccess("Kalkulation gelöscht.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Einzelteilkalkulation</h2>
          <p className="mt-1 text-sm text-gray-600">
            Zuschlagskalkulation für Kunststoff-Einzelteile. Preise und Sätze aus den Stammdaten
            werden vorausgefüllt und können je Kalkulation überschrieben werden.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleNew}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Neue Kalkulation
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleBerechnen}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
          >
            Berechnen
          </button>
          {canWrite && (
            <button
              type="button"
              disabled={busy}
              onClick={handleSave}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              Kalkulation speichern
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
          Bearbeite gespeicherte Kalkulation <strong>#{editId}</strong>
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <form id="spritzguss-form" className="space-y-6" onSubmit={(e) => e.preventDefault()}>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Allgemeine Daten</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <TextInput
                label="Teilebezeichnung"
                value={form.teilebezeichnung}
                onChange={(v) => setField("teilebezeichnung", v)}
              />
              <TextInput
                label="Teilenummer"
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
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Material</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">Material (Stammdaten)</span>
                <select
                  value={form.material_id ?? ""}
                  onChange={(e) => handleMaterialChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– auswählen –</option>
                  {materials.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.material_nr} – {m.bezeichnung} ({euro(m.preis_pro_kg)} €/kg)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                label="Schussgewicht / Brutto (g) – Materialbasis"
                value={form.schussgewicht_g}
                min={0}
                onChange={(v) => setField("schussgewicht_g", v)}
              />
              <NumberInput
                label="Teilegewicht netto (g) – nur Information"
                value={form.teilegewicht_netto_g}
                min={0}
                onChange={(v) => setField("teilegewicht_netto_g", v)}
              />
              <DecimalInputField
                label="Ausschussquote (%)"
                rawValue={ausschussquoteRaw}
                onRawChange={setAusschussquoteRaw}
              />
              <NumberInput
                label="Materialpreis (€/kg, überschreibbar)"
                value={form.materialpreis_pro_kg}
                min={0}
                onChange={(v) => setField("materialpreis_pro_kg", v)}
              />
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">Material-Nominierung (MGK)</span>
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
                  <option value="">– bitte wählen –</option>
                  <option value="selbstnominiert">selbstnominiert (MGK aus Stammdaten)</option>
                  <option value="oem_nominiert">OEM-nominiert (MGK aus Stammdaten)</option>
                </select>
                {!form.material_nominierung && (
                  <p className="mt-1 text-xs text-amber-800">
                    Ohne Nominierung kann die Kalkulation nicht berechnet werden. Bitte
                    selbstnominiert oder OEM-nominiert wählen (Prozentsätze nur unter Stammdaten
                    → Zuschlagssätze).
                  </p>
                )}
              </label>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Maschine & Lohn</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm">
                <span className="font-medium text-gray-700">Land / Region</span>
                <select
                  value={selectedLandId ?? ""}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : null;
                    setSelectedLandId(v);
                    setForm((c) => ({ ...c, werk_id: null, maschine_id: null }));
                  }}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– optional / Legacy –</option>
                  {laender.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.code} – {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="font-medium text-gray-700">Werk / Standort</span>
                <select
                  value={form.werk_id ?? ""}
                  onChange={(e) => handleWerkChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– optional / Legacy –</option>
                  {filteredWerke.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} – {w.name} ({w.currency}, FX {w.fx_to_eur})
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">Maschine (Stammdaten)</span>
                <select
                  value={form.maschine_id ?? ""}
                  onChange={(e) => handleMaschineChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– auswählen –</option>
                  {filteredMachines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.maschinen_nr} – {m.bezeichnung} ({euro(m.stundensatz)} €/h)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                label="Zykluszeit (s)"
                value={form.zykluszeit_s}
                min={0}
                onChange={(v) => setField("zykluszeit_s", v)}
              />
              <NumberInput
                label="Kavitäten"
                value={form.kavitaeten}
                min={1}
                step="1"
                onChange={(v) => setField("kavitaeten", v)}
              />
              <NumberInput
                label="Maschinenstundensatz (€/h, überschreibbar)"
                value={form.maschinenstundensatz}
                min={0}
                onChange={(v) => setField("maschinenstundensatz", v)}
              />
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">Lohnkosten Produktion</span>
                <select
                  value={form.lohnkosten_id ?? ""}
                  onChange={(e) => handleLohnChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– auswählen –</option>
                  {filteredLohns.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.bezeichnung}
                      {l.rolle ? ` [${l.rolle}]` : ""} ({euro(l.kosten_pro_stunde)} €/h)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                label="Lohnstundensatz Produktion (€/h)"
                value={form.lohnstundensatz}
                min={0}
                onChange={(v) => setField("lohnstundensatz", v)}
              />
              <NumberInput
                label="Setup-Lohnsatz (€/h)"
                value={form.setup_lohnstundensatz}
                min={0}
                onChange={(v) => setField("setup_lohnstundensatz", v)}
              />
              <NumberInput
                label="Setup-Zeit (min)"
                value={form.setup_zeit_min}
                min={0}
                onChange={(v) => setField("setup_zeit_min", v)}
              />
              <NumberInput
                label="Setup-Mitarbeiter"
                value={form.setup_mitarbeiter}
                min={0}
                onChange={(v) => setField("setup_mitarbeiter", v)}
              />
              <div className="md:col-span-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-slate-900">Losgröße für Setup-Umlage</span>
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
                    Losgröße manuell überschreiben
                  </label>
                </div>
                {form.losgroesse_modus === "automatisch" ? (
                  <p className="text-slate-600">
                    Modus: <span className="font-medium">automatisch</span>
                    {losgroessePreview.aktiv != null ? (
                      <>
                        {" "}
                        – berechnete Losgröße:{" "}
                        <span className="font-semibold tabular-nums">
                          {losgroessePreview.aktiv.toLocaleString("de-DE")} Stück
                        </span>
                      </>
                    ) : (
                      " – noch nicht berechenbar"
                    )}
                  </p>
                ) : (
                  <NumberInput
                    label="Manuelle Losgröße (Stück)"
                    value={form.losgroesse_manuell ?? 0}
                    min={1}
                    step="1"
                    onChange={(v) =>
                      setField("losgroesse_manuell", v >= 1 ? Math.round(v) : null)
                    }
                  />
                )}
                <dl className="mt-2 space-y-1 text-xs text-slate-600">
                  <div className="flex justify-between gap-3">
                    <dt>Durchschnittlicher Jahresbedarf</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {jahresbedarfLoading
                        ? "…"
                        : jahresbedarf != null
                          ? jahresbedarf.toLocaleString("de-DE")
                          : "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Produktionsintervall</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {losgroessePreview.intervall} Arbeitstage
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Arbeitstage pro Jahr</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {losgroessePreview.arbeitstage ?? "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Automatische Losgröße</dt>
                    <dd className="tabular-nums font-medium text-slate-800">
                      {losgroessePreview.auto != null
                        ? losgroessePreview.auto.toLocaleString("de-DE")
                        : "–"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt>Aktive Losgröße</dt>
                    <dd className="tabular-nums font-semibold text-slate-900">
                      {losgroessePreview.aktiv != null
                        ? losgroessePreview.aktiv.toLocaleString("de-DE")
                        : "–"}{" "}
                      ({losgroessePreview.quelle})
                    </dd>
                  </div>
                </dl>
                {jahresbedarfHint ? (
                  <p className="mt-2 text-xs text-slate-500">{jahresbedarfHint}</p>
                ) : null}
                <p className="mt-2 text-xs text-slate-500">
                  Keine EOQ-/Andler-Losgröße – basiert auf Produktionsintervall am Werk.
                </p>
              </div>
              <NumberInput
                label="Setup-Maschinenstundensatz (€/h)"
                value={form.setup_maschinenstundensatz}
                min={0}
                onChange={(v) => setField("setup_maschinenstundensatz", v)}
              />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Veredelungsschritte</h3>
            <p className="mb-3 text-sm text-gray-600">
              Aktive Veredelungsschritte auswählen und in der gewünschten Reihenfolge anordnen.
            </p>

            {veredelungPool.length === 0 ? (
              <p className="text-sm text-gray-500">
                Keine aktiven Veredelungsschritte vorhanden. Bitte zuerst unter Veredelung anlegen.
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
              <p className="text-sm text-gray-500">Keine Veredelungsschritte ausgewählt.</p>
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
                        aktiv
                      </label>
                      <label className="inline-flex items-center gap-1 text-xs">
                        Faktor
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
                            Entfernen
                          </button>
                        </>
                      )}
                    </li>
                  ))}
              </ul>
            )}

            <p className="mt-3 text-sm">
              <span className="text-gray-600">Veredelungskosten gesamt (aktiv): </span>
              <span className="font-semibold tabular-nums">{euro(veredelungGesamtAktiv)} €</span>
            </p>
          </section>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Zuschläge (automatisch)</h3>
            <p className="text-sm text-gray-600">
              Material-MGK (laut Nominierung), FGK, SG&A/VVGK, Gewinn und Skonto kommen zentral aus{" "}
              <span className="font-medium">Stammdaten → Zuschlagssätze</span>. Material-MGK bezieht
              sich auf die Materialkosten inklusive Ausschuss; Kaufteil-MGK auf den Einkaufspreis.
              Die Beträge und Kostenbasen erscheinen in der Ergebnisübersicht.
            </p>
          </section>
        </form>

        <aside className="space-y-4">
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Ergebnis</h3>
            {!bloecke ? (
              <p className="text-sm text-gray-500">Noch keine Berechnung. „Berechnen“ wählen.</p>
            ) : (
              <div className="space-y-4">
                {ergebnisUebersicht && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                      Ergebnisübersicht
                    </h4>
                    <p className="mb-3 text-xs text-slate-500">
                      Aufbau additiv: FGK wird genau einmal auf die FGK-Basis berechnet und in
                      den Herstellkosten mitgezählt – nicht erneut zu den Spritzguss-HK addieren.
                    </p>
                    <dl className="space-y-1 text-sm">
                      {ERGEBNISUEBERSICHT.map(({ key, label, emphasis, hideZero }) => {
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
                              {label}
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
                    Detailbereiche
                  </h4>
                  {DETAIL_BLOCK_ORDER.filter((blockKey) => bloecke[blockKey]).map((blockKey) => {
                    const fields = bloecke[blockKey];
                    if (!fields) return null;
                    return (
                      <div key={blockKey} className="mb-4">
                        <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                          {BLOCK_LABELS[blockKey] ?? blockKey}
                        </h4>
                        <dl className="space-y-1 text-sm">
                          {Object.entries(fields).map(([field, value]) => {
                            const label =
                              blockKey === "veredelung"
                                ? veredelungDetailLabel(field, selectedVeredelung)
                                : FIELD_LABELS[field] ?? field;
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

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Gespeicherte Kalkulationen</h3>
            {list.length === 0 ? (
              <p className="text-sm text-gray-500">Noch keine gespeicherten Kalkulationen.</p>
            ) : (
              <ul className="max-h-80 space-y-2 overflow-y-auto text-sm">
                {list.map((item) => (
                  <li
                    key={item.id}
                    className="rounded border border-gray-100 p-2 hover:bg-gray-50"
                  >
                    <div className="font-medium text-gray-900">
                      {item.teilenummer} – {item.teilebezeichnung}
                    </div>
                    <div className="text-xs text-gray-500">
                      {item.kunde || "–"} · VP {euro(item.verkaufspreis)} €
                    </div>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleLoad(item.id)}
                        className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-white"
                      >
                        Öffnen
                      </button>
                      {canWrite && (
                        <button
                          type="button"
                          onClick={() => handleDelete(item.id)}
                          className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                        >
                          Löschen
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
