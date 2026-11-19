"use client";

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

export default function Arvore(props: Props) {
  return (
    <ul className="arvore" role="tree">
      {ordenar(props.raiz.filhos, props.ordem).map((filho) => (
        <Linha key={filho.caminho} no={filho} profundidade={0} {...props} />
      ))}
    </ul>
  );
}

function Linha({ no, profundidade, ...props }: Props & { no: No; profundidade: number }) {
  const ePasta = no.tipo === "pasta";
  const aberta = ePasta && props.abertas.has(no.caminho);
  const faixa = nivel(no.risco, props.limiar);
  const escolhida = props.selecionado === no.caminho;

  function clicar() {
    if (ePasta) props.alternar(no.caminho);
    else props.selecionar(no.caminho);
  }

  return (
    <li role="treeitem" aria-expanded={ePasta ? aberta : undefined} aria-selected={escolhida}>
      <button
        type="button"
        className={`linha-arvore${escolhida ? " escolhida" : ""}`}
        style={{ paddingLeft: `${8 + profundidade * 16}px` }}
        onClick={clicar}
      >
        <span className="linha-icone" aria-hidden>
          {ePasta ? (aberta ? "▾" : "▸") : ""}
        </span>
        <span className={ePasta ? "linha-pasta" : "linha-nome"}>{no.nome}</span>

        {ePasta && no.alto > 0 && (
          <span className="linha-contagem" title={`${no.alto} arquivo(s) acima do limiar`}>
            {no.alto}
          </span>
        )}

        {no.risco !== null && (
          <>
            <span className="linha-barra" aria-hidden>
              <span className={`fundo-forte-${faixa}`} style={{ width: `${100 * no.risco}%` }} />
            </span>
            <span className={`linha-valor cor-${faixa}`}>{porcento(no.risco, 0)}</span>
          </>
        )}
      </button>

      {aberta && (
        <ul role="group">
          {ordenar(no.filhos, props.ordem).map((filho) => (
            <Linha key={filho.caminho} no={filho} profundidade={profundidade + 1} {...props} />
          ))}
        </ul>
      )}
    </li>
  );
}
