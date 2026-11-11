/*
 * Detalhe de um commit: nota, chance estimada, o que mais pesou na
 * nota e os arquivos .py de código que ele alterou.
 */

import type { CommitAvaliado, Resultado } from "@/lib/api";
import { CLASSE_DA_FAIXA, decimal, formatarData, inteiro, porcento } from "@/lib/formato";

// =============================================================
// Painel Commit
// -------------------------------------------------------------
// Explica a nota do commit selecionado
// =============================================================
export default function PainelCommit({ commit, resultado }: { commit: CommitAvaliado | null; resultado: Resultado }) {
  if (!commit) {
    return (
      <section className="cartao">
        <p className="vazio">Selecione um commit na lista ou na linha do tempo.</p>
      </section>
    );
  }

  const faixa = resultado.modelo.faixas.find((f) => f.faixa === commit.faixa);
  const maiorEfeito = Math.max(...commit.fatores.map((f) => Math.abs(f.efeito)), 0.01);

  return (
    <section className="cartao painel-commit-v2">
      <p className="painel-caminho">
        <a href={`https://github.com/${resultado.repositorio}/commit/${commit.hash}`} target="_blank" rel="noreferrer">
          <code>{commit.hash.slice(0, 10)}</code> ↗
        </a>
        <span>{formatarData(commit.data)}</span>
        <span>{commit.autor}</span>
      </p>
      <h2 className="painel-assunto">{commit.assunto || "(sem mensagem)"}</h2>

      <div className="painel-numeros">
        <div>
          <strong className={`cor-${CLASSE_DA_FAIXA[commit.faixa]}`}>{decimal(commit.nota, 2)}</strong>
          <span>nota de risco ({commit.faixa})</span>
        </div>
        <div>
          <strong>{porcento(commit.chance, 0)}</strong>
          <span>chance estimada de defeito</span>
        </div>
        <div>
          <strong>{porcento(commit.percentil, 0)}</strong>
          <span>dos commits de referência têm nota menor</span>
        </div>
      </div>

      {faixa && (
        <p className="painel-leitura">
          Em projetos nunca vistos pelo modelo, {porcento(faixa.taxa_de_defeito, 0)} dos commits na faixa{" "}
          <strong>{commit.faixa}</strong> foram marcados como causadores de defeito, contra {porcento(faixa.taxa_geral, 0)}{" "}
          no geral. A nota ordena a revisão; não confirma defeito, nem aponta o arquivo culpado.
        </p>
      )}

      <h3 className="painel-titulo">O que mais pesou na nota</h3>
      {commit.fatores.length === 0 ? (
        <p className="vazio">Nenhuma medida isolada mudou a nota de forma relevante.</p>
      ) : (
        <ul className="fatores">
          {commit.fatores.map((fator) => (
            <li key={fator.feature}>
              <span className="fator-nome">
                {fator.nome}
                <small>
                  vale {fator.valor === null ? "—" : decimal(fator.valor, Number.isInteger(fator.valor) ? 0 : 2)}; mediana do
                  treino {fator.mediana_do_treino === null ? "—" : decimal(fator.mediana_do_treino, Number.isInteger(fator.mediana_do_treino) ? 0 : 2)}
                </small>
              </span>
              <span className="fator-barra" aria-hidden>
                <span
                  className={fator.efeito >= 0 ? "fator-sobe" : "fator-desce"}
                  style={{ width: `${(50 * Math.abs(fator.efeito)) / maiorEfeito}%` }}
                />
              </span>
              <span className="fator-efeito">
                {fator.efeito >= 0 ? "+" : "−"}
                {decimal(Math.abs(fator.efeito), 2)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="nota-rodape">
        Efeito = quanto a nota mudaria se só aquela medida valesse a mediana do treino. Medidas do histórico vêm do
        arquivo <code>{commit.arquivo_decisivo}</code>, o de maior nota no commit.
      </p>

      <h3 className="painel-titulo">
        Arquivos .py de código alterados ({inteiro(commit.arquivos_py)} de {inteiro(commit.arquivos)} arquivos)
      </h3>
      <div className="tabela-rolagem">
        <table className="tabela-arquivos">
          <thead>
            <tr>
              <th>arquivo</th>
              <th>+ / −</th>
              <th>commits</th>
              <th>autores</th>
            </tr>
          </thead>
          <tbody>
            {commit.arquivos_alterados.map((arquivo) => (
              <tr key={arquivo.caminho}>
                <td title={arquivo.caminho}>
                  {arquivo.caminho}
                  {arquivo.novo && <span className="etiqueta-novo">novo</span>}
                </td>
                <td>
                  +{inteiro(arquivo.adicionadas)} −{inteiro(arquivo.removidas)}
                </td>
                <td>{inteiro(arquivo.revisoes)}</td>
                <td>{inteiro(arquivo.autores)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
