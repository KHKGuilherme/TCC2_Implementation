/*
 * Os três gráficos da análise, desenhados em SVG: linha do tempo,
 * curva de esforço e distribuição das notas.
 */

import type { Curva, FaixaDoHistograma, PontoDoTempo, Resultado } from "@/lib/api";
import { CLASSE_DA_FAIXA, decimal, diasEntre, formatarData, inteiro, porcento } from "@/lib/formato";

const LARGURA = 640;
const ALTURA = 260;
const MARGEM = { esquerda: 46, direita: 14, topo: 12, base: 34 };
const AREA_X = LARGURA - MARGEM.esquerda - MARGEM.direita;
const AREA_Y = ALTURA - MARGEM.topo - MARGEM.base;
const MARCAS = [0, 0.25, 0.5, 0.75, 1];

// =============================================================
// Posicao X
// -------------------------------------------------------------
// De uma fração de 0 a 1 para a coordenada horizontal
// =============================================================
function posicaoX(fracao: number): number {
  return MARGEM.esquerda + fracao * AREA_X;
}

// =============================================================
// Posicao Y
// -------------------------------------------------------------
// De uma fração de 0 a 1 para a coordenada vertical
// =============================================================
function posicaoY(fracao: number): number {
  return MARGEM.topo + (1 - fracao) * AREA_Y;
}

// =============================================================
// Grade
// -------------------------------------------------------------
// Linhas horizontais e rótulos do eixo vertical
// =============================================================
function Grade({ rotulo }: { rotulo: (fracao: number) => string }) {
  return (
    <g>
      {MARCAS.map((marca) => (
        <g key={marca}>
          <line className="grafico-grade" x1={MARGEM.esquerda} x2={LARGURA - MARGEM.direita} y1={posicaoY(marca)} y2={posicaoY(marca)} />
          <text className="grafico-rotulo" x={MARGEM.esquerda - 8} y={posicaoY(marca) + 4} textAnchor="end">
            {rotulo(marca)}
          </text>
        </g>
      ))}
    </g>
  );
}

// =============================================================
// Grafico Tempo
// -------------------------------------------------------------
// Cada commit avaliado no tempo: altura = nota, tamanho = linhas
// =============================================================
export function GraficoTempo({
  resultado,
  selecionado,
  selecionar,
}: {
  resultado: Resultado;
  selecionado: string | null;
  selecionar: (hash: string) => void;
}) {
  const pontos = resultado.linha_do_tempo;
  const { inicio, referencia } = resultado.janela;
  const duracao = Math.max(diasEntre(inicio, referencia), 1);
  const cortes = resultado.modelo.faixas.filter((f) => f.faixa !== "baixo");
  const visiveis = new Set(resultado.commits.map((c) => c.hash.slice(0, 10)));

  const raio = (ponto: PontoDoTempo) => 3.5 + 6.5 * Math.sqrt(Math.min(ponto.linhas, 1000) / 1000);

  return (
    <figure className="grafico">
      <figcaption>
        <strong>Linha do tempo</strong>
        <span>Cada círculo é um commit; a altura é a nota de risco e o tamanho, as linhas alteradas.</span>
      </figcaption>
      <svg viewBox={`0 0 ${LARGURA} ${ALTURA}`} role="img" aria-label="Nota de risco de cada commit ao longo do tempo">
        <Grade rotulo={(f) => decimal(f, 2)} />
        {cortes.map((faixa) => (
          <g key={faixa.faixa}>
            <line className={`grafico-corte traco-${CLASSE_DA_FAIXA[faixa.faixa]}`} x1={MARGEM.esquerda} x2={LARGURA - MARGEM.direita} y1={posicaoY(faixa.nota_de)} y2={posicaoY(faixa.nota_de)} />
            <text className="grafico-rotulo" x={LARGURA - MARGEM.direita - 4} y={posicaoY(faixa.nota_de) - 5} textAnchor="end">
              {faixa.faixa}
            </text>
          </g>
        ))}
        {pontos.map((ponto) => {
          const clicavel = visiveis.has(ponto.hash);
          const completo = resultado.commits.find((c) => c.hash.startsWith(ponto.hash))?.hash;
          return (
            <circle
              key={ponto.hash}
              className={`grafico-ponto preenche-${CLASSE_DA_FAIXA[ponto.faixa]} ${completo && completo === selecionado ? "grafico-ponto-ativo" : ""}`}
              cx={posicaoX(Math.min(Math.max(diasEntre(inicio, ponto.data) / duracao, 0), 1))}
              cy={posicaoY(ponto.nota)}
              r={raio(ponto)}
              onClick={() => clicavel && completo && selecionar(completo)}
              style={{ cursor: clicavel ? "pointer" : "default" }}
            >
              <title>
                {`${ponto.hash} · ${formatarData(ponto.data)} · nota ${decimal(ponto.nota, 2)} · ${inteiro(ponto.linhas)} linhas · risco ${ponto.faixa}`}
              </title>
            </circle>
          );
        })}
        <text className="grafico-rotulo" x={MARGEM.esquerda} y={ALTURA - 10}>
          {formatarData(inicio)}
        </text>
        <text className="grafico-rotulo" x={LARGURA - MARGEM.direita} y={ALTURA - 10} textAnchor="end">
          {formatarData(referencia)}
        </text>
      </svg>
      <p className="grafico-legenda">
        <span><i className="fundo-alto" /> alto</span>
        <span><i className="fundo-medio" /> médio</span>
        <span><i className="fundo-baixo" /> baixo</span>
      </p>
    </figure>
  );
}

