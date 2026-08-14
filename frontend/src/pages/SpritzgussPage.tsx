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
import { ExportButtons } from "../components/ExportButtons";
import { useAuth } from "../context/AuthContext";
import type { Lohnkosten, Maschine, Material } from "../types/stammdaten";
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

const BLOCK_LABELS: Record<string, string> = {
  material: "Material",
  fertigung: "Fertigung",
  werkzeug: "Werkzeug",
  veredelung: "Veredelung",
  gemeinkosten: "Gemeinkosten / Selbstkosten",
  verkaufspreis: "Verkaufspreis",
};

const DETAIL_BLOCK_ORDER = [
  "material",
  "fertigung",
  "werkzeug",
  "veredelung",
  "gemeinkosten",
  "verkaufspreis",
] as const;

const ERGEBNISUEBERSICHT: Array<{
  key: string;
  label: string;
  highlight?: boolean;
}> = [
  { key: "spritzguss_herstellkosten", label: "Spritzguss-Herstellkosten (€)" },
  { key: "werkzeugkostenanteil", label: "Werkzeugkostenanteil je Stück (€)" },
  { key: "veredelung_gesamt", label: "Veredelungskosten gesamt (€)" },
  { key: "gesamte_herstellkosten", label: "Gesamte Herstellkosten (€)" },
  { key: "vvgk", label: "VVGK (€)" },
  { key: "selbstkosten", label: "Selbstkosten (€)" },
  { key: "gewinn", label: "Gewinn (€)" },
  { key: "nettoverkaufspreis_gesamt", label: "Nettoverkaufspreis gesamt (€)" },
  { key: "skonto", label: "Skonto (€)" },
  { key: "endpreis_je_stueck", label: "Endpreis je Stück (€)", highlight: true },
];

