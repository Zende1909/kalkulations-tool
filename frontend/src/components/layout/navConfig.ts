/** Sichtbare Hauptnavigation (ohne Router-Abhängigkeit). */

export type NavChild = { to: string; labelKey: string };
export type NavLeaf = { to: string; labelKey: string; end?: boolean };
export type NavGroup = { labelKey: string; children: NavChild[] };
export type NavItem = NavLeaf | NavGroup;

export const stammdatenChildren: NavChild[] = [
  { to: "/stammdaten/materialgruppen", labelKey: "nav.materialGroups" },
  { to: "/stammdaten/materialien", labelKey: "nav.materials" },
  { to: "/stammdaten/laender", labelKey: "nav.countries" },
  { to: "/stammdaten/werke", labelKey: "nav.plants" },
  { to: "/stammdaten/werk-zuschlaege", labelKey: "nav.plantMarkups" },
  { to: "/stammdaten/maschinen", labelKey: "nav.machines" },
  { to: "/stammdaten/lohnkosten", labelKey: "nav.laborCosts" },
  { to: "/stammdaten/zuschlagssaetze", labelKey: "nav.markups" },
  { to: "/stammdaten/hierarchie", labelKey: "nav.hierarchy" },
];

/** Reihenfolge: … Einzelteilkalkulation → Kaufteile → Veredelung … */
export const navItems: NavItem[] = [
  { to: "/", labelKey: "nav.dashboard", end: true },
  {
    labelKey: "nav.masterData",
    children: stammdatenChildren,
  },
  { to: "/spritzguss", labelKey: "nav.partCalculation" },
  { to: "/stammdaten/kaufteile", labelKey: "nav.purchasedParts" },
  { to: "/veredelung", labelKey: "nav.finishing" },
  { to: "/baugruppen", labelKey: "nav.assemblies" },
  { to: "/maschinenauslastung", labelKey: "nav.machineUtilization" },
  { to: "/investitionen", labelKey: "nav.investments" },
  { to: "/business-case", labelKey: "nav.businessCase" },
];

export function isStammdatenSectionPath(pathname: string): boolean {
  return stammdatenChildren.some(
    (child) => pathname === child.to || pathname.startsWith(`${child.to}/`),
  );
}
