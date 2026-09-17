import { catalogs, type MessageTree } from "./catalogs";
import type { Locale } from "./types";

function lookup(tree: MessageTree, path: string): string | undefined {
  const parts = path.split(".");
  let node: string | MessageTree | undefined = tree;
  for (const part of parts) {
    if (node == null || typeof node === "string") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export type TranslateParams = Record<string, string | number | null | undefined>;

export function translate(
  locale: Locale,
  key: string,
  params?: TranslateParams,
  fallback?: string,
): string {
  const raw =
    lookup(catalogs[locale], key) ??
    lookup(catalogs.de, key) ??
    fallback ??
    key;
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = params[name];
    return value == null ? "" : String(value);
  });
}
