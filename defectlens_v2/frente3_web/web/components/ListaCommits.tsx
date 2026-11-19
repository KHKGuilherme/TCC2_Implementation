/*
 * Commits recentes em ordem de prioridade para revisão, por maior
 * risco ou por melhor custo-benefício.
 */

import type { CommitAvaliado, Resultado } from "@/lib/api";
import { CLASSE_DA_FAIXA, decimal, formatarData, inteiro, porcento } from "@/lib/formato";

export type Ordem = "risco" | "custo";

const VISIVEIS = 25;

interface Props {
  resultado: Resultado;
  ordem: Ordem;
  mudarOrdem: (ordem: Ordem) => void;
  selecionado: string | null;
  selecionar: (hash: string) => void;
  mostrarTodos: boolean;
  alternarTodos: () => void;
}

// =============================================================
// Ordenar
// -------------------------------------------------------------
// Os commits na ordem escolhida
// =============================================================
export function ordenar(commits: CommitAvaliado[], ordem: Ordem): CommitAvaliado[] {
  const chave = ordem === "risco" ? "posicao_risco" : "posicao_custo";
  return [...commits].sort((a, b) => a[chave] - b[chave]);
}

// =============================================================
// Lista Commits
// -------------------------------------------------------------
// A lista de prioridade, com a troca de ordem
// =============================================================
export default function ListaCommits({ resultado, ordem, mudarOrdem, selecionado, selecionar, mostrarTodos, alternarTodos }: Props) {
  const ordenados = ordenar(resultado.commits, ordem);
  const exibidos = mostrarTodos ? ordenados : ordenados.slice(0, VISIVEIS);
  const { janela } = resultado;

  return (
    <section className="cartao revisao">
      <div className="revisao-cabecalho">
        <h2 className="titulo-cartao">Commits para revisar</h2>
        <div className="alternador" role="group" aria-label="Ordem da lista">
          <button type="button" className={ordem === "risco" ? "ativo" : ""} onClick={() => mudarOrdem("risco")}>
            maior risco
          </button>
          <button type="button" className={ordem === "custo" ? "ativo" : ""} onClick={() => mudarOrdem("custo")}>
            custo-benefício
          </button>
        </div>
      </div>

      <p className="revisao-explicacao">
        {janela.estendida
          ? `Poucos commits nos últimos ${janela.dias} dias: a lista vai de ${formatarData(janela.inicio)} a ${formatarData(janela.referencia)}. `
          : `Commits dos ${janela.dias} dias até ${formatarData(janela.referencia)}, último commit do repositório. `}
        {ordem === "risco"
          ? "Ordem pela nota de risco: os commits com mais chance de terem introduzido um defeito vêm primeiro, e costumam ser os maiores."
          : "Ordem pela chance dividida pelas linhas alteradas: cobre mais risco por linha lida, e favorece commits pequenos."}
      </p>

      <ol className="revisao-lista">
        {exibidos.map((commit) => (
          <li key={commit.hash}>
            <button
              type="button"
              className={`revisao-commit ${commit.hash === selecionado ? "revisao-commit-ativo" : ""}`}
              onClick={() => selecionar(commit.hash)}
            >
              <span className="revisao-posicao">{ordem === "risco" ? commit.posicao_risco : commit.posicao_custo}</span>
              <span className={`revisao-risco cor-${CLASSE_DA_FAIXA[commit.faixa]}`}>
                {decimal(commit.nota, 2)}
                <small>{commit.faixa}</small>
              </span>
              <span className="revisao-corpo">
                <span className="revisao-assunto">{commit.assunto || "(sem mensagem)"}</span>
                <span className="revisao-meta">
                  <code>{commit.hash.slice(0, 10)}</code>
                  <span>{formatarData(commit.data)}</span>
                  <span>{commit.autor}</span>
                  <span>
                    {inteiro(commit.arquivos)} {commit.arquivos === 1 ? "arquivo" : "arquivos"}
                  </span>
                  <span>
                    +{inteiro(commit.adicionadas)} −{inteiro(commit.removidas)}
                  </span>
                  <span>chance estimada {porcento(commit.chance, 0)}</span>
                </span>
              </span>
            </button>
          </li>
        ))}
      </ol>

      {ordenados.length > VISIVEIS && (
        <button type="button" className="botao-secundario revisao-mais" onClick={alternarTodos}>
          {mostrarTodos ? "Mostrar menos" : `Mostrar os ${ordenados.length} commits`}
        </button>
      )}
    </section>
  );
}