// =============================================================
// Caminho
// -------------------------------------------------------------
// Os pontos de uma curva como atributo de um path
// =============================================================
function caminho(curva: Curva): string {
  return curva.map(([x, y], i) => `${i === 0 ? "M" : "L"}${posicaoX(x).toFixed(1)},${posicaoY(y).toFixed(1)}`).join(" ");
}

// =============================================================
// Valor Em
// -------------------------------------------------------------
// O valor de uma curva numa fração do esforço
// =============================================================
function valorEm(curva: Curva, fracao: number): number {
  const ponto = curva.reduce((perto, atual) => (Math.abs(atual[0] - fracao) < Math.abs(perto[0] - fracao) ? atual : perto));
  return ponto[1];
}

// =============================================================
// Grafico Esforco
// -------------------------------------------------------------
// Risco estimado coberto conforme as linhas revisadas, por ordem
// =============================================================
export function GraficoEsforco({ resultado }: { resultado: Resultado }) {
  const { curvas } = resultado;
  const series = [
    { chave: "custo", rotulo: "melhor custo-benefício", curva: curvas.custo },
    { chave: "risco", rotulo: "maior risco primeiro", curva: curvas.risco },
    { chave: "cronologica", rotulo: "do mais novo ao mais antigo", curva: curvas.cronologica },
  ];

  return (
    <figure className="grafico">
      <figcaption>
        <strong>Quanto revisar</strong>
        <span>
          Parcela do risco estimado já coberta conforme as linhas revisadas, em cada ordem de leitura. É uma estimativa
          do modelo, e não defeitos confirmados.
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${LARGURA} ${ALTURA}`} role="img" aria-label="Risco coberto por linhas revisadas">
        <Grade rotulo={(f) => porcento(f, 0)} />
        <line className="grafico-corte" x1={posicaoX(0.2)} x2={posicaoX(0.2)} y1={MARGEM.topo} y2={posicaoY(0)} />
        {series.map((serie) => (
          <path key={serie.chave} className={`grafico-linha linha-${serie.chave}`} d={caminho(serie.curva)}>
            <title>{serie.rotulo}</title>
          </path>
        ))}
        {MARCAS.map((marca) => (
          <text key={marca} className="grafico-rotulo" x={posicaoX(marca)} y={ALTURA - 10} textAnchor={marca === 0 ? "start" : marca === 1 ? "end" : "middle"}>
            {porcento(marca, 0)}
          </text>
        ))}
      </svg>
      <p className="grafico-legenda">
        {series.map((serie) => (
          <span key={serie.chave}>
            <i className={`fundo-${serie.chave}`} /> {serie.rotulo}: {porcento(valorEm(serie.curva, 0.2), 0)} do risco com 20% das
            linhas
          </span>
        ))}
      </p>
    </figure>
  );
}

// =============================================================
// Grafico Distribuicao
// -------------------------------------------------------------
// As notas deste repositório ao lado das de projetos de referência
// =============================================================
export function GraficoDistribuicao({ faixas, commits }: { faixas: FaixaDoHistograma[]; commits: number }) {
  const maior = Math.max(...faixas.flatMap((f) => [f.repositorio, f.referencia]), 0.01);
  const passo = AREA_X / faixas.length;
  const largura = passo * 0.36;

  return (
    <figure className="grafico">
      <figcaption>
        <strong>Distribuição das notas</strong>
        <span>
          Os {inteiro(commits)} commits avaliados deste repositório, comparados aos commits de projetos nunca vistos
          usados como referência.
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${LARGURA} ${ALTURA}`} role="img" aria-label="Distribuição das notas de risco">
        <Grade rotulo={(f) => porcento(f * maior, 0)} />
        {faixas.map((faixa, i) => {
          const x = MARGEM.esquerda + i * passo + passo / 2;
          return (
            <g key={faixa.de}>
              <rect className="barra-referencia" x={x - largura - 1} width={largura} y={posicaoY(faixa.referencia / maior)} height={AREA_Y * (faixa.referencia / maior)} rx={2}>
                <title>{`referência, nota ${decimal(faixa.de, 1)} a ${decimal(faixa.ate, 1)}: ${porcento(faixa.referencia)}`}</title>
              </rect>
              <rect className="barra-repositorio" x={x + 1} width={largura} y={posicaoY(faixa.repositorio / maior)} height={AREA_Y * (faixa.repositorio / maior)} rx={2}>
                <title>{`este repositório, nota ${decimal(faixa.de, 1)} a ${decimal(faixa.ate, 1)}: ${porcento(faixa.repositorio)}`}</title>
              </rect>
              <text className="grafico-rotulo" x={x} y={ALTURA - 10} textAnchor="middle">
                {decimal(faixa.de, 1)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="grafico-legenda">
        <span><i className="fundo-repositorio" /> este repositório</span>
        <span><i className="fundo-referencia" /> referência</span>
      </p>
    </figure>
  );
}
