export interface SpritzgussZuordnungInput {
  spritzguss_kalkulation_id: number;
  menge: number;
  reihenfolge: number;
}

export interface KaufteilZuordnungInput {
  kaufteil_id: number;
  menge: number;
  reihenfolge: number;
  snapshot_preis?: number | null;
}

export interface VeredelungZuordnungInput {
  veredelungsschritt_id: number;
  reihenfolge: number;
  mengenfaktor: number;
}

export interface SpritzgussZuordnung extends SpritzgussZuordnungInput {
  id: number;
  baugruppe_id: number;
  snapshot_preis: number;
  snapshot_bezeichnung: string;
  snapshot_teilenummer: string;
  zwischensumme?: number;
}

export interface KaufteilZuordnung extends KaufteilZuordnungInput {
  id: number;
  baugruppe_id: number;
  snapshot_preis: number;
  snapshot_bezeichnung: string;
  snapshot_lieferant: string;
  zwischensumme?: number;
}

export interface VeredelungZuordnung extends VeredelungZuordnungInput {
  id: number;
  baugruppe_id: number;
  snapshot_kosten: number;
  snapshot_bezeichnung: string;
  zwischensumme?: number;
}

export interface InvestitionAnzeige {
  id: number;
  bezeichnung: string;
  investment_type: string;
  amount: number;
  status: string;
  quelle: string;
}

export interface BaugruppeErgebnis {
  einzelteile_gesamt: number;
  kaufteile_gesamt: number;
  veredelung_gesamt: number;
  vorprodukt_gesamt?: number;
  assembly_direkt_gesamt?: number;
  assembly_fgk_basis?: number;
  assembly_fgk_satz_pct?: number;
  assembly_fgk_betrag?: number;
  kaufteile_einkauf_gesamt?: number;
  kaufteile_mgk_gesamt?: number;
  kaufteile_oem_handling_gesamt?: number;
  kaufteile_sga_gesamt?: number;
  kostenbasis_vor_ausschuss?: number;
  assembly_ausschuss_zuschlag?: number;
  kostenbasis_nach_assembly?: number;
  gewinn_pct?: number;
  gewinn_betrag?: number;
  baugruppenpreis_je_stueck: number;
  jahresstueckzahl: number;
  jahresumsatz: number;
  investitionen_gesamt: number;
  einzelteile: Array<{
    id_ref: number;
    bezeichnung: string;
    menge: number;
    einzelpreis: number;
    zwischensumme: number;
    detail: { teilenummer: string; reihenfolge: number };
  }>;
  kaufteile: Array<{
    id_ref: number;
    bezeichnung: string;
    menge: number;
    einzelpreis: number;
    zwischensumme: number;
    detail: { lieferant: string; reihenfolge: number };
  }>;
  veredelungen: Array<{
    veredelungsschritt_id: number;
    bezeichnung: string;
    reihenfolge: number;
    kosten_je_stueck: number;
    mengenfaktor: number;
    zwischensumme: number;
  }>;
  investitionen: InvestitionAnzeige[];
}

export interface BaugruppeBloecke {
  zusammenfassung?: Record<string, number>;
  einzelteile?: Record<string, number>;
  kaufteile?: Record<string, number>;
  veredelung?: Record<string, number>;
  investitionen?: Record<string, number>;
}

export interface BaugruppeCalcResponse {
  ergebnis: BaugruppeErgebnis;
  bloecke: BaugruppeBloecke;
}

export interface BaugruppeFormData {
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  project_id: number | null;
  customer_id: number | null;
  program_id: number | null;
  werk_id: number | null;
  jahresstueckzahl: number;
  beschreibung: string;
  status: string;
  aktiv: boolean;
}

export interface BaugruppeListItem {
  id: number;
  name: string;
  teilenummer: string;
  kunde: string;
  projekt: string;
  project_id: number | null;
  jahresstueckzahl: number;
  status: string;
  baugruppenpreis_je_stueck: number | null;
  updated_at: string;
  aktiv: boolean;
}

export interface Baugruppe extends BaugruppeFormData {
  id: number;
  ergebnis: BaugruppeErgebnis | null;
  ergebnis_bloecke: BaugruppeBloecke | null;
  created_at: string;
  updated_at: string;
  spritzguss_zuordnungen: SpritzgussZuordnung[];
  kaufteil_zuordnungen: KaufteilZuordnung[];
  veredelung_zuordnungen: VeredelungZuordnung[];
  investitionen: InvestitionAnzeige[];
}

export interface Kaufteil {
  id: number;
  artikelnummer: string;
  bezeichnung: string;
  beschreibung: string;
  lieferant: string;
  einheit: string;
  preis: number;
  waehrung: string;
  gueltig_ab: string | null;
  aktiv: boolean;
  nominierung: "selbstnominiert" | "oem_nominiert" | null;
  sga_override_aktiv?: boolean;
  sga_satz_manuell?: number | null;
  customer_id: number | null;
  program_id: number | null;
  project_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface SelectedSpritzguss extends SpritzgussZuordnungInput {
  bezeichnung: string;
  teilenummer: string;
  endpreis: number;
  zwischensumme?: number;
}

export interface SelectedKaufteil extends KaufteilZuordnungInput {
  bezeichnung: string;
  lieferant: string;
  preis: number;
  zwischensumme?: number;
}

export interface SelectedVeredelung extends VeredelungZuordnungInput {
  bezeichnung: string;
  kosten: number;
  zwischensumme?: number;
}

export function emptyBaugruppeForm(): BaugruppeFormData {
  return {
    name: "",
    teilenummer: "",
    kunde: "",
    projekt: "",
    project_id: null,
    customer_id: null,
    program_id: null,
    werk_id: null,
    jahresstueckzahl: 0,
    beschreibung: "",
    status: "entwurf",
    aktiv: true,
  };
}
