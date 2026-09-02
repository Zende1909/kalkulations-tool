import { navItems, type NavItem } from "./navConfig";

function titleFromItems(pathname: string, items: NavItem[]): string | null {
  for (const item of items) {
    if ("children" in item) {
      for (const child of item.children) {
        if (pathname === child.to || pathname.startsWith(`${child.to}/`)) {
          return child.label;
        }
      }
    } else if (item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)) {
      return item.label;
    }
  }
  return null;
}

export function getPageTitle(pathname: string): string {
  return titleFromItems(pathname, navItems) ?? "Kalkulations-Tool";
}

export function getPageDescription(pathname: string): string | undefined {
  const descriptions: Record<string, string> = {
    "/": "Übersicht über Kalkulationen, Kennzahlen und Auslastung.",
    "/stammdaten/materialien":
      "Materialstammdaten mit Preisen, Dichte, Einspritzdruck und Materialgruppe für Zykluszeit-Schätzungen.",
    "/stammdaten/materialgruppen":
      "Thermische Kennwerte und Gruppen für die automatische Zykluszeit-Berechnung.",
    "/stammdaten/maschinen": "Maschinenstammdaten inklusive Werkzuordnung und Kostenparameter.",
    "/stammdaten/werke": "Werks- und Standortparameter für Kapazität, Energie und Gemeinkosten.",
    "/stammdaten/zuschlagssaetze": "Zentrale Zuschlagssätze für MGK, FGK, VVGK, Gewinn und Skonto.",
    "/stammdaten/kaufteile": "Kaufteil-Stammdaten für Baugruppen- und Einzelkalkulationen.",
    "/spritzguss": "Einzelteilkalkulation Spritzguss mit Maschinen-, Material- und Zykluszeitlogik.",
    "/baugruppen": "Baugruppenkalkulation aus Einzelteilen, Kaufteilen und Veredelung.",
    "/investitionen": "Werksinvestitionen und CAPEX-Zuordnung zu Projekten und Baugruppen.",
    "/business-case": "Wirtschaftlichkeitsbetrachtung und Szenariovergleich.",
  };

  if (descriptions[pathname]) return descriptions[pathname];

  const base = pathname.split("/").slice(0, 2).join("/");
  return descriptions[base];
}
