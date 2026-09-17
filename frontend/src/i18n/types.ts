/** App locales for ZC PartCalc UI + exports. */
export type Locale = "de" | "en";

export const LOCALES: { code: Locale; label: string; nativeLabel: string }[] = [
  { code: "de", label: "German", nativeLabel: "Deutsch" },
  { code: "en", label: "English", nativeLabel: "English" },
];

export const LOCALE_STORAGE_KEY = "zc_partcalc_locale";
export const DEFAULT_LOCALE: Locale = "de";

export function normalizeLocale(value: string | null | undefined): Locale {
  const v = (value || "").trim().toLowerCase();
  if (v.startsWith("en")) return "en";
  if (v.startsWith("de")) return "de";
  return DEFAULT_LOCALE;
}
