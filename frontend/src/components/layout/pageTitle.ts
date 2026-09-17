import { navItems, type NavItem } from "./navConfig";

const descriptionKeys: Record<string, string> = {
  "/": "pages.dashboardDesc",
  "/stammdaten/materialien": "pages.materialsDesc",
  "/stammdaten/materialgruppen": "pages.materialGroupsDesc",
  "/stammdaten/maschinen": "pages.machinesDesc",
  "/stammdaten/werke": "pages.plantsDesc",
  "/stammdaten/zuschlagssaetze": "pages.markupsDesc",
  "/stammdaten/kaufteile": "pages.purchasedPartsDesc",
  "/stammdaten/hierarchie": "pages.hierarchyDesc",
  "/stammdaten/laender": "pages.countriesDesc",
  "/stammdaten/werk-zuschlaege": "pages.plantMarkupsDesc",
  "/stammdaten/lohnkosten": "pages.laborCostsDesc",
  "/spritzguss": "pages.partCalculationDesc",
  "/baugruppen": "pages.assembliesDesc",
  "/investitionen": "pages.investmentsDesc",
  "/business-case": "pages.businessCaseDesc",
  "/maschinenauslastung": "pages.machineUtilizationDesc",
  "/veredelung": "pages.finishingDesc",
};

function titleKeyFromItems(pathname: string, items: NavItem[]): string | null {
  for (const item of items) {
    if ("children" in item) {
      for (const child of item.children) {
        if (pathname === child.to || pathname.startsWith(`${child.to}/`)) {
          return child.labelKey;
        }
      }
    } else if (item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)) {
      return item.labelKey;
    }
  }
  return null;
}

export function getPageTitleKey(pathname: string): string {
  return titleKeyFromItems(pathname, navItems) ?? "common.appName";
}

export function getPageDescriptionKey(pathname: string): string | undefined {
  if (descriptionKeys[pathname]) return descriptionKeys[pathname];
  const base = pathname.split("/").slice(0, 2).join("/");
  return descriptionKeys[base];
}
