import { LOCALES, type Locale } from "../i18n/types";
import { useLocale } from "../i18n/LocaleContext";

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();

  return (
    <label className="flex items-center gap-2 text-sm text-app-muted">
      <span className="sr-only">{t("language.switchTo")}</span>
      <select
        aria-label={t("common.language")}
        className="rounded-app border border-app-border-strong bg-white px-2.5 py-1.5 text-sm font-medium text-app-heading shadow-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        data-testid="language-switcher"
      >
        {LOCALES.map((item) => (
          <option key={item.code} value={item.code}>
            {item.nativeLabel}
          </option>
        ))}
      </select>
    </label>
  );
}
