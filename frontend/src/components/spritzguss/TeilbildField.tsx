import { useRef, useState } from "react";

import { useT } from "../../i18n";
import { processTeilbildFile, TeilbildError, teilbildSrc } from "../../utils/teilbild";
import { Button } from "../ui/Button";
import { ValidationMessage } from "../ui/ValidationMessage";

export function TeilbildField({
  mime,
  data,
  onChange,
  disabled = false,
}: {
  mime: string | null;
  data: string | null;
  onChange: (next: { mime: string | null; data: string | null }) => void;
  disabled?: boolean;
}) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const preview = teilbildSrc(mime, data);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const processed = await processTeilbildFile(file);
      onChange(processed);
    } catch (err) {
      if (err instanceof TeilbildError) {
        setError(t(err.code));
      } else {
        setError(err instanceof Error ? err.message : t("spritzguss.imageProcessFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="md:col-span-2">
      <div className="flex flex-col gap-3 rounded-app border border-app-border bg-slate-50 p-4 sm:flex-row sm:items-start">
        <div className="flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-app border border-app-border bg-white">
          {preview ? (
            <img
              src={preview}
              alt={t("spritzguss.partImagePreview")}
              className="h-full w-full object-contain"
            />
          ) : (
            <span className="px-2 text-center text-xs text-app-muted">{t("spritzguss.noImage")}</span>
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-body-lg font-medium text-app-heading">{t("spritzguss.partImage")}</p>
            <p className="text-sm text-app-muted">{t("spritzguss.partImageHint")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled || busy}
              onClick={() => inputRef.current?.click()}
            >
              {busy
                ? t("common.processing")
                : preview
                  ? t("spritzguss.replaceImage")
                  : t("spritzguss.uploadImage")}
            </Button>
            {preview && !disabled ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onChange({ mime: null, data: null })}
              >
                {t("common.remove")}
              </Button>
            ) : null}
          </div>
          {error ? <ValidationMessage variant="error">{error}</ValidationMessage> : null}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      </div>
    </div>
  );
}
