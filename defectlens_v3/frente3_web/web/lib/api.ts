/*
 * Conversa com a API do Django.
 */

// =============================================================
// TIPOS — o mesmo formato que a Frente 2 devolve
// =============================================================

export type Situacao = "avaliado";

export type NivelArquivo = "alto" | "medio" | "baixo";

export interface ArquivoAnalisado {
  caminho: string;
  situacao: Situacao;
  probabilidade: number;
  nivel: NivelArquivo;
  posicao: number;
  motivos: string[];
  metricas: Record<string, number | null>;
}

export interface Validacao {
  auc_mediano: number | null;
  auc_melhor_baseline: number | null;
  topo_10: number | null;
  taxa_base: number | null;
  repositorios: number | null;
  erro_porcentagem_pp: number | null;
  erro_porcentagem_mediano_pp: number | null;
  limiar: { precisao: number; revocacao: number; f1: number; marcados: number; base: number } | null;
}

export interface Resultado {
  repositorio: string;
  ramo: string;
  commit: string;
  data_commit: string;
  commits: number;
  modelo: { nome: string; limiar: number; treinado_em: string | null; validacao: Validacao | null };
  resumo: {
    avaliados: number;
    porcentagem_estimada: number;
    porcentagem_minima: number;
    porcentagem_maxima: number;
    arquivos_esperados: number;
    risco_alto: number;
    porcentagem_acima_do_limiar: number;
    risco_maximo: number;
    limiar: number;
    erro_validacao_pp: number;
    distribuicao: number[];
    commits: number;
    consertos: number;
    autores: number;
  };
  arquivos: ArquivoAnalisado[];
  lista_cortada: boolean;
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
  porcentagem_estimada: number | null;
}

export interface Modelo {
  versao: string;
  rotulo: string;
  limiar: number;
  features: string[];
  treinado_em: string | null;
  treino: { retratos: number; repositorios: number; taxa_base: number; datas: string[] };
  validacao: Validacao;
  importancia: { feature: string; queda_auc: number }[];
  uso: { analises: number; repositorios: number; arquivos_avaliados: number };
}

const API_EXTERNA = (process.env.NEXT_PUBLIC_DEFECTLENS_API ?? "").replace(/\/+$/, "");

// =============================================================
// Endereco Da Api
// -------------------------------------------------------------
// Monta a URL: direto na API externa quando configurada, ou pelo proxy
// =============================================================
function enderecoDaApi(caminho: string): string {
  return API_EXTERNA ? `${API_EXTERNA}/api/${caminho.replace(/\/?$/, "/")}` : `/api/${caminho}`;
}

// =============================================================
// Pedir
// -------------------------------------------------------------
// fetch com a mensagem de erro da API, quando houver uma
// =============================================================
async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;

  try {
    resposta = await fetch(enderecoDaApi(caminho), {
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
      corpo?.detail ??
      corpo?.endereco?.[0] ??
      (resposta.status === 429
        ? "Muitos pedidos em pouco tempo. Aguarde um pouco e tente de novo."
        : resposta.status >= 500
          ? "O servidor da API não respondeu. O Django está rodando?"
          : `Erro ${resposta.status}`);
    throw new Error(mensagem);
  }

  return corpo as T;
}

// =============================================================
// CHAMADAS
// =============================================================

// =============================================================
// Buscar Modelo
// -------------------------------------------------------------
// Pede o resumo do modelo em uso
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
