// frente3_web\web\lib\api.ts

/*
 * Conversa com a API do Django.
 *
 * As chamadas vão para /api/..., e o next.config.ts repassa ao
 * Django. Assim o navegador só fala com um endereço e não existe
 * problema de CORS.
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

// [valor, percentil dentro do repositório]
export type ValorComPercentil = [number | null, number | null];

export interface ArquivoAnalisado {
  caminho: string;
  situacao: Situacao;
  probabilidade?: number;
  posicao?: number;
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

export const buscarRecentes = () => pedir<AnaliseResumo[]>("analises");

export const buscarAnalise = (id: string) => pedir<Analise>(`analises/${id}`);

export const pedirAnalise = (endereco: string, ramo?: string) =>
  pedir<{ id: string; reaproveitada: boolean }>("analises", {
    method: "POST",
    body: JSON.stringify({ endereco, ramo: ramo ?? "" }),
  });