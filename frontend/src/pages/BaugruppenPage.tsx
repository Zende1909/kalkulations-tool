import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  archivierenBaugruppe,
  berechnen,
  createBaugruppe,
  deleteBaugruppe,
  getBaugruppe,
  listBaugruppen,
  updateBaugruppe,
} from "../api/baugruppen";
import {
  baugruppePdfUrl,
  baugruppeXlsxUrl,
  downloadReport,
} from "../api/reports";
import { listKaufteile } from "../api/kaufteile";
import { listKalkulationen } from "../api/spritzguss";
import { listVeredelungsschritte } from "../api/veredelung";
import { ExportButtons } from "../components/ExportButtons";
import { CustomerProjectSelector } from "../components/hierarchy/CustomerProjectSelector";
import {
  applyHierarchyToFormFields,
  hierarchySelectionRequiresIds,
  isHierarchyClearedPendingUnlink,
  resolveFreitextForSave,
  resolveHierarchySaveFields,
  type CustomerProjectSelection,
  type LegacyFreitext,
} from "../components/hierarchy/customerProjectSelection";
import { getAverageJahresstueckzahl } from "../api/hierarchy";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { SpritzgussListItem } from "../types/spritzguss";
import type { Land, Werk } from "../types/stammdaten";
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
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [legacyFreitext, setLegacyFreitext] = useState<LegacyFreitext | null>(null);
  const [loadedHierarchy, setLoadedHierarchy] = useState<CustomerProjectSelection>({
    customer_id: null,
    program_id: null,
    project_id: null,
  });
  const [unlinkConfirmed, setUnlinkConfirmed] = useState(false);
  /** Liste: aktive (Standard) oder archivierte Baugruppen */
  const [listFilter, setListFilter] = useState<"aktiv" | "archiviert">("aktiv");
  const [jahresstueckzahlHint, setJahresstueckzahlHint] = useState<string | null>(null);
  const [jahresstueckzahlLoading, setJahresstueckzahlLoading] = useState(false);
  const [laender, setLaender] = useState<Land[]>([]);
  const [werke, setWerke] = useState<Werk[]>([]);
  const [selectedLandId, setSelectedLandId] = useState<number | null>(null);

  const formHierarchy = useMemo(
    (): CustomerProjectSelection => ({
      customer_id: form.customer_id,
      program_id: form.program_id,
      project_id: form.project_id,
    }),
    [form.customer_id, form.program_id, form.project_id],
  );

  const filteredWerke = useMemo(() => {
    const forLand =
      selectedLandId == null
        ? werke
        : werke.filter((w) => w.land_id === selectedLandId);
    const current = form.werk_id != null ? werke.find((w) => w.id === form.werk_id) : null;
    const active = forLand.filter((w) => w.aktiv);
    if (current && !current.aktiv && !active.some((w) => w.id === current.id)) {
      return [...active, current];
    }
    return active;
  }, [werke, selectedLandId, form.werk_id]);

  const setField = <K extends keyof BaugruppeFormData>(key: K, value: BaugruppeFormData[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const calcPayload = useMemo(() => {
    const hierarchyFields = resolveHierarchySaveFields({
      formSelection: formHierarchy,
      loadedProjectId: loadedHierarchy.project_id,
      unlinkConfirmed,
    });
    const freitext = resolveFreitextForSave(
      formHierarchy,
      { kunde: form.kunde, projekt: form.projekt },
      legacyFreitext,
    );
    return {
      ...form,
      project_id: hierarchyFields.project_id,
      clear_project_link: hierarchyFields.clear_project_link,
      kunde: freitext.kunde,
      projekt: freitext.projekt,
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
    };
  }, [
    form,
    formHierarchy,
    legacyFreitext,
    loadedHierarchy.project_id,
    unlinkConfirmed,
    selectedSpritzguss,
    selectedKaufteile,
    selectedVeredelung,
  ]);

  const hierarchyClearedPendingUnlink = isHierarchyClearedPendingUnlink(
    formHierarchy,
    loadedHierarchy.project_id,
    unlinkConfirmed,
  );

  const loadList = useCallback(async () => {
    const items = await listBaugruppen({
      aktiv: listFilter === "aktiv",
    });
    setList(items);
  }, [listFilter]);

  const loadReferences = useCallback(async () => {
    const [sg, kt, vd, lands, plants] = await Promise.all([
      listKalkulationen(),
      listKaufteile({ nurAktiv: true }),
      listVeredelungsschritte(),
      api.get<Land[]>("/laender"),
      api.get<Werk[]>("/werke"),
    ]);
    setSpritzgussList(sg.filter((s) => s.aktiv));
    setKaufteileList(kt.filter((k) => k.aktiv));
    setVeredelungList(vd.filter((v) => v.aktiv));
    setLaender(lands);
    setWerke(plants);
  }, []);

  useEffect(() => {
    loadList().catch(() => undefined);
    loadReferences().catch(() => undefined);
  }, [loadList, loadReferences]);

  // Jahresstückzahl aus Projekt-Durchschnitt (serverseitig berechnet).
  // Gespeicherte Werte beim bloßen Öffnen nicht überschreiben – nur bei Projektwechsel / Neuanlage.
  useEffect(() => {
    let cancelled = false;
    if (form.project_id == null) {
      setJahresstueckzahlHint(
        form.customer_id != null || form.program_id != null
          ? "Jahresstückzahl wird nach Projektauswahl aus den Projektstückzahlen berechnet."
          : null,
      );
      setJahresstueckzahlLoading(false);
      return;
    }
    const projectChangedFromLoaded =
      editId == null || form.project_id !== loadedHierarchy.project_id;
    setJahresstueckzahlLoading(true);
    setJahresstueckzahlHint(null);
    getAverageJahresstueckzahl(form.project_id)
      .then((avg) => {
        if (cancelled) return;
        if (!avg.has_volumes || avg.jahresstueckzahl == null) {
          setJahresstueckzahlHint(
            "Für dieses Projekt sind keine Jahresstückzahlen hinterlegt. Bitte Mengenprofil im Programm pflegen.",
          );
          return;
        }
        if (projectChangedFromLoaded) {
          setForm((current) =>
            current.project_id === form.project_id
              ? { ...current, jahresstueckzahl: avg.jahresstueckzahl! }
              : current,
          );
        }
        setJahresstueckzahlHint(
          `Automatisch: ⌈Summe / ${avg.year_count} Jahre⌉ = ${avg.jahresstueckzahl.toLocaleString("de-DE")}`,
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setJahresstueckzahlHint(
            err instanceof Error ? err.message : "Jahresstückzahl konnte nicht geladen werden.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setJahresstueckzahlLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [form.project_id, form.customer_id, form.program_id, editId, loadedHierarchy.project_id]);

  const handleNew = () => {
    setEditId(null);
    setForm(emptyBaugruppeForm());
    setSelectedLandId(null);
    setLegacyFreitext(null);
    setLoadedHierarchy({ customer_id: null, program_id: null, project_id: null });
    setUnlinkConfirmed(false);
    setJahresstueckzahlHint(null);
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
      if (hierarchySelectionRequiresIds(formHierarchy)) {
        if (form.customer_id == null) throw new Error("Bitte einen Kunden auswählen.");
        if (form.program_id == null) throw new Error("Bitte ein Programm auswählen.");
        if (form.project_id == null) throw new Error("Bitte ein Projekt auswählen.");
      }
      const wasArchived = editId != null && !form.aktiv;
      const reactivating = wasArchived && form.status === "aktiv";
      const wasNew = editId == null;
      // aktiv nie blind mitsenden – Reaktivierung nur über status=aktiv
      const { aktiv: _omitAktiv, ...saveBody } = calcPayload;
      let updatePayload: Partial<typeof calcPayload> = saveBody;
      if (wasArchived && !reactivating) {
        // Archiviert bleibt archiviert, solange Status nicht auf Aktiv gesetzt wird
        const { status: _omitStatus, ...rest } = saveBody;
        updatePayload = rest;
      }
      if (reactivating) {
        updatePayload = { ...saveBody, status: "aktiv", aktiv: true };
      }
      const saved =
        editId == null
          ? await createBaugruppe(calcPayload)
          : await updateBaugruppe(editId, updatePayload);
      setEditId(saved.id);
      const nextHierarchy: CustomerProjectSelection = {
        customer_id: saved.customer_id ?? null,
        program_id: saved.program_id ?? null,
        project_id: saved.project_id ?? null,
      };
      setForm({
        name: saved.name,
        teilenummer: saved.teilenummer,
        kunde: saved.kunde,
        projekt: saved.projekt,
        project_id: nextHierarchy.project_id,
        customer_id: nextHierarchy.customer_id,
        program_id: nextHierarchy.program_id,
        werk_id: saved.werk_id ?? null,
        jahresstueckzahl: saved.jahresstueckzahl,
        beschreibung: saved.beschreibung,
        status: saved.status,
        aktiv: saved.aktiv,
      });
      if (saved.werk_id != null) {
        const plant = werke.find((w) => w.id === saved.werk_id);
        if (plant) setSelectedLandId(plant.land_id);
      }
      setLoadedHierarchy(nextHierarchy);
      setUnlinkConfirmed(false);
      if (saved.project_id == null && (saved.kunde || saved.projekt)) {
        setLegacyFreitext({ kunde: saved.kunde, projekt: saved.projekt });
      } else {
        setLegacyFreitext(null);
      }
      setErgebnis(saved.ergebnis);
      setBloecke(saved.ergebnis_bloecke);
      setInvestitionen(saved.investitionen ?? []);
      loadFromSaved(saved);
      setSuccess(
        wasNew
          ? `Baugruppe #${saved.id} gespeichert.`
          : reactivating
            ? `Baugruppe #${saved.id} reaktiviert und aktualisiert.`
            : `Baugruppe #${saved.id} aktualisiert.`,
      );
      // Liste neu laden; bei Reaktivierung ggf. Filter auf Aktiv
      if (reactivating && listFilter === "archiviert") {
        setListFilter("aktiv");
      } else {
        await loadList();
      }
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
      const nextHierarchy: CustomerProjectSelection = {
        customer_id: item.customer_id ?? null,
        program_id: item.program_id ?? null,
        project_id: item.project_id ?? null,
      };
      setForm({
        name: item.name,
        teilenummer: item.teilenummer,
        kunde: item.kunde,
        projekt: item.projekt,
        project_id: nextHierarchy.project_id,
        customer_id: nextHierarchy.customer_id,
        program_id: nextHierarchy.program_id,
        werk_id: item.werk_id ?? null,
        jahresstueckzahl: item.jahresstueckzahl,
        beschreibung: item.beschreibung,
        status: item.status,
        aktiv: item.aktiv,
      });
      if (item.werk_id != null) {
        const plant = werke.find((w) => w.id === item.werk_id);
        setSelectedLandId(plant?.land_id ?? null);
      } else {
        setSelectedLandId(null);
      }
      setLoadedHierarchy(nextHierarchy);
      setUnlinkConfirmed(false);
      if (item.project_id == null && (item.kunde || item.projekt)) {
        setLegacyFreitext({ kunde: item.kunde, projekt: item.projekt });
      } else {
        setLegacyFreitext(null);
      }
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

  const handleArchive = async (id: number) => {
    if (!canWrite || !window.confirm("Baugruppe wirklich archivieren?")) return;
    setBusy(true);
    setError(null);
    try {
      await archivierenBaugruppe(id);
      if (editId === id) handleNew();
      await loadList();
      setSuccess("Baugruppe archiviert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archivieren fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (
      !canWrite ||
      !window.confirm(
        "Baugruppe endgültig löschen? Zugehörige Positionen und Zuordnungen werden mitgelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteBaugruppe(id);
      if (editId === id) handleNew();
      await loadList();
      setSuccess("Baugruppe gelöscht.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async (format: "pdf" | "xlsx") => {
    if (editId == null) return;
    setExportBusy(true);
    setError(null);
    try {
      const nummer = form.teilenummer.trim() || form.name.trim() || String(editId);
      const filename = `baugruppe_${nummer}.${format === "pdf" ? "pdf" : "xlsx"}`;
      const path = format === "pdf" ? baugruppePdfUrl(editId) : baugruppeXlsxUrl(editId);
      await downloadReport(path, filename);
      setSuccess(`Export ${format.toUpperCase()} erfolgreich.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportBusy(false);
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
          {editId != null && (
            <ExportButtons
              busy={exportBusy}
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
          Bearbeite Baugruppe <strong>#{editId}</strong>
          {!form.aktiv && (
            <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold uppercase text-amber-950">
              Archiviert
            </span>
          )}
        </p>
      )}
      {editId != null && !form.aktiv && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Diese Baugruppe ist archiviert. Zum Reaktivieren im Statusfeld „Aktiv“ wählen und speichern.
          Ohne Statusänderung bleibt sie archiviert. Zum endgültigen Entfernen „Löschen“ in der Liste
          verwenden.
        </div>
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
              <CustomerProjectSelector
                disabled={busy}
                value={formHierarchy}
                legacyText={
                  form.project_id == null &&
                  loadedHierarchy.project_id == null &&
                  !unlinkConfirmed &&
                  legacyFreitext &&
                  (legacyFreitext.kunde || legacyFreitext.projekt)
                    ? legacyFreitext
                    : null
                }
                onChange={(next) => {
                  setUnlinkConfirmed(false);
                  setForm((current) => applyHierarchyToFormFields(current, next, legacyFreitext));
                }}
              />
              <label className="block text-sm">
                <span className="text-gray-600">Land / Region</span>
                <select
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={selectedLandId ?? ""}
                  disabled={busy}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : null;
                    setSelectedLandId(v);
                    setForm((c) => ({ ...c, werk_id: null }));
                  }}
                >
                  <option value="">– optional / Legacy –</option>
                  {laender
                    .filter((l) => l.aktiv || (form.werk_id != null && werke.some((w) => w.id === form.werk_id && w.land_id === l.id)))
                    .map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.code} – {l.name}
                        {!l.aktiv ? " (inaktiv)" : ""}
                      </option>
                    ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Werk / Standort</span>
                <select
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.werk_id ?? ""}
                  disabled={busy}
                  onChange={(e) => {
                    const wid = e.target.value ? Number(e.target.value) : null;
                    setForm((c) => ({ ...c, werk_id: wid }));
                    if (wid != null) {
                      const plant = werke.find((w) => w.id === wid);
                      if (plant) setSelectedLandId(plant.land_id);
                    }
                  }}
                >
                  <option value="">– optional / Legacy –</option>
                  {filteredWerke.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} – {w.name}
                      {!w.aktiv ? " (inaktiv)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              {hierarchyClearedPendingUnlink && (
                <div className="md:col-span-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <p>
                    Die Kunden-/Programm-/Projektauswahl wurde geleert. Beim Speichern bleibt die
                    bestehende Verknüpfung erhalten.
                  </p>
                  <button
                    type="button"
                    disabled={busy || !canWrite}
                    className="mt-2 rounded-md border border-amber-400 bg-white px-3 py-1.5 text-sm font-medium text-amber-950 hover:bg-amber-100 disabled:opacity-50"
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Verknüpfung zu Kunde, Programm und Projekt wirklich entfernen? Die Änderung wird erst beim Speichern übernommen.",
                        )
                      ) {
                        return;
                      }
                      setUnlinkConfirmed(true);
                      setForm((current) => ({
                        ...current,
                        customer_id: null,
                        program_id: null,
                        project_id: null,
                      }));
                    }}
                  >
                    Verknüpfung entfernen
                  </button>
                </div>
              )}
              {unlinkConfirmed && loadedHierarchy.project_id != null && (
                <div className="md:col-span-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                  Verknüpfung wird beim Speichern entfernt.{" "}
                  <button
                    type="button"
                    className="underline"
                    onClick={() => {
                      setUnlinkConfirmed(false);
                      setForm((current) => ({
                        ...current,
                        customer_id: loadedHierarchy.customer_id,
                        program_id: loadedHierarchy.program_id,
                        project_id: loadedHierarchy.project_id,
                      }));
                    }}
                  >
                    Rückgängig
                  </button>
                </div>
              )}
              <label className="block text-sm">
                <span className="text-gray-600">Jahresstückzahl (aus Projekt)</span>
                <input
                  type="number"
                  readOnly
                  disabled
                  data-testid="baugruppe-jahresstueckzahl"
                  className="mt-1 w-full rounded border bg-gray-50 px-2 py-1.5 text-gray-800"
                  value={form.jahresstueckzahl}
                />
                {jahresstueckzahlLoading && (
                  <p className="mt-1 text-xs text-gray-500">Jahresstückzahl wird berechnet…</p>
                )}
                {jahresstueckzahlHint && (
                  <p className="mt-1 text-xs text-amber-800">{jahresstueckzahlHint}</p>
                )}
              </label>
              <label className="block text-sm">
                <span className="text-gray-600">Status</span>
                <select
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  value={form.status}
                  onChange={(e) => setField("status", e.target.value)}
                >
                  {form.aktiv ? (
                    <>
                      <option value="entwurf">Entwurf</option>
                      <option value="aktiv">Aktiv</option>
                      <option value="archiviert">Archiviert</option>
                    </>
                  ) : (
                    <>
                      <option value="archiviert">Archiviert</option>
                      <option value="aktiv">Aktiv</option>
                    </>
                  )}
                </select>
                {!form.aktiv && (
                  <p className="mt-1 text-xs text-amber-800">
                    Zum Reaktivieren „Aktiv“ wählen und speichern. Ohne Statusänderung bleibt die
                    Baugruppe archiviert.
                  </p>
                )}
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
            addLabel="Einzelteilkalkulation hinzufügen"
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
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-gray-900">Gespeicherte Baugruppen</h3>
              <div className="flex rounded-md border border-gray-200 text-xs">
                <button
                  type="button"
                  className={`px-2 py-1 ${listFilter === "aktiv" ? "bg-slate-800 text-white" : "bg-white text-gray-700"}`}
                  onClick={() => setListFilter("aktiv")}
                >
                  Aktiv
                </button>
                <button
                  type="button"
                  className={`px-2 py-1 ${listFilter === "archiviert" ? "bg-slate-800 text-white" : "bg-white text-gray-700"}`}
                  onClick={() => setListFilter("archiviert")}
                >
                  Archiviert
                </button>
              </div>
            </div>
            {list.length === 0 ? (
              <p className="text-sm text-gray-500">
                {listFilter === "aktiv"
                  ? "Noch keine aktiven Baugruppen."
                  : "Keine archivierten Baugruppen."}
              </p>
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
                      {!item.aktiv && (
                        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-900">
                          Archiviert
                        </span>
                      )}
                      <span className="ml-2 text-gray-500">
                        {euro(item.baugruppenpreis_je_stueck)} €
                      </span>
                    </button>
                    {canWrite && (
                      <div className="flex shrink-0 gap-2">
                        {item.aktiv && (
                          <button
                            type="button"
                            className="text-xs text-amber-800"
                            onClick={() => handleArchive(item.id)}
                          >
                            Archivieren
                          </button>
                        )}
                        <button
                          type="button"
                          className="text-xs font-medium text-red-600"
                          onClick={() => handleDelete(item.id)}
                        >
                          Löschen
                        </button>
                      </div>
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
