/*
 * Conversa com a API do Django.
 */

// =============================================================
// TIPOS — o mesmo formato que a Frente 2 devolve
// =============================================================

export type Situacao =
  | "avaliado"
  | "teste"
  | "ignorado"
  | "vazio"
  | "grande"
  | "sem_parse"
  | "sem_funcoes";

export type ValorComPercentil = [number | null, number | null];

export interface CommitResumo {
  hash: string;
  data: string;
  arquivos: number;
  adicionadas: number;
  removidas: number;
}

export interface CommitParaRevisar extends CommitResumo {
  risco: number;
  avaliados: string[];
}

export interface Revisao {
  janela_dias: number;
  referencia: string;
  recentes: number;
  fora_da_janela: number;
  commits: CommitParaRevisar[];
}

export interface ArquivoAnalisado {
  caminho: string;
  situacao: Situacao;
  probabilidade?: number;
  posicao?: number;
  ultimo_commit?: CommitResumo | null;
  metricas?: Record<string, ValorComPercentil>;
}

export interface MetricaExibida {
  coluna: string;
  rotulo: string;
  melhor: "menor" | "maior";
}

export interface Resultado {
  repositorio: string;
  ramo: string;
  commit: string;
  commits: number;
  modelo: { nome: string; limiar: number };
  resumo: {
    arquivos_py: number;
    avaliados: number;
    risco_alto: number;
    risco_maximo: number;
    risco_medio: number;
    por_situacao: Partial<Record<Situacao, number>>;
  };
  metricas_exibidas: MetricaExibida[];
  situacoes: Record<Situacao, string>;
  revisao?: Revisao;
  arquivos: ArquivoAnalisado[];
  aviso: string | null;
  duracao_s: number;
}

export type Status = "na_fila" | "rodando" | "concluida" | "erro";

export interface Analise {
  id: string;
  repositorio: string;
  ramo: string;
  commit: string;
  status: Status;
  etapa: string;
  progresso: number;
  mensagem: string;
  erro: string;
  criada: string;
  concluida: string | null;
  posicao_na_fila: number | null;
  resultado: Resultado | null;
}

export interface AnaliseResumo {
  id: string;
  repositorio: string;
  ramo: string;
  commit: string;
  concluida: string | null;
  avaliados: number | null;
  risco_alto: number | null;
  risco_maximo: number | null;
}

export interface Modelo {
  nome: string;
  features: number;
  limiar: number;
  metricas: Record<string, number> | null;
  projeto_novo: {
    repositorios: number;
    auc: number;
    auc_mediano: number;
    auc_retrato: number;
    base: number;
    precisao_topo: number;
    fracao_topo: number;
  } | null;
  treinado_em: string | null;
  repositorios_treino: number | null;
  tem_medias: boolean;
  importancias: { feature: string; peso: number; origem: string }[];
  uso: { analises: number; repositorios: number; arquivos_avaliados: number };
}

// =============================================================
// Pedir
// -------------------------------------------------------------
// fetch com a mensagem de erro da API, quando houver uma
// =============================================================
async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;

  try {
    resposta = await fetch(`/api/${caminho}`, {
      ...opcoes,
      headers: { "Content-Type": "application/json", ...opcoes?.headers },
      cache: "no-store",
    });
  } catch {
    throw new Error("Sem resposta do servidor. O Django está rodando?");
  }

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    const mensagem =
      corpo?.erro ??
      corpo?.endereco?.[0] ??
      (resposta.status >= 500
        ? "O servidor da API não respondeu. O Django está rodando?"
        : `Erro ${resposta.status}`);
    throw new Error(mensagem);
  }

  return corpo as T;
}

// =============================================================
// CHAMADAS
// =============================================================

export const buscarModelo = () => pedir<Modelo>("modelo");

// =============================================================
// Buscar Recentes
// -------------------------------------------------------------
// Pede as análises recentes
// =============================================================
export const buscarRecentes = () => pedir<AnaliseResumo[]>("analises");

// =============================================================
// Buscar Analise
// -------------------------------------------------------------
// Pede uma análise pelo identificador
// =============================================================
export const buscarAnalise = (id: string) => pedir<Analise>(`analises/${id}`);

// =============================================================
// Pedir Analise
// -------------------------------------------------------------
// Envia um pedido de análise
// =============================================================
export const pedirAnalise = (endereco: string, ramo?: string) =>
  pedir<{ id: string; reaproveitada: boolean }>("analises", {
    method: "POST",
    body: JSON.stringify({ endereco, ramo: ramo ?? "" }),
  });