import { en } from "./en";
import type { Translations } from "./types";

// Partial-locale helper: a translation file supplies only the strings it has
// translated and every missing key falls back to English, while unknown keys
// still fail the type-check. Mirrors the desktop app's `defineLocale` so a new
// locale (e.g. Arabic) can land without hand-porting every future English key.

type TranslationOverride<T> = T extends (...args: never[]) => string
  ? T
  : T extends readonly unknown[]
    ? T
    : T extends string
      ? string
      : T extends object
        ? { [K in keyof T]?: TranslationOverride<T[K]> }
        : T;

export type TranslationOverrides = TranslationOverride<Translations>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function mergeTranslations<T>(base: T, overrides: TranslationOverride<T> | undefined): T {
  if (!isRecord(base) || !isRecord(overrides)) {
    return (overrides ?? base) as T;
  }

  const result: Record<string, unknown> = { ...base };

  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined) {
      continue;
    }

    const baseValue = result[key];
    result[key] = isRecord(baseValue) && isRecord(value) ? mergeTranslations(baseValue, value) : value;
  }

  return result as T;
}

/**
 * @param base  Catálogo sobre o qual sobrepor. O padrão é o inglês, que é o
 *   caso normal de um idioma novo. Passar outro catálogo serve para variantes
 *   regionais: `pt-BR` herda de `pt` e sobrescreve só o que difere, em vez de
 *   duplicar 634 strings que já estão certas nos dois. Sem isso, cada correção
 *   em `pt` teria que ser repetida à mão em `pt-BR` — e não seria.
 */
export function defineLocale(overrides: TranslationOverrides, base: Translations = en): Translations {
  return mergeTranslations<Translations>(base, overrides);
}
