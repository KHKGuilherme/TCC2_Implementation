import type { components } from "@/tipos/api";

type Esquemas = components["schemas"];

export type Analise = Esquemas["Analise"];
export type AnaliseResumo = Esquemas["AnaliseResumo"];
export type ArquivoAnalisado = Esquemas["ArquivoAnalisado"];
export type Modelo = Esquemas["Modelo"];
export type Resultado = Esquemas["Resultado"];
export type Validacao = Esquemas["Validacao"];
export type Status = Analise["status"];

const BASE = (process.env.NEXT_PUBLIC_DEFECTLENS_API ?? "").replace(/\/+$/, "");

export const enderecoDaApi = (caminho: string) => `${BASE}/api/${caminho.replace(/\/?$/, "/")}`;

async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;

  try {
    resposta = await fetch(enderecoDaApi(caminho), {
      ...opcoes,
      headers: { "Content-Type": "application/json", ...opcoes?.headers },
      cache: "no-store",
    });
  } catch {
    throw new Error("Não foi possível falar com a API.");
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
          ? "A API não respondeu."
          : `Erro ${resposta.status}`);
    throw new Error(mensagem);
  }

  return corpo as T;
}

export const buscarModelo = () => pedir<Modelo>("modelo");

export const buscarRecentes = () => pedir<AnaliseResumo[]>("analises");

export const buscarAnalise = (id: string) => pedir<Analise>(`analises/${id}`);

export const pedirAnalise = (endereco: string, ramo?: string) =>
  pedir<Esquemas["PedidoAceito"]>("analises", {
    method: "POST",
    body: JSON.stringify({ endereco, ramo: ramo ?? "" }),
  });
