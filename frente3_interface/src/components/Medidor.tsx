interface Props {
  valor: number;
  minimo?: number;
  maximo?: number;
  tamanho?: number;
  rotulo: string;
  texto?: string;
}

const RAIO = 52;
const LARGURA = 12;
const CIRCUNFERENCIA = 2 * Math.PI * RAIO;

const limitar = (v: number) => Math.min(100, Math.max(0, v));

export default function Medidor({ valor, minimo, maximo, tamanho = 176, rotulo, texto }: Props) {
  const v = limitar(valor);
  const faixa = minimo !== undefined && maximo !== undefined ? [limitar(minimo), limitar(maximo)] : null;

  return (
    <svg className="medidor" viewBox="0 0 140 140" width={tamanho} height={tamanho} role="img" aria-label={rotulo}>
      <circle className="medidor-trilho" cx="70" cy="70" r={RAIO} strokeWidth={LARGURA} fill="none" />
      {faixa && (
        <circle
          className="medidor-faixa"
          cx="70"
          cy="70"
          r={RAIO}
          strokeWidth={LARGURA}
          fill="none"
          strokeDasharray={`${((faixa[1] - faixa[0]) / 100) * CIRCUNFERENCIA} ${CIRCUNFERENCIA}`}
          strokeDashoffset={-(faixa[0] / 100) * CIRCUNFERENCIA}
          transform="rotate(-90 70 70)"
        />
      )}
      <circle
        className="medidor-valor"
        cx="70"
        cy="70"
        r={RAIO}
        strokeWidth={LARGURA}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={`${(v / 100) * CIRCUNFERENCIA} ${CIRCUNFERENCIA}`}
        transform="rotate(-90 70 70)"
      />
      {texto && (
        <text className="medidor-numero" x="70" y="78" textAnchor="middle">
          {texto}
        </text>
      )}
    </svg>
  );
}
