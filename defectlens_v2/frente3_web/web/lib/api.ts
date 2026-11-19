/*
 * Conversa com a API do Django.
 */

// =============================================================
// TIPOS — o mesmo formato que a Frente 2 devolve
// =============================================================

export type Faixa = "alto" | "médio" | "baixo";

export interface Fator {
  feature: string;
  nome: string;
  grupo: string;
  valor: number | null;
  mediana_do_treino: number | null;
  percentil: number;
  efeito: number;
}

export interface ArquivoAlterado {
  caminho: string;
  adicionadas: number;
  removidas: number;
  revisoes: number;
  autores: number;
  idade_dias: number | null;
  novo: boolean;
}

export interface CommitAvaliado {
  hash: string;
  data: string;
  autor: string;
  assunto: string;
  arquivos: number;
  arquivos_py: number;
  adicionadas: number;
  removidas: number;
  nota: number;
  chance: number;
  percentil: number;
  faixa: Faixa;
  posicao_risco: number;
  posicao_custo: number;
  arquivo_decisivo: string;
  fatores: Fator[];
  arquivos_alterados: ArquivoAlterado[];
}

export interface PontoDoTempo {
  hash: string;
  data: string;
  nota: number;
  linhas: number;
  faixa: Faixa;
}

export interface CommitForaDoDominio {
  hash: string;
  data: string;
  autor: string;
  assunto: string;
  arquivos: number;
  adicionadas: number;
  removidas: number;
  motivo: string | null;
}

export interface ArquivoEmDestaque {
  caminho: string;
  commits: number;
  risco_somado: number;
  maior_chance: number;
  adicionadas: number;
  removidas: number;
  revisoes: number;
  autores: number;
}

export interface FaixaDeRisco {
  faixa: Faixa;
  nota_de: number;
  quantil_de: number;
  taxa_de_defeito: number;
  taxa_geral: number;
  parcela_dos_defeitos: number;
}

export interface FaixaDoHistograma {
  de: number;
  ate: number;
  repositorio: number;
  referencia: number;
}

export type Curva = [number, number][];

export interface Resultado {
  repositorio: string;
  ramo: string;
  commit: string;
  commits_no_historico: number;
  tamanho_mb: number | null;
  modelo: {
    nome: string;
    versao: string;
    features: number;
    faixas: FaixaDeRisco[];
    taxa_de_referencia: number;
    dominio: { maximo_linhas: number; maximo_arquivos: number; minimo_adicionadas: number };
  };
  janela: {
    dias: number;
    referencia: string;
    inicio: string;
    estendida: boolean;
    commits_no_periodo: number;
    sem_py: number;
    fora_do_dominio: number;
    avaliados: number;
  };
  resumo: {
    avaliados: number;
    risco_alto: number;
    risco_medio: number;
    risco_baixo: number;
    risco_maximo: number;
    chance_maxima: number;
    defeitos_esperados: number;
    linhas_alteradas: number;
    fora_do_dominio: number;
  };
  commits: CommitAvaliado[];
  linha_do_tempo: PontoDoTempo[];
  curvas: { risco: Curva; custo: Curva; cronologica: Curva };
  distribuicao: FaixaDoHistograma[];
  arquivos: ArquivoEmDestaque[];
  fora_do_dominio: CommitForaDoDominio[];
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

export interface MedidasDoMetodo {
  nome: string;
  repositorios: number;
  commits: number;
  base: number;
  auc: number;
  auc_agregado: number;
  topo_10: number;
  popt_densidade: number;
  revocacao_esforco_risco: number;
  revocacao_esforco_densidade: number;
}

export interface Importancia {
  feature: string;
  nome: string;
  grupo: string;
  queda_auc: number;
}

export interface Modelo {
  nome: string;
  versao: string;
  algoritmo: string;
  features: number;
  treinado_em: string;
  repositorios_treino: number;
  commits_treino: number;
  faixas: FaixaDeRisco[];
  referencia: { commits: number; taxa_de_defeito: number };
  calibracao_medida: { brier: number; erro_calibracao: number };
  dominio: { maximo_linhas: number; maximo_arquivos: number; minimo_adicionadas: number };
  metricas: Record<"principal" | "sem_filtro" | "natural", Record<string, MedidasDoMetodo>>;
  importancia: Importancia[];
  uso: { analises: number; repositorios: number; commits_avaliados: number };
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
      (resposta.status === 429
        ? "Muitos pedidos seguidos. Tente de novo mais tarde."
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
// Pede a descrição do modelo em uso
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
