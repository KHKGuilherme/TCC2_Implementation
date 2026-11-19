/*
 * Detalhe do arquivo selecionado na árvore.
 */

import type { ArquivoAnalisado, Resultado } from "@/lib/api";
import { nivel, porcento, ROTULO_NIVEL } from "@/lib/arvore";

interface Props {
  arquivo: ArquivoAnalisado | null;
  resultado: Resultado;
}

const MEDIDAS: { coluna: string; rotulo: string }[] = [
  { coluna: "linhas_estimadas", rotulo: "Linhas (estimadas pelo histórico)" },
  { coluna: "revisoes", rotulo: "Commits que alteraram o arquivo" },
  { coluna: "autores", rotulo: "Autores" },
  { coluna: "idade_dias", rotulo: "Idade (dias)" },
  { coluna: "dias_desde_ultima", rotulo: "Dias desde a última alteração" },
  { coluna: "commits_365", rotulo: "Commits no último ano" },
  { coluna: "churn_365", rotulo: "Linhas mexidas no último ano" },
  { coluna: "consertos", rotulo: "Commits de conserto anteriores" },
  { coluna: "dias_desde_conserto", rotulo: "Dias desde o último conserto" },
  { coluna: "commits_desde_conserto", rotulo: "Commits desde o último conserto" },
  { coluna: "adicionadas_desde_conserto", rotulo: "Linhas novas desde o último conserto" },
];

// =============================================================
// Formatar
// -------------------------------------------------------------
// Número legível, sem casas decimais à toa
// =============================================================
function formatar(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return Math.round(valor).toLocaleString("pt-BR");
}

// =============================================================
// Painel Arquivo
// -------------------------------------------------------------
// Chance, motivos e medidas do arquivo
// =============================================================
export default function PainelArquivo({ arquivo, resultado }: Props) {
  if (!arquivo) {
    return (
      <aside className="cartao painel painel-vazio">
        <p>Escolha um arquivo na árvore para ver os detalhes.</p>
      </aside>
    );
  }

  const limiar = resultado.modelo.limiar;
  const faixa = nivel(arquivo.probabilidade, limiar);
  const linkGithub = `https://github.com/${resultado.repositorio}/blob/${resultado.commit}/${arquivo.caminho}`;
  const escala = Math.max(resultado.resumo.risco_maximo, limiar, 0.01);

  return (
    <aside className="cartao painel">
      <p className="painel-caminho">{arquivo.caminho}</p>

      <div className="painel-nota">
        <span className={`painel-numero cor-${faixa}`}>{porcento(arquivo.probabilidade)}</span>
        <div>
          <span className={`selo-nivel fundo-${faixa}`}>{ROTULO_NIVEL[faixa]}</span>
          <p className="painel-posicao">
            {arquivo.posicao}º de {resultado.resumo.avaliados} arquivos avaliados
          </p>
        </div>
      </div>

      <div className="regua" aria-hidden>
        <span
          className={`regua-valor fundo-${faixa}`}
          style={{ width: `${Math.min(100, (100 * arquivo.probabilidade) / escala)}%` }}
        />
        <span className="regua-limiar" style={{ left: `${Math.min(100, (100 * limiar) / escala)}%` }} />
      </div>
      <p className="regua-legenda">
        chance de o arquivo ter um defeito ainda não consertado · limiar do modelo: {porcento(limiar, 0)}
      </p>

      {arquivo.motivos.length > 0 && (
        <p className="painel-commit">
          Neste repositório, o arquivo se destaca por: {arquivo.motivos.join("; ")}.
        </p>
      )}

      <table className="tabela-metricas">
        <thead>
          <tr>
            <th>Medida do histórico</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {MEDIDAS.map((m) => (
            <tr key={m.coluna}>
              <td>{m.rotulo}</td>
              <td className="numero">{formatar(arquivo.metricas[m.coluna])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="nota-rodape">
        A chance é estatística: vem do histórico do arquivo, comparado com arquivos de 20 projetos em que o defeito
        foi confirmado depois por um conserto. Não aponta a linha do defeito.
      </p>

      <a className="link-github" href={linkGithub} target="_blank" rel="noreferrer">
        Abrir no GitHub ↗
      </a>
    </aside>
  );
}
