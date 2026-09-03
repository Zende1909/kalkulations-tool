import { useEffect, useMemo, useRef, useState } from "react";

import { listCustomers, listPrograms, listProjects } from "../../api/hierarchy";
import { listKalkulationen } from "../../api/spritzguss";
import { Button } from "../ui/Button";
import { SectionHeader } from "../ui/SectionHeader";
import { ValidationMessage } from "../ui/ValidationMessage";
import type { Customer, Program, Project } from "../../types/hierarchy";
import type { SpritzgussListItem } from "../../types/spritzguss";
import { teilbildSrc } from "../../utils/teilbild";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function SpritzgussSavedList({
  activeId,
  canWrite,
  refreshKey = 0,
  onOpen,
  onDelete,
}: {
  activeId: number | null;
  canWrite: boolean;
  refreshKey?: number;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  const [list, setList] = useState<SpritzgussListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [collapsedMaxHeightPx, setCollapsedMaxHeightPx] = useState<number>(260);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [customerId, setCustomerId] = useState<number | "">("");
  const [programId, setProgramId] = useState<number | "">("");
  const [projectId, setProjectId] = useState<number | "">("");
  const gridHeightMeasureRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listCustomers(undefined, true).then(setCustomers).catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    if (customerId === "") {
      setPrograms([]);
      return;
    }
    listPrograms(Number(customerId)).then(setPrograms).catch(() => setPrograms([]));
  }, [customerId]);

  useEffect(() => {
    if (programId === "") {
      setProjects([]);
      return;
    }
    listProjects(Number(programId)).then(setProjects).catch(() => setProjects([]));
  }, [programId]);

  const filterKey = useMemo(
    () => `${customerId}|${programId}|${projectId}`,
    [customerId, programId, projectId],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    listKalkulationen({
      customerId: customerId === "" ? undefined : Number(customerId),
      programId: programId === "" ? undefined : Number(programId),
      projectId: projectId === "" ? undefined : Number(projectId),
    })
      .then((items) => {
        if (!cancelled) setList(items);
      })
      .catch((err) => {
        if (!cancelled) {
          setList([]);
          setLoadError(
            err instanceof Error ? err.message : "Gespeicherte Kalkulationen konnten nicht geladen werden.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filterKey, refreshKey]);

  // Beim Wechsel des Filters wieder "einklappen".
  useEffect(() => {
    setExpanded(false);
  }, [filterKey]);

  // Höhe für "eingeklappt" (genau eine Zeile) messen.
  useEffect(() => {
    if (expanded) return;
    const host = gridHeightMeasureRef.current;
    if (!host) return;
    const firstCard = host.querySelector('[data-saved-card="true"]') as HTMLElement | null;
    if (!firstCard) return;

    // Tailwind: gap-3 ~ 12px
    const gapPx = 12;
    const measured = firstCard.getBoundingClientRect().height + gapPx;
    if (Number.isFinite(measured) && measured > 0) {
      setCollapsedMaxHeightPx(measured);
    }
  }, [expanded, list.length, loading]);

  function resetFilter() {
    setCustomerId("");
    setProgramId("");
    setProjectId("");
    setLoadError(null);
  }

  const filterActive = customerId !== "" || programId !== "" || projectId !== "";

  return (
    <section className="app-card p-5">
      <SectionHeader
        title="Gespeicherte Kalkulationen"
        description="Schnellzugriff auf gespeicherte Einzelteile – mit Teilbild zur leichteren Erkennung."
        actions={
          <Button variant="secondary" size="sm" onClick={resetFilter}>
            Filter zurücksetzen
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-app-heading">Kunde</span>
          <select
            value={customerId}
            onChange={(e) => {
              const next = e.target.value === "" ? "" : Number(e.target.value);
              setCustomerId(next);
              setProgramId("");
              setProjectId("");
            }}
            className="app-input mt-0"
          >
            <option value="">Alle Kunden</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-app-heading">Programm</span>
          <select
            value={programId}
            disabled={customerId === ""}
            onChange={(e) => {
              const next = e.target.value === "" ? "" : Number(e.target.value);
              setProgramId(next);
              setProjectId("");
            }}
            className="app-input mt-0"
          >
            <option value="">Alle Programme</option>
            {programs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-app-heading">Projekt</span>
          <select
            value={projectId}
            disabled={programId === ""}
            onChange={(e) => setProjectId(e.target.value === "" ? "" : Number(e.target.value))}
            className="app-input mt-0"
          >
            <option value="">Alle Projekte</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loadError ? (
        <ValidationMessage variant="error" className="mb-4">
          {loadError}
        </ValidationMessage>
      ) : null}

      {loading ? (
        <p className="text-body-lg text-app-muted">Lade gespeicherte Kalkulationen…</p>
      ) : list.length === 0 ? (
        <p className="rounded-app border border-dashed border-app-border px-4 py-8 text-center text-app-muted">
          {filterActive
            ? "Keine gespeicherten Kalkulationen für den gewählten Filter. Filter zurücksetzen, um alle anzuzeigen."
            : "Noch keine gespeicherten Kalkulationen."}
        </p>
      ) : (
        <div className="relative">
          <div
            ref={gridHeightMeasureRef}
            style={{
              maxHeight: expanded ? 9999 : collapsedMaxHeightPx,
              overflow: "hidden",
              transition: "max-height 360ms ease",
            }}
          >
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {list.map((item) => {
                const thumb = teilbildSrc(item.teilbild_mime, item.teilbild_data);
                const isActive = activeId === item.id;
                return (
                  <article
                    key={item.id}
                    data-saved-card="true"
                    className={`rounded-app border p-3 transition-colors ${
                      isActive
                        ? "border-brand bg-brand-light/40 shadow-sm"
                        : "border-app-border bg-white hover:border-brand/40 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex gap-3">
                      <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-app border border-app-border bg-slate-50">
                        {thumb ? (
                          <img src={thumb} alt="" className="h-full w-full object-contain" />
                        ) : (
                          <span className="text-[10px] uppercase tracking-wide text-app-muted">Kein Bild</span>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-app-heading">
                          {item.teilenummer}
                        </p>
                        <p className="truncate text-sm text-app-body">{item.teilebezeichnung}</p>
                        <p className="mt-1 truncate text-xs text-app-muted">
                          {item.kunde || "–"} · {item.projekt || "–"}
                        </p>
                        <p className="mt-1 text-xs font-medium text-brand">
                          VP {euro(item.verkaufspreis)} €
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button
                        variant={isActive ? "primary" : "secondary"}
                        size="sm"
                        onClick={() => onOpen(item.id)}
                      >
                        {isActive ? "Geöffnet" : "Öffnen"}
                      </Button>
                      {canWrite ? (
                        <Button variant="danger" size="sm" onClick={() => onDelete(item.id)}>
                          Löschen
                        </Button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          {list.length > 1 ? (
            <div className="mt-3 flex justify-end">
              <Button variant="secondary" size="sm" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
                {expanded ? "Weniger anzeigen" : "Alle anzeigen"}
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
