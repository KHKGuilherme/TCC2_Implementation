import type { JSX } from "react";

import type { ArquivoAnalisado, Resultado } from "@/lib/api";
import { nivel, porcento, ROTULO_NIVEL } from "@/lib/arvore";

interface Props {
  arquivo: ArquivoAnalisado | null;
  resultado: Resultado;
  limiar: number;
}

const MEDIDAS: { coluna: string; rotulo: string }[] = [
  { coluna: "linhas_estimadas", rotulo: "Linhas estimadas" },
  { coluna: "revisoes", rotulo: "Commits que alteraram o arquivo" },
  { coluna: "autores", rotulo: "Autores" },
  { coluna: "idade_dias", rotulo: "Idade em dias" },
  { coluna: "dias_desde_ultima", rotulo: "Dias desde a última alteração" },
  { coluna: "commits_365", rotulo: "Commits no último ano" },
  { coluna: "churn_365", rotulo: "Linhas mexidas no último ano" },
  { coluna: "consertos", rotulo: "Commits de conserto" },
  { coluna: "dias_desde_conserto", rotulo: "Dias desde o último conserto" },
  { coluna: "commits_desde_conserto", rotulo: "Commits desde o último conserto" },
  { coluna: "adicionadas_desde_conserto", rotulo: "Linhas novas desde o último conserto" },
];

function formatar(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "n/d";
  return Math.round(valor).toLocaleString("pt-BR");
}

export default function PainelArquivo({ arquivo, resultado, limiar }: Props): JSX.Element {
  if (!arquivo) {
    return (
      <aside className="bloco painel">
        <p className="texto-apoio">Escolha um arquivo na árvore.</p>
      </aside>
    );
  }

  const faixa = nivel(arquivo.probabilidade, limiar);
  const linkGithub = `https://github.com/${resultado.repositorio}/blob/${resultado.commit}/${arquivo.caminho}`;
  const escala = Math.max(resultado.resumo.risco_maximo, limiar, 0.01);

  return (
    <aside className="bloco painel">
      <p className="painel-caminho">{arquivo.caminho}</p>

      <div className="painel-chance">
        <span className={`painel-numero cor-${faixa}`}>{porcento(arquivo.probabilidade)}</span>
        <span className={`selo fundo-${faixa}`}>{ROTULO_NIVEL[faixa]}</span>
      </div>
      <p className="texto-apoio">
        {arquivo.posicao}º entre {resultado.resumo.avaliados} arquivos
      </p>

      <div className="regua" aria-hidden>
        <span
          className={`regua-valor fundo-forte-${faixa}`}
          style={{ width: `${Math.min(100, (100 * arquivo.probabilidade) / escala)}%` }}
        />
        <span className="regua-limiar" style={{ left: `${Math.min(100, (100 * limiar) / escala)}%` }} />
      </div>

      {arquivo.motivos.length > 0 && <p>Se destaca por {arquivo.motivos.join("; ")}.</p>}

      <table className="tabela-medidas">
        <tbody>
          {MEDIDAS.map((m) => (
            <tr key={m.coluna}>
              <th scope="row">{m.rotulo}</th>
              <td>{formatar(arquivo.metricas[m.coluna])}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <a href={linkGithub} target="_blank" rel="noreferrer">
        Abrir no GitHub
      </a>
    </aside>
  );
}
