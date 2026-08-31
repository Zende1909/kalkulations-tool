"""SQL-Snippets für Test-Schemas (Maschinengröße / Materialdruck)."""

MATERIAL_INJECTION_PRESSURE_COLUMN = "injection_pressure_kg_cm2 FLOAT NOT NULL DEFAULT 500"

SPRITZGUSS_SIZING_COLUMNS = """
                    maschinen_groesse_modus VARCHAR(16),
                    maschinen_groesse_breite_mm FLOAT,
                    maschinen_groesse_laenge_mm FLOAT,
                    maschinen_groesse_oeffnungen_pct FLOAT,
                    maschinen_groesse_proj_flaeche_mm2 FLOAT,
                    maschinen_groesse_schwindung_pct FLOAT,
                    maschinen_groesse_injection_pressure_kg_cm2 FLOAT,
                    maschinen_groesse_proj_flaeche_netto_mm2 FLOAT,
                    maschinen_groesse_zuhaltekraft_ohne_sicherheit_t FLOAT,
                    maschinen_groesse_sicherheitszuschlag_faktor FLOAT,
                    maschinen_groesse_zuhaltekraft_erforderlich_t FLOAT,
                    maschinen_groesse_empfohlene_maschine_id INTEGER,
                    maschinen_groesse_warnung VARCHAR(512)"""

SPRITZGUSS_ZYKLUSZEIT_COLUMNS = """
                    zykluszeit_quelle VARCHAR(16),
                    zykluszeit_wandstaerke_mm FLOAT,
                    zykluszeit_variante INTEGER,
                    zykluszeit_kuehlfaktor FLOAT,
                    zykluszeit_komponenten INTEGER,
                    zykluszeit_nz_werkzeug_schliessen_s FLOAT,
                    zykluszeit_nz_duese_anlegen_s FLOAT,
                    zykluszeit_nz_einspritzen_s FLOAT,
                    zykluszeit_nz_werkzeug_oeffnen_s FLOAT,
                    zykluszeit_nz_auswerfen_s FLOAT,
                    zykluszeit_nz_kernzug_s FLOAT,
                    zykluszeit_nz_ausschrauben_s FLOAT,
                    zykluszeit_nz_einlegen_s FLOAT,
                    zykluszeit_nz_ausblasen_s FLOAT,
                    zykluszeit_temperaturleitfaehigkeit_m2_s FLOAT,
                    zykluszeit_optimale_kuehlzeit_s FLOAT,
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512)"""

MATERIAL_THERMIK_COLUMNS = """
                    materialgruppe VARCHAR(32),
                    schmelzdichte_kg_m3 FLOAT,
                    waermekapazitaet_j_kg_k FLOAT,
                    waermeleitfaehigkeit_w_m_k FLOAT,
                    werkzeugtemperatur_c FLOAT,
                    schmelzetemperatur_c FLOAT,
                    entformungstemperatur_c FLOAT"""
