/*
 * Formatação de números, datas e faixas de risco.
 */

import type { Faixa } from "./api";

export const CLASSE_DA_FAIXA: Record<Faixa, string> = {
  alto: "alto",
  médio: "medio",
  baixo: "baixo",
};

// =============================================================
// Porcento
// -------------------------------------------------------------
// De 0,1234 para 12,3%
// =============================================================
export function porcento(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return `${(100 * valor).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })}%`;
}

// =============================================================
// Decimal
// -------------------------------------------------------------
// Número com vírgula e casas fixas
// =============================================================
export function decimal(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

// =============================================================
// Inteiro
// -------------------------------------------------------------
// Número inteiro com separador de milhar
// =============================================================
export function inteiro(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return Math.round(valor).toLocaleString("pt-BR");
}

// =============================================================
// Formatar Data
// -------------------------------------------------------------
// De 2026-03-12 para 12/03/2026, sem passar por fuso horário
// =============================================================
export function formatarData(iso: string): string {
  return iso.split("-").reverse().join("/");
}

// =============================================================
// Dias Desde
// -------------------------------------------------------------
// Dias entre duas datas ISO
// =============================================================
export function diasEntre(inicio: string, fim: string): number {
  return (Date.parse(fim) - Date.parse(inicio)) / 86_400_000;
}
