import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import {
  berechnen,
  createKalkulation,
  deleteKalkulation,
  getKalkulation,
  listKalkulationen,
  updateKalkulation,
} from "../api/spritzguss";
import { useAuth } from "../context/AuthContext";
import type { Lohnkosten, Maschine, Material } from "../types/stammdaten";
import {
  emptySpritzgussForm,
  type SpritzgussBloecke,
  type SpritzgussFormData,
  type SpritzgussListItem,
} from "../types/spritzguss";

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
  gemeinkosten: "Gemeinkosten / Selbstkosten",
  verkaufspreis: "Verkaufspreis",
};

const FIELD_LABELS: Record<string, string> = {
  materialgewicht_kg: "Materialgewicht je Gutteil (kg)",
  materialkosten: "Materialkosten (€)",
  materialkosten_inkl_ausschuss: "Materialkosten inkl. Ausschuss (€)",
  materialgemeinkosten: "Materialgemeinkosten MGK (€)",
  materialkosten_gesamt: "Materialkosten gesamt (€)",
  maschinenkosten: "Maschinenkosten je Teil (€)",
  fertigungslohn: "Fertigungslohn je Teil (€)",
  fertigungsgemeinkosten: "Fertigungsgemeinkosten FGK (€)",
  werkzeugkostenanteil: "Werkzeugkostenanteil (€)",
  herstellkosten: "Herstellkosten (€)",
  vvgk: "VVGK (€)",
  selbstkosten: "Selbstkosten (€)",
  gewinn: "Gewinn (€)",
  nettoverkaufspreis: "Nettoverkaufspreis (€)",
  skonto: "Skonto (€)",
  verkaufspreis: "Verkaufspreis (€)",
};

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
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const setField = <K extends keyof SpritzgussFormData>(key: K, value: SpritzgussFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const loadStammdaten = useCallback(async () => {
    const [mats, masch, lohn] = await Promise.all([
      api.get<Material[]>("/materialien"),
      api.get<Maschine[]>("/maschinen"),
      api.get<Lohnkosten[]>("/lohnkosten"),
    ]);
    setMaterials(mats.filter((m) => m.aktiv));
    setMachines(masch.filter((m) => m.aktiv));
    setLohns(lohn.filter((l) => l.aktiv));
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
      amortisationsvolumen: form.amortisationsvolumen,
      vvgk_pct: form.vvgk_pct,
      gewinn_pct: form.gewinn_pct,
      skonto_pct: form.skonto_pct,
    }),
    [form],
  );

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
      const result = await berechnen(calcPayload);
      setBloecke(result.bloecke);
      setSuccess("Berechnung erfolgreich.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Berechnung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!canWrite) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const saved =
        editId == null
          ? await createKalkulation(form)
          : await updateKalkulation(editId, form);
      setEditId(saved.id);
      setBloecke((saved.ergebnis_bloecke as SpritzgussBloecke) ?? null);
      setSuccess(editId == null ? "Kalkulation gespeichert." : "Kalkulation aktualisiert.");
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
        amortisationsvolumen: item.amortisationsvolumen,
        mgk_pct: item.mgk_pct,
        fgk_pct: item.fgk_pct,
        vvgk_pct: item.vvgk_pct,
        gewinn_pct: item.gewinn_pct,
        skonto_pct: item.skonto_pct,
        notizen: item.notizen,
        aktiv: item.aktiv,
      });
      setBloecke((item.ergebnis_bloecke as SpritzgussBloecke) ?? null);
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
    setBloecke(null);
    setSuccess(null);
    setError(null);
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
              type="submit"
              form="spritzguss-form"
              disabled={busy}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {editId == null ? "Speichern" : "Aktualisieren"}
            </button>
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
        <form id="spritzguss-form" onSubmit={handleSave} className="space-y-6">
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
            <div className="grid gap-3 md:grid-cols-2">
              <NumberInput
                label="Werkzeugkosten (€)"
                value={form.werkzeugkosten_eur}
                min={0}
                onChange={(v) => setField("werkzeugkosten_eur", v)}
              />
              <NumberInput
                label="Amortisationsvolumen (Stück)"
                value={form.amortisationsvolumen}
                min={0.0001}
                step="1"
                onChange={(v) => setField("amortisationsvolumen", v)}
              />
            </div>
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
              <p className="text-sm text-gray-500">Noch keine Berechnung. „Berechnen“ oder „Speichern“ wählen.</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(bloecke).map(([blockKey, fields]) => (
                  <div key={blockKey}>
                    <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                      {BLOCK_LABELS[blockKey] ?? blockKey}
                    </h4>
                    <dl className="space-y-1 text-sm">
                      {Object.entries(fields).map(([field, value]) => (
                        <div key={field} className="flex justify-between gap-3 border-b border-gray-100 py-1">
                          <dt className="text-gray-600">{FIELD_LABELS[field] ?? field}</dt>
                          <dd className="font-medium tabular-nums text-gray-900">
                            {euro(typeof value === "number" ? value : Number(value))}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ))}
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
