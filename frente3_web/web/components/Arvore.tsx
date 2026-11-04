// frente3_web\web\components\Arvore.tsx

"use client";

/*
 * A árvore de pastas e arquivos, com o risco em cada linha.
 *
 * Arquivo mostra a própria probabilidade. Pasta mostra a MAIOR
 * probabilidade dentro dela, e quantos arquivos dela passam do
 * limiar.
 */

import { nivel, ordenar, porcento, type No, type Ordem } from "@/lib/arvore";

interface Props {
  raiz: No;
  limiar: number;
  ordem: Ordem;
  abertas: Set<string>;
  alternar: (caminho: string) => void;
  selecionado: string | null;
  selecionar: (caminho: string) => void;
}

// Rótulo curto de quem ficou sem nota, ao lado do nome
const MOTIVO_CURTO: Record<string, string> = {
  teste: "teste",
  ignorado: "fora do escopo",
  vazio: "vazio",
  grande: "grande demais",
  sem_parse: "não lido",
  sem_funcoes: "sem funções",
};

export default function Arvore(props: Props) {
  return (
    <ul className="arvore" role="tree">
      {ordenar(props.raiz.filhos, props.ordem).map((filho) => (
        <Linha key={filho.caminho} no={filho} nivelArvore={0} {...props} />
      ))}
    </ul>
  );
}

// =============================================================
// Linha
// -------------------------------------------------------------
// Uma pasta ou um arquivo, e os filhos se estiver aberta
// =============================================================
function Linha({ no, nivelArvore, ...props }: Props & { no: No; nivelArvore: number }) {
  const ePasta = no.tipo === "pasta";
  const aberta = ePasta && props.abertas.has(no.caminho);
  const faixa = nivel(no.risco, props.limiar);
  const situacao = no.arquivo?.situacao;

  function clicar() {
    if (ePasta) props.alternar(no.caminho);
    else props.selecionar(no.caminho);
  }

  return (
    <li role="treeitem" aria-expanded={ePasta ? aberta : undefined} aria-selected={props.selecionado === no.caminho}>
      <button
        type="button"
        className={`linha-arvore ${props.selecionado === no.caminho ? "linha-selecionada" : ""} ${
          faixa === "nenhum" ? "linha-apagada" : ""
        }`}
        style={{ paddingLeft: `${10 + nivelArvore * 16}px` }}
        onClick={clicar}
      >
        <span className="linha-icone" aria-hidden>
          {ePasta ? (aberta ? "▾" : "▸") : "·"}
        </span>
        <span className={`linha-nome ${ePasta ? "linha-pasta" : ""}`}>{no.nome}</span>

        {ePasta && no.alto > 0 && (
          <span className="linha-contagem" title={`${no.alto} arquivo(s) acima do limiar`}>
            {no.alto} alto
          </span>
        )}

        {!ePasta && situacao && situacao !== "avaliado" && (
          <span className="linha-motivo">{MOTIVO_CURTO[situacao]}</span>
        )}

        {no.risco !== null && (
          <>
            <span className="linha-barra" aria-hidden>
              <span className={`fundo-${faixa}`} style={{ width: `${100 * no.risco}%` }} />
            </span>
            <span className={`linha-valor cor-${faixa}`}>
              {ePasta && <span className="linha-max">máx </span>}
              {porcento(no.risco, 0)}
            </span>
          </>
        )}
      </button>

      {aberta && (
        <ul role="group">
          {ordenar(no.filhos, props.ordem).map((filho) => (
            <Linha key={filho.caminho} no={filho} nivelArvore={nivelArvore + 1} {...props} />
          ))}
        </ul>
      )}
    </li>
  );
}