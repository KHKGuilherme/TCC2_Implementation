/*
 * Converte a lista plana de arquivos em árvore de pastas.
 */

import type { ArquivoAnalisado } from "./api";

export interface No {
  nome: string;
  caminho: string;
  tipo: "pasta" | "arquivo";
  filhos: No[];
  arquivo?: ArquivoAnalisado;
  risco: number | null;
  avaliados: number;
  alto: number;
}

// =============================================================
// Nivel
// -------------------------------------------------------------
// Faixa de cor de uma probabilidade
// =============================================================
export type Nivel = "alto" | "medio" | "baixo" | "nenhum";

// =============================================================
// Nivel
// -------------------------------------------------------------
// Faixa de cor de uma nota
// =============================================================
export function nivel(risco: number | null | undefined, limiar: number): Nivel {
  if (risco === null || risco === undefined) return "nenhum";
  if (risco >= limiar) return "alto";
  if (risco >= limiar / 2) return "medio";
  return "baixo";
}

export const ROTULO_NIVEL: Record<Nivel, string> = {
  alto: "chance alta",
  medio: "chance média",
  baixo: "chance baixa",
  nenhum: "não avaliado",
};

// =============================================================
// Porcento
// -------------------------------------------------------------
// Formata uma fração como porcentagem
// =============================================================
export function porcento(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined) return "—";
  return `${(100 * valor).toFixed(casas)}%`;
}

// =============================================================
// Montar Arvore
// -------------------------------------------------------------
// Pastas a partir dos caminhos, com o risco subindo
// =============================================================
export function montarArvore(arquivos: ArquivoAnalisado[], limiar: number): No {
  const raiz: No = novaPasta("", "");

  for (const arquivo of arquivos) {
    const partes = arquivo.caminho.split("/");
    let atual = raiz;

    partes.slice(0, -1).forEach((parte, i) => {
      const caminho = partes.slice(0, i + 1).join("/");
      let pasta = atual.filhos.find((f) => f.tipo === "pasta" && f.nome === parte);
      if (!pasta) {
        pasta = novaPasta(parte, caminho);
        atual.filhos.push(pasta);
      }
      atual = pasta;
    });

    atual.filhos.push({
      nome: partes[partes.length - 1],
      caminho: arquivo.caminho,
      tipo: "arquivo",
      filhos: [],
      arquivo,
      risco: arquivo.situacao === "avaliado" ? (arquivo.probabilidade ?? null) : null,
      avaliados: arquivo.situacao === "avaliado" ? 1 : 0,
      alto: (arquivo.probabilidade ?? 0) >= limiar ? 1 : 0,
    });
  }

  somar(raiz);
  return compactar(raiz);
}

// =============================================================
// Nova Pasta
// -------------------------------------------------------------
// Cria um nó de pasta vazio
// =============================================================
function novaPasta(nome: string, caminho: string): No {
  return { nome, caminho, tipo: "pasta", filhos: [], risco: null, avaliados: 0, alto: 0 };
}

// =============================================================
// Somar
// -------------------------------------------------------------
// Leva o maior risco e as contagens até a raiz
// =============================================================
function somar(no: No): void {
  if (no.tipo === "arquivo") return;

  for (const filho of no.filhos) {
    somar(filho);
    if (filho.risco !== null && (no.risco === null || filho.risco > no.risco)) {
      no.risco = filho.risco;
    }
    no.avaliados += filho.avaliados;
    no.alto += filho.alto;
  }
}

// =============================================================
// Compactar
// -------------------------------------------------------------
// Junta a pasta que só contém outra pasta
// =============================================================
function compactar(no: No): No {
  no.filhos = no.filhos.map(compactar);

  if (no.tipo === "pasta" && no.nome && no.filhos.length === 1 && no.filhos[0].tipo === "pasta") {
    const unico = no.filhos[0];
    return { ...unico, nome: `${no.nome}/${unico.nome}` };
  }

  return no;
}

// =============================================================
// Ordenar
// -------------------------------------------------------------
// Pastas antes de arquivos; dentro de cada grupo, pelo critério
// =============================================================
export type Ordem = "risco" | "nome";

// =============================================================
// Ordenar
// -------------------------------------------------------------
// Ordena os filhos por risco ou por nome
// =============================================================
export function ordenar(filhos: No[], ordem: Ordem): No[] {
  return [...filhos].sort((a, b) => {
    if (a.tipo !== b.tipo) return a.tipo === "pasta" ? -1 : 1;

    if (ordem === "risco") {
      const ra = a.risco ?? -1;
      const rb = b.risco ?? -1;
      if (ra !== rb) return rb - ra;
    }

    return a.nome.localeCompare(b.nome);
  });
}

// =============================================================
// Filtrar
// -------------------------------------------------------------
// Mantém os arquivos que casam e as pastas no caminho deles
// =============================================================
export function filtrar(no: No, aceitar: (a: ArquivoAnalisado) => boolean): No | null {
  if (no.tipo === "arquivo") {
    return no.arquivo && aceitar(no.arquivo) ? no : null;
  }

  const filhos = no.filhos.map((f) => filtrar(f, aceitar)).filter((f): f is No => f !== null);
  if (filhos.length === 0 && no.nome) return null;

  return { ...no, filhos };
}

// =============================================================
// Pastas Ate
// -------------------------------------------------------------
// Os caminhos de pasta que precisam abrir para mostrar um arquivo
// =============================================================
export function pastasAte(raiz: No, caminho: string): string[] {
  const abertas: string[] = [];

  function descer(no: No): boolean {
    if (no.tipo === "arquivo") return no.caminho === caminho;
    for (const filho of no.filhos) {
      if (descer(filho)) {
        if (no.caminho) abertas.push(no.caminho);
        return true;
      }
    }
    return false;
  }

  descer(raiz);
  return abertas;
}