import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  createAssemblyFamily,
  createAssemblyVariant,
  deleteAssemblyVariant,
  getAssemblyFamilyMix,
  listAssemblyFamilies,
  recalculateAssemblyFamily,
  updateAssemblyVariant,
} from "../api/assemblyFamilies";
import { CustomerProjectSelector } from "../components/hierarchy/CustomerProjectSelector";
import type { CustomerProjectSelection } from "../components/hierarchy/customerProjectSelection";
import type {
  AssemblyFamily,
  AssemblyFamilyMix,
  AssemblyVariantSummary,
} from "../types/assemblyFamily";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { maximumFractionDigits: 2 })} %`;
}

function qty(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

const emptyVariantForm = () => ({
  teilenummer: "",
  bezeichnung: "",
  anteil_prozent: "0",
  aktiv: true,
});

export function AssemblyFamilyPage() {
  const [selection, setSelection] = useState<CustomerProjectSelection>({
    customer_id: null,
    program_id: null,
    project_id: null,
  });
  const [families, setFamilies] = useState<AssemblyFamily[]>([]);
  const [familyName, setFamilyName] = useState("");
  const [selectedFamilyId, setSelectedFamilyId] = useState<number | null>(null);
  const [mix, setMix] = useState<AssemblyFamilyMix | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null);
  const [variantForm, setVariantForm] = useState(emptyVariantForm);
  const [editingVariantId, setEditingVariantId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const projectId = selection.project_id;

  const loadFamilies = useCallback(async () => {
    if (projectId == null) {
      setFamilies([]);
      return;
    }
    const rows = await listAssemblyFamilies({ project_id: projectId, aktiv: true });
    setFamilies(rows);
  }, [projectId]);

  const loadMix = useCallback(
    async (familyId: number) => {
      const data = await getAssemblyFamilyMix(familyId);
      setMix(data);
      if (data.variants.length && selectedVariantId == null) {
        setSelectedVariantId(data.variants[0].id);
      }
    },
    [selectedVariantId],
  );

  useEffect(() => {
    void loadFamilies().catch((err: Error) => setError(err.message));
  }, [loadFamilies]);

  useEffect(() => {
    if (selectedFamilyId == null) {
      setMix(null);
      return;
    }
    void loadMix(selectedFamilyId).catch((err: Error) => setError(err.message));
  }, [selectedFamilyId, loadMix]);

  const selectedVariant: AssemblyVariantSummary | null =
    mix?.variants.find((v) => v.id === selectedVariantId) ?? null;

  async function handleCreateFamily() {
    if (projectId == null || !familyName.trim()) {
      setError("Projekt und Familienname sind erforderlich.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createAssemblyFamily({
        project_id: projectId,
        name: familyName.trim(),
      });
      setFamilyName("");
      await loadFamilies();
      setSelectedFamilyId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Familie konnte nicht angelegt werden.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveVariant() {
    if (selectedFamilyId == null) return;
    const anteil = coerceFormDecimal(variantForm.anteil_prozent);
    if (anteil == null || anteil < 0 || anteil > 100) {
      setError("Variantenanteil muss zwischen 0 und 100 % liegen.");
      return;
    }
    if (!variantForm.teilenummer.trim() || !variantForm.bezeichnung.trim()) {
      setError("Teilenummer und Bezeichnung sind erforderlich.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        teilenummer: variantForm.teilenummer.trim(),
        bezeichnung: variantForm.bezeichnung.trim(),
        anteil_prozent: anteil,
        aktiv: variantForm.aktiv,
      };
      if (editingVariantId != null) {
        await updateAssemblyVariant(selectedFamilyId, editingVariantId, body);
      } else {
        const created = await createAssemblyVariant(selectedFamilyId, body);
        setSelectedVariantId(created.id);
      }
      setVariantForm(emptyVariantForm());
      setEditingVariantId(null);
      await loadMix(selectedFamilyId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Variante konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteVariant(variantId: number) {
    if (selectedFamilyId == null) return;
    if (!window.confirm("Variante wirklich löschen?")) return;
    setBusy(true);
    try {
      await deleteAssemblyVariant(selectedFamilyId, variantId);
      if (selectedVariantId === variantId) setSelectedVariantId(null);
      await loadMix(selectedFamilyId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRecalculate() {
    if (selectedFamilyId == null) return;
    setBusy(true);
    try {
      const data = await recalculateAssemblyFamily(selectedFamilyId);
      setMix(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Neuberechnung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(v: AssemblyVariantSummary) {
    setEditingVariantId(v.id);
    setSelectedVariantId(v.id);
    setVariantForm({
      teilenummer: v.teilenummer,
      bezeichnung: v.bezeichnung,
      anteil_prozent: formatDecimalForInputDe(v.anteil_prozent),
      aktiv: v.aktiv,
    });
  }

  const mixWarningClass =
    mix?.mix_status === "complete"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : mix?.mix_status === "overflow"
        ? "border-red-200 bg-red-50 text-red-800"
        : "border-amber-200 bg-amber-50 text-amber-900";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Baugruppenfamilien</h2>
        <p className="mt-1 text-sm text-slate-600">
          Variantenmix mit Anteilen an der Projektstückzahl. Komponenten je Variante über die
          bestehende Baugruppen-BOM pflegen.
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-slate-800">Projekt</h3>
        <CustomerProjectSelector value={selection} onChange={setSelection} />
      </section>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-800">Familien</h3>
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="z. B. Stoßfänger BN7i"
              value={familyName}
              onChange={(e) => setFamilyName(e.target.value)}
            />
            <button
              type="button"
              disabled={busy || projectId == null}
              onClick={() => void handleCreateFamily()}
              className="rounded-md bg-slate-800 px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              Anlegen
            </button>
          </div>
          <ul className="divide-y divide-slate-100">
            {families.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className={`w-full px-2 py-2 text-left text-sm ${
                    selectedFamilyId === f.id ? "bg-slate-100 font-semibold" : "hover:bg-slate-50"
                  }`}
                  onClick={() => setSelectedFamilyId(f.id)}
                >
                  {f.name}
                </button>
              </li>
            ))}
            {!families.length ? (
              <li className="px-2 py-3 text-sm text-slate-500">Keine Familien für dieses Projekt.</li>
            ) : null}
          </ul>
        </div>

        <div className="space-y-4">
          {mix ? (
            <>
              <section className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{mix.name}</h3>
                    <p className="mt-1 text-sm text-slate-600">
                      Projektstückzahl:{" "}
                      <strong>{qty(mix.project_jahresstueckzahl)} Stück/Jahr</strong>
                    </p>
                    <p className="text-sm text-slate-600">
                      Variantenanteile gesamt: <strong>{pct(mix.active_share_sum_pct)}</strong>
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleRecalculate()}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    Neu berechnen
                  </button>
                </div>
                <div className={`mt-3 rounded-md border px-3 py-2 text-sm ${mixWarningClass}`}>
                  <p className="font-medium">
                    Status:{" "}
                    {mix.mix_status === "complete"
                      ? "vollständig"
                      : mix.mix_status === "overflow"
                        ? "überschritten"
                        : mix.mix_status === "empty"
                          ? "leer"
                          : "unvollständig"}
                  </p>
                  <p className="mt-1">{mix.mix_message}</p>
                </div>
                {mix.gewichtete_kosten_pro_projektstueck != null ? (
                  <p className="mt-3 text-sm text-slate-700">
                    Gewichtete Baugruppenkosten pro Projektstück:{" "}
                    <strong>{euro(mix.gewichtete_kosten_pro_projektstueck)}</strong>
                  </p>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">
                    Gewichtete Gesamtkosten erst bei Summe 100 % verbindlich.
                  </p>
                )}
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="mb-3 font-semibold text-slate-800">Variantenübersicht</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-slate-600">
                        <th className="py-2 pr-3">Teilenr.</th>
                        <th className="py-2 pr-3">Bezeichnung</th>
                        <th className="py-2 pr-3 text-right">Anteil</th>
                        <th className="py-2 pr-3 text-right">Jahresmenge</th>
                        <th className="py-2">Aktiv</th>
                        <th className="py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {mix.variants.map((v) => (
                        <tr
                          key={v.id}
                          className={`border-b border-slate-100 ${
                            selectedVariantId === v.id ? "bg-slate-50" : ""
                          }`}
                        >
                          <td className="py-2 pr-3">
                            <button
                              type="button"
                              className="font-medium text-blue-700 hover:underline"
                              onClick={() => setSelectedVariantId(v.id)}
                            >
                              {v.teilenummer}
                            </button>
                          </td>
                          <td className="py-2 pr-3">{v.bezeichnung}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{pct(v.anteil_prozent)}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{qty(v.jahresmenge)}</td>
                          <td className="py-2">{v.aktiv ? "ja" : "nein"}</td>
                          <td className="py-2 text-right">
                            <button
                              type="button"
                              className="mr-2 text-xs text-slate-600 hover:underline"
                              onClick={() => startEdit(v)}
                            >
                              Bearbeiten
                            </button>
                            <button
                              type="button"
                              className="text-xs text-red-700 hover:underline"
                              onClick={() => void handleDeleteVariant(v.id)}
                            >
                              Löschen
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  Summe aktiver Anteile: {pct(mix.active_share_sum_pct)}
                </p>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="mb-3 font-semibold text-slate-800">
                  {editingVariantId != null ? "Variante bearbeiten" : "Variante hinzufügen"}
                </h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  <label className="text-sm">
                    <span className="mb-1 block text-slate-600">Teilenummer</span>
                    <input
                      className="w-full rounded-md border border-slate-300 px-3 py-2"
                      value={variantForm.teilenummer}
                      onChange={(e) =>
                        setVariantForm((f) => ({ ...f, teilenummer: e.target.value }))
                      }
                    />
                  </label>
                  <label className="text-sm sm:col-span-2">
                    <span className="mb-1 block text-slate-600">Bezeichnung</span>
                    <input
                      className="w-full rounded-md border border-slate-300 px-3 py-2"
                      value={variantForm.bezeichnung}
                      onChange={(e) =>
                        setVariantForm((f) => ({ ...f, bezeichnung: e.target.value }))
                      }
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1 block text-slate-600">Anteil %</span>
                    <input
                      className="w-full rounded-md border border-slate-300 px-3 py-2"
                      value={variantForm.anteil_prozent}
                      onChange={(e) =>
                        setVariantForm((f) => ({ ...f, anteil_prozent: e.target.value }))
                      }
                    />
                  </label>
                  <label className="flex items-end gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={variantForm.aktiv}
                      onChange={(e) =>
                        setVariantForm((f) => ({ ...f, aktiv: e.target.checked }))
                      }
                    />
                    Aktiv (zählt zur Summe)
                  </label>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleSaveVariant()}
                    className="rounded-md bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
                  >
                    {editingVariantId != null ? "Speichern" : "Variante hinzufügen"}
                  </button>
                  {editingVariantId != null ? (
                    <button
                      type="button"
                      className="rounded-md border border-slate-300 px-4 py-2 text-sm"
                      onClick={() => {
                        setEditingVariantId(null);
                        setVariantForm(emptyVariantForm());
                      }}
                    >
                      Abbrechen
                    </button>
                  ) : null}
                </div>
              </section>

              {selectedVariant ? (
                <section className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-800">
                        Variante {selectedVariant.teilenummer}
                      </h4>
                      <p className="text-sm text-slate-600">{selectedVariant.bezeichnung}</p>
                      <p className="mt-1 text-sm text-slate-600">
                        Anteil {pct(selectedVariant.anteil_prozent)} · Jahresmenge{" "}
                        {qty(selectedVariant.jahresmenge)}
                      </p>
                    </div>
                    <Link
                      to="/baugruppen"
                      className="text-sm font-medium text-blue-700 hover:underline"
                    >
                      Komponenten in Baugruppen bearbeiten (ID {selectedVariant.id})
                    </Link>
                  </div>
                  <div className="mt-3 overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-slate-600">
                          <th className="py-2 pr-3">Komponente</th>
                          <th className="py-2 pr-3 text-right">Menge je Variante</th>
                          <th className="py-2 text-right">Effektive Jahresmenge</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedVariant.komponenten.map((c) => (
                          <tr
                            key={`${c.component_type}-${c.component_id}`}
                            className="border-b border-slate-100"
                          >
                            <td className="py-2 pr-3">
                              {c.bezeichnung || c.teilenummer || c.component_type}
                            </td>
                            <td className="py-2 pr-3 text-right tabular-nums">
                              {c.menge_je_variante.toLocaleString("de-DE")}
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {qty(c.effektive_jahresmenge)}
                            </td>
                          </tr>
                        ))}
                        {!selectedVariant.komponenten.length ? (
                          <tr>
                            <td colSpan={3} className="py-4 text-center text-slate-500">
                              Noch keine Komponenten. Bitte in der Baugruppenmaske zuordnen.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}

              {mix.aggregated_components.length ? (
                <section className="rounded-lg border border-slate-200 bg-white p-4">
                  <h4 className="mb-3 font-semibold text-slate-800">
                    Aggregierte Komponentenmengen (alle Varianten)
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-slate-600">
                          <th className="py-2 pr-3">Komponente</th>
                          <th className="py-2 pr-3 text-right">Effektive Jahresmenge</th>
                          <th className="py-2 pr-3 text-right">Losgröße</th>
                          <th className="py-2 text-right">Anzahl Lose</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mix.aggregated_components.map((c) => (
                          <tr
                            key={`agg-${c.component_type}-${c.component_id}`}
                            className="border-b border-slate-100"
                          >
                            <td className="py-2 pr-3">{c.bezeichnung || c.teilenummer}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">
                              {qty(c.effektive_jahresmenge)}
                            </td>
                            <td className="py-2 pr-3 text-right tabular-nums">
                              {c.losgroesse != null ? qty(c.losgroesse) : "–"}
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {c.anzahl_lose != null ? qty(c.anzahl_lose) : "–"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">
              Projekt wählen und eine Baugruppenfamilie auswählen oder anlegen.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
