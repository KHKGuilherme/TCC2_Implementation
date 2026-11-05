// frente3_web\web\components\PainelArquivo.tsx

/*
 * Detalhe do arquivo selecionado na árvore.
 *
 * Mostra a nota da última alteração do arquivo, a posição no ranking
 * e as medidas mais legíveis, cada uma com o percentil dentro do próprio
 * repositório: "mais complexo que 92% dos arquivos daqui" diz mais
 * do que "complexidade 34".
 */

import type { ArquivoAnalisado, Resultado } from "@/lib/api";
import { nivel, porcento, ROTULO_NIVEL } from "@/lib/arvore";

import { formatarData } from "./CommitsRevisar";

interface Props {
  arquivo: ArquivoAnalisado | null;
  resultado: Resultado;
}

// =============================================================
// Formatar
// -------------------------------------------------------------
// Número legível, sem casas decimais à toa
// =============================================================
function formatar(valor: number | null): string {
  if (valor === null) return "—";
  if (Number.isInteger(valor)) return valor.toLocaleString("pt-BR");
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

export default function PainelArquivo({ arquivo, resultado }: Props) {
  if (!arquivo) {
    return (
      <aside className="cartao painel painel-vazio">
        <p>Escolha um arquivo na árvore para ver os detalhes.</p>
      </aside>
    );
  }

  const limiar = resultado.modelo.limiar;
  const avaliado = arquivo.situacao === "avaliado";
  const faixa = nivel(arquivo.probabilidade, limiar);
  const linkGithub = `https://github.com/${resultado.repositorio}/blob/${resultado.commit}/${arquivo.caminho}`;
  const ultimo = arquivo.ultimo_commit;

  return (
    <aside className="cartao painel">
      <p className="painel-caminho">{arquivo.caminho}</p>

      {!avaliado ? (
        <div className="painel-nao-avaliado">
          <strong>Sem nota</strong>
          <p>{resultado.situacoes[arquivo.situacao]}.</p>
        </div>
      ) : (
        <>
          <div className="painel-nota">
            <span className={`painel-numero cor-${faixa}`}>{porcento(arquivo.probabilidade)}</span>
            <div>
              <span className={`selo-nivel fundo-${faixa}`}>{ROTULO_NIVEL[faixa]}</span>
              <p className="painel-posicao">
                {arquivo.posicao}º de {resultado.resumo.avaliados} arquivos avaliados
              </p>
            </div>
          </div>

          {/* A régua mostra onde fica o limiar de decisão do modelo */}
          <div className="regua" aria-hidden>
            <span className={`regua-valor fundo-${faixa}`} style={{ width: `${100 * (arquivo.probabilidade ?? 0)}%` }} />
            <span className="regua-limiar" style={{ left: `${100 * limiar}%` }} />
          </div>
          <p className="regua-legenda">limiar do modelo: {porcento(limiar, 0)}</p>

          {ultimo && (
            <p className="painel-commit">
              Risco da última alteração:{" "}
              <a
                href={`https://github.com/${resultado.repositorio}/commit/${ultimo.hash}`}
                target="_blank"
                rel="noreferrer"
              >
                <code>{ultimo.hash.slice(0, 10)}</code> ↗
              </a>
              , {formatarData(ultimo.data)}, {ultimo.arquivos.toLocaleString("pt-BR")}{" "}
              {ultimo.arquivos === 1 ? "arquivo" : "arquivos"}, +{ultimo.adicionadas.toLocaleString("pt-BR")} −
              {ultimo.removidas.toLocaleString("pt-BR")}. Não indica que o arquivo tem defeito hoje.
            </p>
          )}

          <table className="tabela-metricas">
            <thead>
              <tr>
                <th>Medida</th>
                <th>Valor</th>
                <th>No repositório</th>
              </tr>
            </thead>
            <tbody>
              {resultado.metricas_exibidas.map((m) => {
                const [valor, percentil] = arquivo.metricas?.[m.coluna] ?? [null, null];
                // Pinta só os extremos do lado ruim
                const ruim =
                  percentil !== null && (m.melhor === "menor" ? percentil >= 0.85 : percentil <= 0.15);
                return (
                  <tr key={m.coluna} className={ruim ? "metrica-ruim" : ""}>
                    <td>{m.rotulo}</td>
                    <td className="numero">{formatar(valor)}</td>
                    <td>
                      {percentil !== null && (
                        <span className="percentil" title={`maior que ${porcento(percentil, 0)} dos arquivos`}>
                          <span className="percentil-barra">
                            <span style={{ width: `${100 * percentil}%` }} />
                          </span>
                          {porcento(percentil, 0)}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="nota-rodape">
            Percentil: a posição do arquivo entre os avaliados deste repositório. Em destaque, os extremos do lado
            desfavorável.
          </p>
        </>
      )}

      <a className="link-github" href={linkGithub} target="_blank" rel="noreferrer">
        Abrir no GitHub ↗
      </a>
    </aside>
  );
}