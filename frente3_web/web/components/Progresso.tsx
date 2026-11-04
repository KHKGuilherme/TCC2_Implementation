// frente3_web\web\components\Progresso.tsx

/*
 * Tela de espera enquanto a análise roda: as quatro etapas, a
 * barra e a mensagem que a Frente 2 vai escrevendo.
 */

import type { Analise } from "@/lib/api";

const ETAPAS = [
  { chave: "clonando", rotulo: "Clonando o repositório" },
  { chave: "medindo", rotulo: "Medindo o código de cada arquivo" },
  { chave: "historico", rotulo: "Lendo o histórico de commits" },
  { chave: "prevendo", rotulo: "Aplicando o modelo" },
];

export default function Progresso({ analise }: { analise: Analise }) {
  const atual = ETAPAS.findIndex((e) => e.chave === analise.etapa);
  const naFila = analise.status === "na_fila";

  return (
    <div className="cartao progresso">
      <p className="progresso-repo">{analise.repositorio}</p>

      <div className="barra-progresso" role="progressbar" aria-valuenow={Math.round(100 * analise.progresso)}>
        <span style={{ width: `${Math.max(2, 100 * analise.progresso)}%` }} />
      </div>

      <p className="progresso-mensagem">
        {naFila
          ? analise.posicao_na_fila
            ? `Na fila: ${analise.posicao_na_fila} análise(s) antes desta`
            : "Na fila, começando…"
          : `${Math.round(100 * analise.progresso)}% · ${analise.mensagem || "trabalhando"}`}
      </p>

      <ol className="etapas">
        {ETAPAS.map((etapa, i) => {
          const estado = naFila || i > atual ? "futura" : i < atual ? "feita" : "atual";
          return (
            <li key={etapa.chave} className={`etapa etapa-${estado}`}>
              <span className="etapa-marca" aria-hidden>
                {estado === "feita" ? "✓" : i + 1}
              </span>
              {etapa.rotulo}
            </li>
          );
        })}
      </ol>
    </div>
  );
}