/*
 * Arquivos que concentram o risco do período e commits que o modelo
 * não pode avaliar.
 */

import type { Resultado } from "@/lib/api";
import { decimal, formatarData, inteiro, porcento } from "@/lib/formato";

// =============================================================
// Arquivos Destaque
// -------------------------------------------------------------
// Onde os commits arriscados do período se concentram
// =============================================================
export function ArquivosDestaque({ resultado }: { resultado: Resultado }) {
  const maior = Math.max(...resultado.arquivos.map((a) => a.risco_somado), 0.01);

  return (
    <section className="cartao">
      <h2 className="titulo-cartao">Arquivos que concentram o risco do período</h2>
      <p className="revisao-explicacao">
        Soma da chance estimada dos commits que alteraram cada arquivo. Mostra onde a atenção se acumula; não diz que o
        arquivo tem defeito, porque o rótulo do treino é do commit, e não do arquivo.
      </p>
      <ol className="destaques">
        {resultado.arquivos.slice(0, 12).map((arquivo) => (
          <li key={arquivo.caminho}>
            <span className="destaque-caminho" title={arquivo.caminho}>
              {arquivo.caminho}
            </span>
            <span className="destaque-barra" aria-hidden>
              <span style={{ width: `${(100 * arquivo.risco_somado) / maior}%` }} />
            </span>
            <span className="destaque-numero">
              {decimal(arquivo.risco_somado, 2)}
              <small>
                {inteiro(arquivo.commits)} {arquivo.commits === 1 ? "commit" : "commits"}, máx. {porcento(arquivo.maior_chance, 0)}
              </small>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// =============================================================
// Fora do Dominio
// -------------------------------------------------------------
// Os commits do período que o modelo não avalia, e o motivo
// =============================================================
export function ForaDoDominio({ resultado }: { resultado: Resultado }) {
  const { fora_do_dominio: fora, janela, modelo, repositorio } = resultado;

  if (fora.length === 0 && janela.sem_py === 0) return null;

  return (
    <section className="cartao">
      <h2 className="titulo-cartao">Sem nota</h2>
      <p className="revisao-explicacao">
        {janela.sem_py > 0 &&
          `${inteiro(janela.sem_py)} commits do período não alteraram arquivos .py de código (só testes, documentação ou outros tipos), como no treino. `}
        {fora.length > 0 &&
          `${inteiro(janela.fora_do_dominio)} estão fora do domínio do modelo: o Defectors nunca marca como causador um commit com mais de ${inteiro(modelo.dominio.maximo_linhas)} linhas alteradas ou ${inteiro(modelo.dominio.maximo_arquivos)} arquivos, nem um sem linhas adicionadas. Dar nota a eles seria extrapolar; os grandes merecem revisão por conta própria.`}
      </p>
      {fora.length > 0 && (
        <ul className="fora-lista">
          {fora.slice(0, 10).map((commit) => (
            <li key={commit.hash}>
              <a href={`https://github.com/${repositorio}/commit/${commit.hash}`} target="_blank" rel="noreferrer">
                <code>{commit.hash.slice(0, 10)}</code> ↗
              </a>
              <span>{formatarData(commit.data)}</span>
              <span>
                {inteiro(commit.arquivos)} arq., +{inteiro(commit.adicionadas)} −{inteiro(commit.removidas)}
              </span>
              <span className="fora-assunto" title={commit.motivo ?? ""}>
                {commit.assunto}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
