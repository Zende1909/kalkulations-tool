import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getBusinessCaseOverview, listProjectOptions } from "../api/businessCase";
import {
  baugruppePdfUrl,
  baugruppeXlsxUrl,
  dashboardPdfUrl,
  dashboardXlsxUrl,
  downloadReport,
  spritzgussPdfUrl,
  spritzgussXlsxUrl,
} from "../api/reports";
import { EINMALZAHLUNG_HINWEIS } from "../types/investition";
import type { BusinessCaseResponse } from "../types/businessCase";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function int(value: number | null | undefined): string {
  if (value == null) return "–";
  return value.toLocaleString("de-DE");
}

export function BusinessCasePage() {
  const [customers, setCustomers] = useState<string[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [customerDraft, setCustomerDraft] = useState("");
  const [projectDraft, setProjectDraft] = useState("");
  const [data, setData] = useState<BusinessCaseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjectOptions().then(({ customers: c, projects: p }) => {
      setCustomers(c);
      setProjects(p);
    });
  }, []);

  const loadBusinessCase = useCallback(async () => {
    if (!customerDraft.trim() || !projectDraft.trim()) {
      setError("Bitte Kunde und Projekt auswählen.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getBusinessCaseOverview({
        customer: customerDraft,
        project: projectDraft,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Business Case konnte nicht geladen werden.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [customerDraft, projectDraft]);

  const resetFilters = () => {
    setCustomerDraft("");
    setProjectDraft("");
    setData(null);
    setError(null);
  };

  const exportDashboard = async (format: "pdf" | "xlsx") => {
    if (!data) return;
    setExportBusy(true);
    try {
      const filename = `dashboard_${data.project.replace(/\W+/g, "_")}.${format === "pdf" ? "pdf" : "xlsx"}`;
      const path =
        format === "pdf"
          ? dashboardPdfUrl({ project: data.project, customer: data.customer })
          : dashboardXlsxUrl({ project: data.project, customer: data.customer });
      await downloadReport(path, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Business Case</h2>
        <p className="mt-1 text-sm text-gray-600">
          Projektbezogene Gesamtübersicht – Einzelteile, Baugruppen und Investitionen getrennt.
          Teilepreise ohne Investitionsanteil.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">Kunde</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={customerDraft}
              onChange={(e) => setCustomerDraft(e.target.value)}
            >
              <option value="">Alle</option>
              {customers.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={projectDraft}
              onChange={(e) => setProjectDraft(e.target.value)}
            >
              <option value="">Alle</option>
              {projects.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={loading || !customerDraft || !projectDraft}
            onClick={loadBusinessCase}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
          >
            Business Case anzeigen
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            Filter zurücksetzen
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {data && (
        <>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="text-lg font-semibold text-gray-900">Business-Case-Kopf</h3>
            <p className="mt-1 text-sm text-gray-600">
              {data.customer} · {data.project}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Gesamtstückzahl Laufzeit", int(data.kpis.gesamtstueckzahl_laufzeit)],
                ["Umsatzpotenzial Laufzeit", euro(data.kpis.umsatzpotenzial_laufzeit)],
                ["Jahresstückzahl gesamt (historisch)", int(data.kpis.jahresstueckzahl_gesamt)],
                ["Umsatzpotenzial Einzelteile", euro(data.kpis.umsatzpotenzial_einzelteile)],
                ["Umsatzpotenzial Baugruppen", euro(data.kpis.umsatzpotenzial_baugruppen)],
                ["Investitionen gesamt", euro(data.kpis.investitionen_gesamt)],
                ["Anzahl Einzelteile", String(data.kpis.anzahl_einzelteile)],
                ["Anzahl Baugruppen", String(data.kpis.anzahl_baugruppen)],
                ["Anzahl Investitionen", String(data.kpis.anzahl_investitionen)],
                ["Amortisationsanteil je Stück", euro(data.kpis.amortisationsanteil_je_stueck)],
              ].map(([label, value]) => (
                <div key={label} className="rounded border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">{label}</div>
                  <div className="mt-1 font-semibold text-gray-900">{value}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-500">{data.revenue_summary.hinweis}</p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={exportBusy}
                onClick={() => exportDashboard("pdf")}
                className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Dashboard PDF
              </button>
              <button
                type="button"
                disabled={exportBusy}
                onClick={() => exportDashboard("xlsx")}
                className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Dashboard Excel
              </button>
            </div>
          </section>

          {data.lifetime_volume_profile && data.lifetime_volume_profile.length > 0 && (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-3 font-semibold">Mengenprofil über die Projektlaufzeit</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Jahr</th>
                      <th className="py-2 pr-3">Programmfahrzeuge</th>
                      <th className="py-2 pr-3">Anzahl pro Fahrzeug</th>
                      <th className="py-2 pr-3">Projektstückzahl</th>
                      <th className="py-2 pr-3">Teilepreis/Stück</th>
                      <th className="py-2 pr-3">Jahresumsatz</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.lifetime_volume_profile.map((row) => (
                      <tr key={row.calendar_year} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{row.calendar_year}</td>
                        <td className="py-2 pr-3">{int(row.vehicle_volume)}</td>
                        <td className="py-2 pr-3">{row.quantity_per_vehicle}</td>
                        <td className="py-2 pr-3">{int(row.project_volume)}</td>
                        <td className="py-2 pr-3">{euro(row.teilepreis_je_stueck)}</td>
                        <td className="py-2 pr-3">{euro(row.jahresumsatz)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Einzelteile</h3>
            {data.parts.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Einzelteil-Kalkulationen für dieses Projekt.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Bezeichnung</th>
                      <th className="py-2 pr-3">Teilenummer</th>
                      <th className="py-2 pr-3">Stückzahl Laufzeit</th>
                      <th className="py-2 pr-3">Endpreis/Stück</th>
                      <th className="py-2 pr-3">Umsatz Laufzeit</th>
                      <th className="py-2 pr-3">Veredelung</th>
                      <th className="py-2">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.parts.map((p) => (
                      <tr key={p.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{p.bezeichnung}</td>
                        <td className="py-2 pr-3">{p.teilenummer}</td>
                        <td className="py-2 pr-3">{int(p.gesamtstueckzahl_laufzeit ?? p.jahresstueckzahl)}</td>
                        <td className="py-2 pr-3">{euro(p.endpreis_je_stueck)}</td>
                        <td className="py-2 pr-3">{euro(p.umsatzpotenzial_laufzeit ?? p.jahresumsatz)}</td>
                        <td className="py-2 pr-3">{p.anzahl_veredelungsschritte}</td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            <Link to="/spritzguss" className="text-blue-700 underline">
                              Öffnen
                            </Link>
                            <button
                              type="button"
                              className="text-blue-700 underline"
                              onClick={() =>
                                downloadReport(
                                  spritzgussPdfUrl(p.id),
                                  `einzelteil_${p.teilenummer}.pdf`,
                                )
                              }
                            >
                              PDF
                            </button>
                            <button
                              type="button"
                              className="text-blue-700 underline"
                              onClick={() =>
                                downloadReport(
                                  spritzgussXlsxUrl(p.id),
                                  `einzelteil_${p.teilenummer}.xlsx`,
                                )
                              }
                            >
                              Excel
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Baugruppen</h3>
            {data.assemblies.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Baugruppen für dieses Projekt.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Name</th>
                      <th className="py-2 pr-3">Nummer</th>
                      <th className="py-2 pr-3">Jahresstückzahl</th>
                      <th className="py-2 pr-3">Preis/Stück</th>
                      <th className="py-2 pr-3">Jahresumsatz</th>
                      <th className="py-2 pr-3">ET / KT / VD</th>
                      <th className="py-2">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.assemblies.map((a) => (
                      <tr key={a.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{a.name}</td>
                        <td className="py-2 pr-3">{a.teilenummer}</td>
                        <td className="py-2 pr-3">{int(a.jahresstueckzahl)}</td>
                        <td className="py-2 pr-3">{euro(a.baugruppenpreis_je_stueck)}</td>
                        <td className="py-2 pr-3">{euro(a.jahresumsatz)}</td>
                        <td className="py-2 pr-3">
                          {a.anzahl_einzelteile}/{a.anzahl_kaufteile}/{a.anzahl_veredelungsschritte}
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            <Link to="/baugruppen" className="text-blue-700 underline">
                              Öffnen
                            </Link>
                            <button
                              type="button"
                              className="text-blue-700 underline"
                              onClick={() =>
                                downloadReport(
                                  baugruppePdfUrl(a.id),
                                  `baugruppe_${a.teilenummer}.pdf`,
                                )
                              }
                            >
                              PDF
                            </button>
                            <button
                              type="button"
                              className="text-blue-700 underline"
                              onClick={() =>
                                downloadReport(
                                  baugruppeXlsxUrl(a.id),
                                  `baugruppe_${a.teilenummer}.xlsx`,
                                )
                              }
                            >
                              Excel
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Investitionen</h3>
            <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 text-sm">
              <div>Gesamt: {euro(data.kpis.investitionen_gesamt)}</div>
              <div>Amortisation: {euro(data.kpis.amortisationsinvestitionen_gesamt)}</div>
              <div className="text-amber-900">
                Einmalzahlungen: {euro(data.kpis.einmalinvestitionen_gesamt)}
              </div>
              <div>Anteil/Stück: {euro(data.kpis.amortisationsanteil_je_stueck)}</div>
            </div>
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Investitionen für dieses Projekt.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Bezeichnung</th>
                      <th className="py-2 pr-3">Art</th>
                      <th className="py-2 pr-3">Zahlungsart</th>
                      <th className="py-2 pr-3">Betrag</th>
                      <th className="py-2 pr-3">Kosten/Stück</th>
                      <th className="py-2 pr-3">Zuordnung</th>
                      <th className="py-2">Hinweis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investments.map((inv) => (
                      <tr key={inv.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{inv.bezeichnung}</td>
                        <td className="py-2 pr-3">{inv.investment_type}</td>
                        <td className="py-2 pr-3">{inv.payment_type}</td>
                        <td className="py-2 pr-3">{euro(inv.amount)}</td>
                        <td className="py-2 pr-3">
                          {inv.payment_type === "Amortisation" ? euro(inv.cost_per_piece) : "–"}
                        </td>
                        <td className="py-2 pr-3">{inv.zuordnung}</td>
                        <td className="py-2 text-amber-800">{inv.hinweis}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-3 text-xs text-amber-800">{EINMALZAHLUNG_HINWEIS}</p>
          </section>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
          Bitte Kunde und Projekt wählen und „Business Case anzeigen“ klicken.
        </div>
      )}
    </div>
  );
}
