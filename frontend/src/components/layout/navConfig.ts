/** Sichtbare Hauptnavigation (ohne Router-Abhängigkeit). */

export type NavChild = { to: string; label: string };
export type NavLeaf = { to: string; label: string; end?: boolean };
export type NavGroup = { label: string; children: NavChild[] };
export type NavItem = NavLeaf | NavGroup;

export const stammdatenChildren: NavChild[] = [
  { to: "/stammdaten/materialgruppen", label: "Materialgruppen" },
  { to: "/stammdaten/materialien", label: "Materialien" },
  { to: "/stammdaten/laender", label: "Länder" },
  { to: "/stammdaten/werke", label: "Werke" },
  { to: "/stammdaten/werk-zuschlaege", label: "Werk-Zuschläge" },
  { to: "/stammdaten/maschinen", label: "Maschinen" },
  { to: "/stammdaten/lohnkosten", label: "Lohnkosten" },
  { to: "/stammdaten/zuschlagssaetze", label: "Zuschlagssätze" },
  { to: "/stammdaten/hierarchie", label: "Kunden, Programme & Projekte" },
];

/** Reihenfolge: … Einzelteilkalkulation → Kaufteile → Veredelung … */
export const navItems: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  {
    label: "Stammdaten",
    children: stammdatenChildren,
  },
  { to: "/spritzguss", label: "Einzelteilkalkulation" },
  { to: "/stammdaten/kaufteile", label: "Kaufteile" },
  { to: "/veredelung", label: "Veredelung" },
  { to: "/baugruppen", label: "Baugruppen" },
  { to: "/baugruppen/familien", label: "Baugruppenfamilien" },
  { to: "/maschinenauslastung", label: "Maschinenauslastung" },
  { to: "/investitionen", label: "Investitionen" },
  { to: "/business-case", label: "Business Case" },
];

export function isStammdatenSectionPath(pathname: string): boolean {
  return stammdatenChildren.some(
    (child) => pathname === child.to || pathname.startsWith(`${child.to}/`),
  );
}
