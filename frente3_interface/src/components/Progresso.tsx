import type { Analise } from "@/lib/api";

const ETAPAS = [
  { chave: "conferindo", rotulo: "Conferindo o tamanho do repositório" },
  { chave: "clonando", rotulo: "Baixando o histórico" },
  { chave: "historico", rotulo: "Lendo o histórico de cada arquivo" },
  { chave: "avaliando", rotulo: "Aplicando o modelo" },
];

export default function Progresso({ analise }: { analise: Analise }) {
  const atual = ETAPAS.findIndex((e) => e.chave === analise.etapa);
  const naFila = analise.status === "na_fila";
  const percentual = Math.round(100 * analise.progresso);

  return (
    <section className="progresso">
      <h1 className="titulo-repo">{analise.repositorio}</h1>

      <div
        className="barra"
        role="progressbar"
        aria-valuenow={percentual}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${Math.max(2, percentual)}%` }} />
      </div>

      <p className="texto-apoio">
        {naFila
          ? analise.posicao_na_fila
            ? `Na fila, com ${analise.posicao_na_fila} análise(s) antes desta.`
            : "Na fila."
          : `${percentual}%`}
      </p>

      <ol className="etapas">
        {ETAPAS.map((etapa, i) => {
          const estado = naFila || i > atual ? "futura" : i < atual ? "feita" : "atual";
          return (
            <li key={etapa.chave} className={`etapa ${estado}`}>
              {etapa.rotulo}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