const FIELD_LABELS: Record<string, string> = {
  materialgewicht_kg: "Materialgewicht je Gutteil (kg)",
  materialkosten: "Materialkosten (€)",
  materialkosten_inkl_ausschuss: "Materialkosten inkl. Ausschuss (€)",
  materialgemeinkosten: "Materialgemeinkosten MGK (€)",
  materialkosten_gesamt: "Materialkosten gesamt (€)",
  maschinenkosten: "Maschinenkosten je Teil (€)",
  fertigungslohn: "Fertigungslohn je Teil (€)",
  fertigungsgemeinkosten: "Fertigungsgemeinkosten FGK (€)",
  werkzeugkostenanteil: "Werkzeugkostenanteil je Stück (€)",
  werkzeug_einmalzahlung: "Einmalzahlung / Investition (€)",
  herstellkosten: "Herstellkosten (€)",
  vvgk: "VVGK (€)",
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
        type="number"
        step={step}
        min={min}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(Number(e.target.value))}
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
  const [editId, setEditId] = useState<number | null>(null);
  const [bloecke, setBloecke] = useState<SpritzgussBloecke | null>(null);
  const [list, setList] = useState<SpritzgussListItem[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [machines, setMachines] = useState<Maschine[]>([]);
  const [lohns, setLohns] = useState<Lohnkosten[]>([]);
  const [veredelungPool, setVeredelungPool] = useState<Veredelungsschritt[]>([]);
  const [selectedVeredelung, setSelectedVeredelung] = useState<SelectedVeredelung[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);

  const setField = <K extends keyof SpritzgussFormData>(key: K, value: SpritzgussFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const loadStammdaten = useCallback(async () => {
    const [mats, masch, lohn, veredelung] = await Promise.all([
      api.get<Material[]>("/materialien"),
      api.get<Maschine[]>("/maschinen"),
      api.get<Lohnkosten[]>("/lohnkosten"),
      listVeredelungsschritte(),
    ]);
    setMaterials(mats.filter((m) => m.aktiv));
    setMachines(masch.filter((m) => m.aktiv));
    setLohns(lohn.filter((l) => l.aktiv));
    setVeredelungPool(veredelung.filter((v) => v.aktiv));
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

  const calcPayload = useMemo(
    () => ({
      teilegewicht_netto_g: form.teilegewicht_netto_g,
      materialpreis_pro_kg: form.materialpreis_pro_kg,
      ausschussquote_pct: form.ausschussquote_pct,
      mgk_pct: form.mgk_pct,
      zykluszeit_s: form.zykluszeit_s,
      maschinenstundensatz: form.maschinenstundensatz,
      kavitaeten: form.kavitaeten,
      lohnstundensatz: form.lohnstundensatz,
      fgk_pct: form.fgk_pct,
      werkzeugkosten_eur: form.werkzeugkosten_eur,
      werkzeug_abrechnungsart: form.werkzeug_abrechnungsart,
      amortisationsvolumen:
        form.werkzeug_abrechnungsart === "amortisation"
          ? form.amortisationsvolumen
          : null,
      vvgk_pct: form.vvgk_pct,
      gewinn_pct: form.gewinn_pct,
      skonto_pct: form.skonto_pct,
      veredelung_zuordnungen: veredelungZuordnungen,
    }),
    [form, veredelungZuordnungen],
  );

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

  const handleBerechnen = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      if (form.werkzeug_abrechnungsart === "amortisation") {
        const vol = form.amortisationsvolumen;
        if (vol == null || !Number.isInteger(vol) || vol < 1) {
          throw new Error(
            "Amortisationsvolumen muss eine positive ganze Zahl >= 1 sein (z. B. 1 oder 20000).",
          );
        }
      }
      const result = await berechnen(calcPayload);
      setBloecke(result.bloecke);
      updateSelectedFromResponse(result.veredelung_zuordnungen);
      setSuccess("Berechnung erfolgreich.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Berechnung fehlgeschlagen");
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
      if (!form.teilebezeichnung.trim()) {
        throw new Error("Teilebezeichnung ist für das Speichern erforderlich.");
      }
      if (!form.teilenummer.trim()) {
        throw new Error("Teilenummer ist für das Speichern erforderlich.");
      }
      if (form.werkzeug_abrechnungsart === "amortisation") {
        const vol = form.amortisationsvolumen;
        if (vol == null || !Number.isInteger(vol) || vol < 1) {
          throw new Error(
            "Amortisationsvolumen muss eine positive ganze Zahl >= 1 sein (z. B. 1 oder 20000).",
          );
        }
      }
      const payload = {
        ...form,
        amortisationsvolumen:
          form.werkzeug_abrechnungsart === "amortisation"
            ? form.amortisationsvolumen
            : null,
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
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
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
      setForm({
        teilebezeichnung: item.teilebezeichnung,
        teilenummer: item.teilenummer,
        kunde: item.kunde,
        projekt: item.projekt,
        jahresstueckzahl: item.jahresstueckzahl,
        material_id: item.material_id,
        schussgewicht_g: item.schussgewicht_g,
        teilegewicht_netto_g: item.teilegewicht_netto_g,
        ausschussquote_pct: item.ausschussquote_pct,
        materialpreis_pro_kg: item.materialpreis_pro_kg,
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
    if (!g || !v) return null;
    const hk = g.herstellkosten ?? 0;
    return {
      spritzguss_herstellkosten: hk,
      veredelung_gesamt: 0,
      gesamte_herstellkosten: hk,
      vvgk: g.vvgk ?? 0,
      selbstkosten: g.selbstkosten ?? 0,
      gewinn: g.gewinn ?? 0,
      nettoverkaufspreis_gesamt: v.nettoverkaufspreis ?? 0,
      skonto: v.skonto ?? 0,
      endpreis_je_stueck: v.verkaufspreis ?? 0,
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
          <h2 className="text-2xl font-bold text-gray-900">Spritzguss-Kalkulation</h2>
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
              <TextInput label="Kunde" value={form.kunde} onChange={(v) => setField("kunde", v)} />
              <TextInput
                label="Projekt"
                value={form.projekt}
                onChange={(v) => setField("projekt", v)}
              />
              <NumberInput
                label="Jahresstückzahl"
                value={form.jahresstueckzahl}
                min={0}
                step="1"
                onChange={(v) => setField("jahresstueckzahl", v)}
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
                label="Schussgewicht (g)"
                value={form.schussgewicht_g}
                min={0}
                onChange={(v) => setField("schussgewicht_g", v)}
              />
              <NumberInput
                label="Teilegewicht netto (g)"
                value={form.teilegewicht_netto_g}
                min={0}
                onChange={(v) => setField("teilegewicht_netto_g", v)}
              />
              <NumberInput
                label="Ausschussquote (%)"
                value={form.ausschussquote_pct}
                min={0}
                onChange={(v) => setField("ausschussquote_pct", v)}
              />
              <NumberInput
                label="Materialpreis (€/kg, überschreibbar)"
                value={form.materialpreis_pro_kg}
                min={0}
                onChange={(v) => setField("materialpreis_pro_kg", v)}
              />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Maschine & Lohn</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm md:col-span-2">
                <span className="font-medium text-gray-700">Maschine (Stammdaten)</span>
                <select
                  value={form.maschine_id ?? ""}
                  onChange={(e) => handleMaschineChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– auswählen –</option>
                  {machines.map((m) => (
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
                <span className="font-medium text-gray-700">Lohnkosten (Stammdaten)</span>
                <select
                  value={form.lohnkosten_id ?? ""}
                  onChange={(e) => handleLohnChange(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                >
                  <option value="">– auswählen –</option>
                  {lohns.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.bezeichnung} ({euro(l.kosten_pro_stunde)} €/h)
                    </option>
                  ))}
                </select>
              </label>
              <NumberInput
                label="Lohnstundensatz (€/h, überschreibbar)"
                value={form.lohnstundensatz}
                min={0}
                onChange={(v) => setField("lohnstundensatz", v)}
              />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Werkzeug</h3>

            <fieldset className="mb-4">
              <legend className="text-sm font-medium text-gray-700">Abrechnungsart</legend>
              <div className="mt-2 flex flex-wrap gap-4">
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="werkzeug_abrechnungsart"
                    checked={form.werkzeug_abrechnungsart === "amortisation"}
                    onChange={() =>
                      setForm((current) => ({
                        ...current,
                        werkzeug_abrechnungsart: "amortisation",
                        amortisationsvolumen:
                          current.amortisationsvolumen != null &&
                          current.amortisationsvolumen >= 1
                            ? Math.round(current.amortisationsvolumen)
                            : 1,
                      }))
                    }
                  />
                  Amortisation
                </label>
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="werkzeug_abrechnungsart"
                    checked={form.werkzeug_abrechnungsart === "einmalzahlung"}
                    onChange={() =>
                      setForm((current) => ({
                        ...current,
                        werkzeug_abrechnungsart: "einmalzahlung",
                        amortisationsvolumen: null,
                      }))
                    }
                  />
                  Einmalzahlung
                </label>
              </div>
            </fieldset>

            <div className="grid gap-3 md:grid-cols-2">
              <NumberInput
                label={
                  form.werkzeug_abrechnungsart === "einmalzahlung"
                    ? "Einmalzahlung / Werkzeugkosten (€)"
                    : "Werkzeugkosten (€)"
                }
                value={form.werkzeugkosten_eur}
                min={0}
                onChange={(v) => setField("werkzeugkosten_eur", v)}
              />
              {form.werkzeug_abrechnungsart === "amortisation" && (
                <label className="block text-sm">
                  <span className="font-medium text-gray-700">
                    Amortisationsvolumen (Stück)
                  </span>
                  <input
                    type="number"
                    inputMode="numeric"
                    step={1}
                    min={1}
                    required
                    value={form.amortisationsvolumen ?? ""}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (raw === "") {
                        setField("amortisationsvolumen", null);
                        return;
                      }
                      const parsed = Number.parseInt(raw, 10);
                      setField(
                        "amortisationsvolumen",
                        Number.isFinite(parsed) ? parsed : null,
                      );
                    }}
                    className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                  />
                  <span className="mt-1 block text-xs text-gray-500">
                    Positive ganze Zahl, z. B. 1 oder 20000
                  </span>
                </label>
              )}
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
            <h3 className="mb-3 font-semibold text-gray-900">Zuschläge (%)</h3>
            <div className="grid gap-3 md:grid-cols-3">
              <NumberInput label="MGK %" value={form.mgk_pct} min={0} onChange={(v) => setField("mgk_pct", v)} />
              <NumberInput label="FGK %" value={form.fgk_pct} min={0} onChange={(v) => setField("fgk_pct", v)} />
              <NumberInput label="VVGK %" value={form.vvgk_pct} min={0} onChange={(v) => setField("vvgk_pct", v)} />
              <NumberInput
                label="Gewinnzuschlag %"
                value={form.gewinn_pct}
                min={0}
                onChange={(v) => setField("gewinn_pct", v)}
              />
              <NumberInput
                label="Skonto %"
                value={form.skonto_pct}
                min={0}
                onChange={(v) => setField("skonto_pct", v)}
              />
            </div>
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
                    <dl className="space-y-1 text-sm">
                      {ERGEBNISUEBERSICHT.map(({ key, label, highlight }) => {
                        const value = ergebnisUebersicht[key];
                        if (value == null) return null;
                        return (
                          <div
                            key={key}
                            className={`flex justify-between gap-3 border-b py-1.5 ${
                              highlight
                                ? "border-slate-300 bg-white px-2 -mx-2 rounded font-semibold"
                                : "border-gray-100"
                            }`}
                          >
                            <dt className={highlight ? "text-slate-900" : "text-gray-600"}>
                              {label}
                            </dt>
                            <dd
                              className={`tabular-nums ${
                                highlight ? "text-lg text-slate-900" : "font-medium text-gray-900"
                              }`}
                            >
                              {euro(typeof value === "number" ? value : Number(value))}
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
                            if (
                              blockKey === "werkzeug" &&
                              form.werkzeug_abrechnungsart === "amortisation" &&
                              field === "werkzeug_einmalzahlung"
                            ) {
                              return null;
                            }
                            if (
                              blockKey === "werkzeug" &&
                              form.werkzeug_abrechnungsart === "einmalzahlung" &&
                              field === "werkzeugkostenanteil"
                            ) {
                              return null;
                            }
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
                                  {euro(typeof value === "number" ? value : Number(value))}
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
