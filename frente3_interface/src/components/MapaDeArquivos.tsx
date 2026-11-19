const COLUNAS = 16;
const LINHAS = 9;
const LADO = 22;
const FOLGA = 5;

function sorteio(): number[] {
  let semente = 11;
  const saida: number[] = [];
  for (let i = 0; i < COLUNAS * LINHAS; i++) {
    semente = (semente * 48271) % 2147483647;
    saida.push(Math.pow(semente / 2147483647, 3.2));
  }
  return saida;
}

const VALORES = sorteio();
const LARGURA = COLUNAS * (LADO + FOLGA) - FOLGA;
const ALTURA = LINHAS * (LADO + FOLGA) - FOLGA;

export default function MapaDeArquivos() {
  return (
    <svg className="mapa" viewBox={`0 0 ${LARGURA} ${ALTURA}`} aria-hidden>
      {VALORES.map((v, i) => (
        <rect
          key={i}
          x={(i % COLUNAS) * (LADO + FOLGA)}
          y={Math.floor(i / COLUNAS) * (LADO + FOLGA)}
          width={LADO}
          height={LADO}
          rx={5}
          className={v > 0.78 ? "mapa-alto" : "mapa-comum"}
          opacity={0.1 + 0.9 * Math.min(1, v * 1.15)}
        />
      ))}
    </svg>
  );
}
