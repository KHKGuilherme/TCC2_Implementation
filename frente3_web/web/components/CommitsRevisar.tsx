// frente3_web\web\components\CommitsRevisar.tsx

/*
 * Commits recentes para revisar, do mais para o menos arriscado.
 *
 * É a resposta principal da análise. O rótulo do treino é do commit,
 * então a ordem que o modelo sustenta é entre commits. Os arquivos de
 * um commit aparecem juntos, e não como notas soltas quase iguais.
 */

import type { Resultado } from "@/lib/api";
import { nivel, porcento } from "@/lib/arvore";

// Commit grande listaria dezenas de arquivos
const ARQUIVOS_VISIVEIS = 4;

interface Props {
  resultado: Resultado;
  selecionado: string | null;
  selecionar: (caminho: string) => void;
}

// =============================================================
// Formatar Data
// -------------------------------------------------------------
// De 2026-03-12 para 12/03/2026, sem passar por fuso horário
// =============================================================
export function formatarData(iso: string): string {
  return iso.split("-").reverse().join("/");
}

export default function CommitsRevisar({ resultado, selecionado, selecionar }: Props) {
  const { revisao, modelo, repositorio } = resultado;

  // Análise gravada antes da revisão por commit
  if (!revisao) return null;

  return (
    <section className="cartao revisao">
      <h2 className="titulo-cartao">Commits para revisar</h2>
      <p className="revisao-explicacao">
        Commits dos {revisao.janela_dias} dias até {formatarData(revisao.referencia)}, último commit do repositório,
        ordenados pelo risco de terem introduzido um defeito. A nota é uma ordem de prioridade, e não uma chance real.
        Cada commit lista os arquivos em que ele é a última alteração.
      </p>

      {revisao.commits.length === 0 ? (
        <p className="vazio">Nenhum arquivo avaliado foi alterado nesse período.</p>
      ) : (
        <ol className="revisao-lista">
          {revisao.commits.map((commit) => {
            const extras = commit.avaliados.length - ARQUIVOS_VISIVEIS;
            return (
              <li key={commit.hash} className="revisao-commit">
                <span className={`revisao-risco cor-${nivel(commit.risco, modelo.limiar)}`}>
                  {porcento(commit.risco, 0)}
                </span>
                <div className="revisao-corpo">
                  <p className="revisao-meta">
                    <a
                      href={`https://github.com/${repositorio}/commit/${commit.hash}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <code>{commit.hash.slice(0, 10)}</code> ↗
                    </a>
                    <span>{formatarData(commit.data)}</span>
                    <span>
                      {commit.arquivos.toLocaleString("pt-BR")} {commit.arquivos === 1 ? "arquivo" : "arquivos"}
                    </span>
                    <span>
                      +{commit.adicionadas.toLocaleString("pt-BR")} −{commit.removidas.toLocaleString("pt-BR")}
                    </span>
                  </p>
                  <div className="revisao-arquivos">
                    {commit.avaliados.slice(0, ARQUIVOS_VISIVEIS).map((caminho) => (
                      <button
                        key={caminho}
                        type="button"
                        className={caminho === selecionado ? "revisao-ativo" : ""}
                        title={caminho}
                        onClick={() => selecionar(caminho)}
                      >
                        {caminho}
                      </button>
                    ))}
                    {extras > 0 && <span className="revisao-extras">e mais {extras}</span>}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {(revisao.fora_da_janela > 0 || revisao.recentes > revisao.commits.length) && (
        <p className="nota-rodape">
          {revisao.recentes > revisao.commits.length &&
            `Mostrando ${revisao.commits.length} de ${revisao.recentes} commits recentes. `}
          {revisao.fora_da_janela > 0 &&
            `${revisao.fora_da_janela.toLocaleString("pt-BR")} commits mais antigos ficaram de fora: o defeito que trouxeram pode já ter sido corrigido.`}
        </p>
      )}
    </section>
  );
}
