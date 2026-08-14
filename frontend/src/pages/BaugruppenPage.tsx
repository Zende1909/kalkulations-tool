import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  berechnen,
  createBaugruppe,
  deleteBaugruppe,
  getBaugruppe,
  listBaugruppen,
  updateBaugruppe,
} from "../api/baugruppen";
import { listKaufteile } from "../api/kaufteile";
import { listKalkulationen } from "../api/spritzguss";
import { listVeredelungsschritte } from "../api/veredelung";
import { useAuth } from "../context/AuthContext";
import type { SpritzgussListItem } from "../types/spritzguss";
import type { Veredelungsschritt } from "../types/veredelung";
import {
  emptyBaugruppeForm,
  type BaugruppeBloecke,
  type BaugruppeErgebnis,
  type BaugruppeFormData,
  type BaugruppeListItem,
  type Kaufteil,
  type SelectedKaufteil,
  type SelectedSpritzguss,
  type SelectedVeredelung,
} from "../types/baugruppe";

function euro(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const ZUSAMMENFASSUNG: Array<{ key: keyof BaugruppeErgebnis; label: string; highlight?: boolean }> = [
  { key: "einzelteile_gesamt", label: "Einzelteile gesamt (€)" },
  { key: "kaufteile_gesamt", label: "Kaufteile gesamt (€)" },
  { key: "veredelung_gesamt", label: "Montage/Veredelung gesamt (€)" },
  { key: "baugruppenpreis_je_stueck", label: "Baugruppenpreis je Stück (€)", highlight: true },
  { key: "jahresstueckzahl", label: "Jahresstückzahl" },
  { key: "jahresumsatz", label: "Jahresumsatz (€)" },
  { key: "investitionen_gesamt", label: "Investitionen gesamt (€)" },
];

export function BaugruppenPage() {
  const { canWrite } = useAuth();
  const [list, setList] = useState<BaugruppeListItem[]>([]);
  const [spritzgussList, setSpritzgussList] = useState<SpritzgussListItem[]>([]);
  const [kaufteileList, setKaufteileList] = useState<Kaufteil[]>([]);
  const [veredelungList, setVeredelungList] = useState<Veredelungsschritt[]>([]);
  const [form, setForm] = useState<BaugruppeFormData>(emptyBaugruppeForm());
  const [selectedSpritzguss, setSelectedSpritzguss] = useState<SelectedSpritzguss[]>([]);
  const [selectedKaufteile, setSelectedKaufteile] = useState<SelectedKaufteil[]>([]);
  const [selectedVeredelung, setSelectedVeredelung] = useState<SelectedVeredelung[]>([]);
  const [investitionen, setInvestitionen] = useState<
    Array<{ id: number; bezeichnung: string; investment_type: string; amount: number; status: string; quelle: string }>
  >([]);
  const [ergebnis, setErgebnis] = useState<BaugruppeErgebnis | null>(null);
  const [bloecke, setBloecke] = useState<BaugruppeBloecke | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const setField = <K extends keyof BaugruppeFormData>(key: K, value: BaugruppeFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const calcPayload = useMemo(
    () => ({
      ...form,
      spritzguss_zuordnungen: selectedSpritzguss.map((s) => ({
        spritzguss_kalkulation_id: s.spritzguss_kalkulation_id,
        menge: s.menge,
        reihenfolge: s.reihenfolge,
      })),
      kaufteil_zuordnungen: selectedKaufteile.map((k) => ({
        kaufteil_id: k.kaufteil_id,
        menge: k.menge,
        reihenfolge: k.reihenfolge,
        snapshot_preis: k.snapshot_preis ?? k.preis,
      })),
      veredelung_zuordnungen: selectedVeredelung.map((v) => ({
        veredelungsschritt_id: v.veredelungsschritt_id,
        reihenfolge: v.reihenfolge,
        mengenfaktor: v.mengenfaktor,
      })),
    }),
    [form, selectedSpritzguss, selectedKaufteile, selectedVeredelung],
  );

  const loadList = useCallback(async () => {
    const items = await listBaugruppen();
    setList(items.filter((i) => i.aktiv));
  }, []);

  const loadReferences = useCallback(async () => {
    const [sg, kt, vd] = await Promise.all([
      listKalkulationen(),
      listKaufteile(true),
      listVeredelungsschritte(),
    ]);
    setSpritzgussList(sg.filter((s) => s.aktiv));
    setKaufteileList(kt.filter((k) => k.aktiv));
    setVeredelungList(vd.filter((v) => v.aktiv));
  }, []);

  useEffect(() => {
    loadList().catch(() => undefined);
    loadReferences().catch(() => undefined);
  }, [loadList, loadReferences]);

  const handleNew = () => {
    setEditId(null);
    setForm(emptyBaugruppeForm());
    setSelectedSpritzguss([]);
    setSelectedKaufteile([]);
    setSelectedVeredelung([]);
    setInvestitionen([]);
    setErgebnis(null);
    setBloecke(null);
    setError(null);
    setSuccess(null);
  };

  const addSpritzguss = (id: number) => {
    if (selectedSpritzguss.some((s) => s.spritzguss_kalkulation_id === id)) return;
    const item = spritzgussList.find((s) => s.id === id);
    if (!item) return;
    const nextOrder =
      selectedSpritzguss.length === 0
        ? 1
        : Math.max(...selectedSpritzguss.map((s) => s.reihenfolge)) + 1;
    setSelectedSpritzguss((c) => [
      ...c,
      {
        spritzguss_kalkulation_id: id,
        bezeichnung: item.teilebezeichnung,
        teilenummer: item.teilenummer,
        endpreis: item.verkaufspreis ?? 0,
        menge: 1,
        reihenfolge: nextOrder,
      },
    ]);
  };

  const addKaufteil = (id: number) => {
    if (selectedKaufteile.some((k) => k.kaufteil_id === id)) return;
    const item = kaufteileList.find((k) => k.id === id);
    if (!item) return;
    const nextOrder =
      selectedKaufteile.length === 0
        ? 1
        : Math.max(...selectedKaufteile.map((k) => k.reihenfolge)) + 1;
    setSelectedKaufteile((c) => [
      ...c,
      {
        kaufteil_id: id,
        bezeichnung: item.bezeichnung,
        lieferant: item.lieferant,
        preis: item.preis,
        menge: 1,
        reihenfolge: nextOrder,
      },
    ]);
  };

  const addVeredelung = (id: number) => {
    if (selectedVeredelung.some((v) => v.veredelungsschritt_id === id)) return;
    const item = veredelungList.find((v) => v.id === id);
    if (!item) return;
    const nextOrder =
      selectedVeredelung.length === 0
        ? 1
        : Math.max(...selectedVeredelung.map((v) => v.reihenfolge)) + 1;
    setSelectedVeredelung((c) => [
      ...c,
      {
        veredelungsschritt_id: id,
        bezeichnung: item.bezeichnung,
        kosten: item.kosten_inkl_ausschuss,
        reihenfolge: nextOrder,
        mengenfaktor: 1,
      },
    ]);
  };

  const moveItem = <T extends { reihenfolge: number }>(
    _items: T[],
    _index: number,
    direction: "up" | "down",
    setter: (fn: (c: T[]) => T[]) => void,
    idKey: keyof T,
    id: number,
  ) => {
    setter((current) => {
      const sorted = [...current].sort((a, b) => a.reihenfolge - b.reihenfolge);
      const idx = sorted.findIndex((s) => s[idKey] === id);
      if (idx < 0) return current;
      const swap = direction === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= sorted.length) return current;
      const tmp = sorted[idx].reihenfolge;
      sorted[idx] = { ...sorted[idx], reihenfolge: sorted[swap].reihenfolge };
      sorted[swap] = { ...sorted[swap], reihenfolge: tmp };
      return sorted;
    });
  };

  const handleBerechnen = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      if (!form.name.trim()) throw new Error("Baugruppenname ist erforderlich.");
      const result = await berechnen(calcPayload);
      setErgebnis(result.ergebnis);
      setBloecke(result.bloecke);
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
      if (!form.name.trim()) throw new Error("Baugruppenname ist für das Speichern erforderlich.");
      const wasNew = editId == null;
      const saved =
        editId == null
          ? await createBaugruppe(calcPayload)
          : await updateBaugruppe(editId, calcPayload);
      setEditId(saved.id);
      setErgebnis(saved.ergebnis);
      setBloecke(saved.ergebnis_bloecke);
      setInvestitionen(saved.investitionen ?? []);
      loadFromSaved(saved);
      setSuccess(
        wasNew ? `Baugruppe #${saved.id} gespeichert.` : `Baugruppe #${saved.id} aktualisiert.`,
      );
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const loadFromSaved = (item: Awaited<ReturnType<typeof getBaugruppe>>) => {
    setSelectedSpritzguss(
      (item.spritzguss_zuordnungen ?? []).map((z) => ({
        spritzguss_kalkulation_id: z.spritzguss_kalkulation_id,
        bezeichnung: z.snapshot_bezeichnung,
        teilenummer: z.snapshot_teilenummer,
        endpreis: z.snapshot_preis,
        menge: z.menge,
        reihenfolge: z.reihenfolge,
        zwischensumme: z.zwischensumme,
      })),
    );
    setSelectedKaufteile(
      (item.kaufteil_zuordnungen ?? []).map((z) => ({
        kaufteil_id: z.kaufteil_id,
        bezeichnung: z.snapshot_bezeichnung,
        lieferant: z.snapshot_lieferant,
        preis: z.snapshot_preis,
        snapshot_preis: z.snapshot_preis,
        menge: z.menge,
        reihenfolge: z.reihenfolge,
        zwischensumme: z.zwischensumme,
      })),
    );
    setSelectedVeredelung(
      (item.veredelung_zuordnungen ?? []).map((z) => ({
        veredelungsschritt_id: z.veredelungsschritt_id,
        bezeichnung: z.snapshot_bezeichnung,
        kosten: z.snapshot_kosten,
        reihenfolge: z.reihenfolge,
        mengenfaktor: z.mengenfaktor,
        zwischensumme: z.zwischensumme,
      })),
    );
  };

  const handleLoad = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      const item = await getBaugruppe(id);
      setEditId(item.id);
      setForm({
        name: item.name,
        teilenummer: item.teilenummer,
        kunde: item.kunde,
        projekt: item.projekt,
        jahresstueckzahl: item.jahresstueckzahl,
        beschreibung: item.beschreibung,
        status: item.status,
        aktiv: item.aktiv,
      });
      setErgebnis(item.ergebnis);
      setBloecke(item.ergebnis_bloecke);
      setInvestitionen(item.investitionen ?? []);
      loadFromSaved(item);
      setSuccess(`Baugruppe #${item.id} geladen.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!canWrite || !window.confirm("Baugruppe archivieren?")) return;
    setBusy(true);
    try {
      await deleteBaugruppe(id);
      if (editId === id) handleNew();
      await loadList();
      setSuccess("Baugruppe archiviert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archivieren fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const zusammenfassung = bloecke?.zusammenfassung ?? ergebnis;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Baugruppen</h2>
          <p className="mt-1 text-sm text-gray-600">
            Zusammenführung von Einzelteilen, Kaufteilen und Montageschritten. Keine doppelten
            Zuschläge auf Einzelteilpreise.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleNew}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Neu
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
              Baugruppe speichern
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
          Bearbeite Baugruppe <strong>#{editId}</strong>
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Stammdaten</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm">
                <span className="text-gray-600">Name *</span>
                <input
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.name}
                  onChange={(e) => setField("name", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Teilenummer</span>
                <input
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.teilenummer}
                  onChange={(e) => setField("teilenummer", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Kunde</span>
                <input
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.kunde}
                  onChange={(e) => setField("kunde", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Projekt</span>
                <input
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.projekt}
                  onChange={(e) => setField("projekt", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Jahresstückzahl</span>
                <input
                  type="number"
                  min={0}
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.jahresstueckzahl}
                  onChange={(e) => setField("jahresstueckzahl", Number(e.target.value))}
                />
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Status</span>
                <select
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.status}
                  onChange={(e) => setField("status", e.target.value)}
                >
                  <option value="entwurf">Entwurf</option>
                  <option value="aktiv">Aktiv</option>
                  <option value="archiviert">Archiviert</option>
                </select>
              </label>
            </div>
            <label className="mt-3 block text-sm">
              <span className="text-gray-600">Beschreibung</span>
              <textarea
                className="mt-1 w-full rounded border px-2 py-1.5"
                rows={2}
                value={form.beschreibung}
                onChange={(e) => setField("beschreibung", e.target.value)}
              />
            </label>
          </section>

          <PositionSection
            title="Einzelteile"
            addLabel="Spritzguss-Kalkulation hinzufügen"
            options={spritzgussList.map((s) => ({
              id: s.id,
              label: `${s.teilebezeichnung} (${s.teilenummer}) – ${euro(s.verkaufspreis)} €`,
            }))}
            onAdd={addSpritzguss}
            emptyText="Noch keine Einzelteile."
          >
            {selectedSpritzguss
              .sort((a, b) => a.reihenfolge - b.reihenfolge)
              .map((s) => (
                <PositionRow
                  key={s.spritzguss_kalkulation_id}
                  title={s.bezeichnung}
                  subtitle={s.teilenummer}
                  menge={s.menge}
                  preis={s.endpreis}
                  zwischensumme={s.zwischensumme ?? s.menge * s.endpreis}
                  onMengeChange={(m) =>
                    setSelectedSpritzguss((c) =>
                      c.map((x) =>
                        x.spritzguss_kalkulation_id === s.spritzguss_kalkulation_id
                          ? { ...x, menge: m }
                          : x,
                      ),
                    )
                  }
                  onRemove={() =>
                    setSelectedSpritzguss((c) =>
                      c.filter((x) => x.spritzguss_kalkulation_id !== s.spritzguss_kalkulation_id),
                    )
                  }
                  onMoveUp={() =>
                    moveItem(
                      selectedSpritzguss,
                      0,
                      "up",
                      setSelectedSpritzguss,
                      "spritzguss_kalkulation_id",
                      s.spritzguss_kalkulation_id,
                    )
                  }
                  onMoveDown={() =>
                    moveItem(
                      selectedSpritzguss,
                      0,
                      "down",
                      setSelectedSpritzguss,
                      "spritzguss_kalkulation_id",
                      s.spritzguss_kalkulation_id,
                    )
                  }
                  preisLabel="Endpreis"
                />
              ))}
          </PositionSection>

          <PositionSection
            title="Kaufteile"
            addLabel="Kaufteil hinzufügen"
            options={kaufteileList.map((k) => ({
              id: k.id,
              label: `${k.bezeichnung} (${k.artikelnummer}) – ${euro(k.preis)} €`,
            }))}
            onAdd={addKaufteil}
            emptyText="Noch keine Kaufteile."
          >
            {selectedKaufteile
              .sort((a, b) => a.reihenfolge - b.reihenfolge)
              .map((k) => (
                <PositionRow
                  key={k.kaufteil_id}
                  title={k.bezeichnung}
                  subtitle={k.lieferant}
                  menge={k.menge}
                  preis={k.snapshot_preis ?? k.preis}
                  zwischensumme={
                    k.zwischensumme ?? k.menge * (k.snapshot_preis ?? k.preis)
                  }
                  onMengeChange={(m) =>
                    setSelectedKaufteile((c) =>
                      c.map((x) => (x.kaufteil_id === k.kaufteil_id ? { ...x, menge: m } : x)),
                    )
                  }
                  onPreisChange={(p) =>
                    setSelectedKaufteile((c) =>
                      c.map((x) =>
                        x.kaufteil_id === k.kaufteil_id ? { ...x, snapshot_preis: p, preis: p } : x,
                      ),
                    )
                  }
                  preisEditable
                  onRemove={() =>
                    setSelectedKaufteile((c) => c.filter((x) => x.kaufteil_id !== k.kaufteil_id))
                  }
                  onMoveUp={() =>
                    moveItem(
                      selectedKaufteile,
                      0,
                      "up",
                      setSelectedKaufteile,
                      "kaufteil_id",
                      k.kaufteil_id,
                    )
                  }
                  onMoveDown={() =>
                    moveItem(
                      selectedKaufteile,
                      0,
                      "down",
                      setSelectedKaufteile,
                      "kaufteil_id",
                      k.kaufteil_id,
                    )
                  }
                  preisLabel="Preis"
                />
              ))}
          </PositionSection>

          <PositionSection
            title="Montage / Veredelung"
            addLabel="Veredelungsschritt hinzufügen"
            options={veredelungList.map((v) => ({
              id: v.id,
              label: `${v.bezeichnung} – ${euro(v.kosten_inkl_ausschuss)} €`,
            }))}
            onAdd={addVeredelung}
            emptyText="Noch keine Montage-/Veredelungsschritte."
          >
            {selectedVeredelung
              .sort((a, b) => a.reihenfolge - b.reihenfolge)
              .map((v) => (
                <div
                  key={v.veredelungsschritt_id}
                  className="flex flex-wrap items-center gap-2 rounded border border-gray-100 bg-gray-50 p-2 text-sm"
                >
                  <span className="font-medium">{v.bezeichnung}</span>
                  <label className="flex items-center gap-1">
                    Faktor
                    <input
                      type="number"
                      min={0.01}
                      step="0.01"
                      className="w-20 rounded border px-1 py-0.5"
                      value={v.mengenfaktor}
                      onChange={(e) =>
                        setSelectedVeredelung((c) =>
                          c.map((x) =>
                            x.veredelungsschritt_id === v.veredelungsschritt_id
                              ? { ...x, mengenfaktor: Number(e.target.value) }
                              : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <span className="text-gray-600">
                    Kosten: {euro(v.kosten)} € → {euro(v.kosten * v.mengenfaktor)} €
                  </span>
                  <div className="ml-auto flex gap-1">
                    <button type="button" className="text-xs text-slate-600" onClick={() => moveItem(selectedVeredelung, 0, "up", setSelectedVeredelung, "veredelungsschritt_id", v.veredelungsschritt_id)}>↑</button>
                    <button type="button" className="text-xs text-slate-600" onClick={() => moveItem(selectedVeredelung, 0, "down", setSelectedVeredelung, "veredelungsschritt_id", v.veredelungsschritt_id)}>↓</button>
                    <button type="button" className="text-xs text-red-600" onClick={() => setSelectedVeredelung((c) => c.filter((x) => x.veredelungsschritt_id !== v.veredelungsschritt_id))}>Entfernen</button>
                  </div>
                </div>
              ))}
          </PositionSection>
        </div>

        <aside className="space-y-4">
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Gespeicherte Baugruppen</h3>
            {list.length === 0 ? (
              <p className="text-sm text-gray-500">Noch keine Baugruppen.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {list.map((item) => (
                  <li
                    key={item.id}
                    className="flex items-center justify-between gap-2 rounded border border-gray-100 p-2"
                  >
                    <button
                      type="button"
                      className="text-left hover:underline"
                      onClick={() => handleLoad(item.id)}
                    >
                      <span className="font-medium">{item.name}</span>
                      <span className="ml-2 text-gray-500">{euro(item.baugruppenpreis_je_stueck)} €</span>
                    </button>
                    {canWrite && (
                      <button
                        type="button"
                        className="text-xs text-red-600"
                        onClick={() => handleDelete(item.id)}
                      >
                        Archiv
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold text-gray-900">Ergebnis</h3>
            {!zusammenfassung ? (
              <p className="text-sm text-gray-500">Noch keine Berechnung. „Berechnen“ wählen.</p>
            ) : (
              <div className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
                    Zusammenfassung
                  </h4>
                  <dl className="space-y-1 text-sm">
                    {ZUSAMMENFASSUNG.map(({ key, label, highlight }) => {
                      const value = (zusammenfassung as Record<string, number>)[key];
                      if (value == null) return null;
                      const display =
                        key === "jahresstueckzahl"
                          ? String(value)
                          : euro(typeof value === "number" ? value : Number(value));
                      return (
                        <div
                          key={key}
                          className={`flex justify-between gap-3 border-b py-1.5 ${
                            highlight
                              ? "border-slate-300 bg-white px-2 -mx-2 rounded font-semibold"
                              : "border-gray-100"
                          }`}
                        >
                          <dt>{label}</dt>
                          <dd className={`tabular-nums ${highlight ? "text-lg" : "font-medium"}`}>
                            {display}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                  <p className="mt-3 text-xs text-amber-800">
                    Investitionen sind nicht im Stückpreis enthalten.
                  </p>
                </div>

                {ergebnis?.einzelteile?.length ? (
                  <DetailBlock title="Einzelteile" rows={ergebnis.einzelteile.map((p) => [
                    p.bezeichnung,
                    p.detail.teilenummer,
                    String(p.menge),
                    euro(p.einzelpreis),
                    euro(p.zwischensumme),
                  ])} headers={["Bezeichnung", "Teilenummer", "Menge", "Einzelpreis", "Summe"]} />
                ) : null}

                {ergebnis?.kaufteile?.length ? (
                  <DetailBlock title="Kaufteile" rows={ergebnis.kaufteile.map((p) => [
                    p.bezeichnung,
                    p.detail.lieferant,
                    String(p.menge),
                    euro(p.einzelpreis),
                    euro(p.zwischensumme),
                  ])} headers={["Bezeichnung", "Lieferant", "Menge", "Preis", "Summe"]} />
                ) : null}

                {ergebnis?.veredelungen?.length ? (
                  <DetailBlock title="Montage / Veredelung" rows={ergebnis.veredelungen.map((p) => [
                    String(p.reihenfolge),
                    p.bezeichnung,
                    euro(p.kosten_je_stueck),
                    String(p.mengenfaktor),
                    euro(p.zwischensumme),
                  ])} headers={["Reihenf.", "Bezeichnung", "Kosten/St.", "Faktor", "Summe"]} />
                ) : null}

                {(investitionen.length > 0 || (ergebnis?.investitionen?.length ?? 0) > 0) && (
                  <div>
                    <h4 className="mb-2 text-sm font-semibold text-slate-600">Investitionen</h4>
                    <p className="mb-2 text-xs text-amber-800">Separat, nicht im Stückpreis enthalten.</p>
                    <ul className="space-y-1 text-sm">
                      {(ergebnis?.investitionen ?? investitionen).map((inv) => (
                        <li key={inv.id} className="flex justify-between rounded bg-amber-50 px-2 py-1">
                          <span>{inv.bezeichnung} ({inv.investment_type})</span>
                          <span className="tabular-nums font-medium">{euro(inv.amount)} €</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function PositionSection({
  title,
  addLabel,
  options,
  onAdd,
  emptyText,
  children,
}: {
  title: string;
  addLabel: string;
  options: Array<{ id: number; label: string }>;
  onAdd: (id: number) => void;
  emptyText: string;
  children: ReactNode;
}) {
  const [selected, setSelected] = useState("");
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-3 font-semibold text-gray-900">{title}</h3>
      <div className="mb-3 flex gap-2">
        <select
          className="flex-1 rounded border px-2 py-1.5 text-sm"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="">– auswählen –</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!selected}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          onClick={() => {
            onAdd(Number(selected));
            setSelected("");
          }}
        >
          {addLabel}
        </button>
      </div>
      {(!children || (Array.isArray(children) && children.length === 0)) ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <div className="space-y-2">{children}</div>
      )}
    </section>
  );
}

function PositionRow({
  title,
  subtitle,
  menge,
  preis,
  zwischensumme,
  onMengeChange,
  onPreisChange,
  preisEditable,
  onRemove,
  onMoveUp,
  onMoveDown,
  preisLabel,
}: {
  title: string;
  subtitle: string;
  menge: number;
  preis: number;
  zwischensumme: number;
  onMengeChange: (m: number) => void;
  onPreisChange?: (p: number) => void;
  preisEditable?: boolean;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  preisLabel: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded border border-gray-100 bg-gray-50 p-2 text-sm">
      <div className="min-w-[120px]">
        <div className="font-medium">{title}</div>
        <div className="text-xs text-gray-500">{subtitle}</div>
      </div>
      <label className="flex items-center gap-1">
        Menge
        <input
          type="number"
          min={0.01}
          step="0.01"
          className="w-20 rounded border px-1 py-0.5"
          value={menge}
          onChange={(e) => onMengeChange(Number(e.target.value))}
        />
      </label>
      <label className="flex items-center gap-1">
        {preisLabel}
        {preisEditable ? (
          <input
            type="number"
            min={0}
            step="0.01"
            className="w-24 rounded border px-1 py-0.5"
            value={preis}
            onChange={(e) => onPreisChange?.(Number(e.target.value))}
          />
        ) : (
          <span className="tabular-nums">{euro(preis)} €</span>
        )}
      </label>
      <span className="text-gray-600">Summe: {euro(zwischensumme)} €</span>
      <div className="ml-auto flex gap-1">
        <button type="button" className="text-xs text-slate-600" onClick={onMoveUp}>↑</button>
        <button type="button" className="text-xs text-slate-600" onClick={onMoveDown}>↓</button>
        <button type="button" className="text-xs text-red-600" onClick={onRemove}>Entfernen</button>
      </div>
    </div>
  );
}

function DetailBlock({
  title,
  headers,
  rows,
}: {
  title: string;
  headers: string[];
  rows: string[][];
}) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-600">{title}</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-gray-500">
              {headers.map((h) => (
                <th key={h} className="px-1 py-1">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-gray-100">
                {row.map((cell, j) => (
                  <td key={j} className="px-1 py-1 tabular-nums">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
