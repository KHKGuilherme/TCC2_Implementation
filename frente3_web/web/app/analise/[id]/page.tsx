"use client";

/*
 * Página de uma análise.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import Arvore from "@/components/Arvore";
import CommitsRevisar from "@/components/CommitsRevisar";
import FormularioAnalise from "@/components/FormularioAnalise";
import PainelArquivo from "@/components/PainelArquivo";
import Progresso from "@/components/Progresso";
import { buscarAnalise, type Analise, type Resultado } from "@/lib/api";
import { filtrar, montarArvore, nivel, pastasAte, porcento, type Ordem } from "@/lib/arvore";

const INTERVALO_DE_CONSULTA = 1000;

// =============================================================
// Pagina Analise
// -------------------------------------------------------------
// Consulta a análise até ela terminar
// =============================================================
export default function PaginaAnalise() {
  const { id } = useParams<{ id: string }>();
  const [analise, setAnalise] = useState<Analise | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    let espera: ReturnType<typeof setTimeout>;

    async function consultar() {
      try {
        const atual = await buscarAnalise(id);
        if (!ativo) return;
        setAnalise(atual);
        setErro("");
        if (atual.status === "na_fila" || atual.status === "rodando") {
          espera = setTimeout(consultar, INTERVALO_DE_CONSULTA);
        }
      } catch (e) {
        if (!ativo) return;
        setErro((e as Error).message);
        espera = setTimeout(consultar, 3 * INTERVALO_DE_CONSULTA);
      }
    }

    consultar();
    return () => {
      ativo = false;
      clearTimeout(espera);
    };
  }, [id]);

  if (!analise) {
    return <div className="pagina-analise">{erro ? <p className="mensagem-erro">{erro}</p> : <p>Carregando…</p>}</div>;
  }

  if (analise.status === "erro") {
    return (
      <div className="pagina-analise estreita">
        <div className="cartao">
          <p className="progresso-repo">{analise.repositorio}</p>
          <p className="mensagem-erro">{analise.erro}</p>
        </div>
        <h2 className="titulo-secao">Tentar outra vez</h2>
        <FormularioAnalise inicial={analise.repositorio} />
      </div>
    );
  }

  if (analise.status !== "concluida" || !analise.resultado) {
    return (
      <div className="pagina-analise estreita">
        <Progresso analise={analise} />
        {erro && <p className="mensagem-erro">{erro}</p>}
      </div>
    );
  }

  return <Resultados resultado={analise.resultado} />;
}

// =============================================================
// Resultados
// -------------------------------------------------------------
// Árvore, ranking e detalhe de uma análise pronta
// =============================================================
function Resultados({ resultado }: { resultado: Resultado }) {
  const limiar = resultado.modelo.limiar;
  const { resumo } = resultado;

  const arvoreCompleta = useMemo(() => montarArvore(resultado.arquivos, limiar), [resultado, limiar]);

  const ranking = useMemo(
    () =>
      resultado.arquivos
        .filter((a) => a.situacao === "avaliado")
        .sort((a, b) => (a.posicao ?? 0) - (b.posicao ?? 0)),
    [resultado],
  );

  const [selecionado, setSelecionado] = useState<string | null>(ranking[0]?.caminho ?? null);
  const [ordem, setOrdem] = useState<Ordem>("risco");
  const [busca, setBusca] = useState("");
  const [soAvaliados, setSoAvaliados] = useState(true);

  const [abertas, setAbertas] = useState<Set<string>>(
    () => new Set(ranking[0] ? pastasAte(arvoreCompleta, ranking[0].caminho) : []),
  );

  const arvore = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    if (!termo && !soAvaliados) return arvoreCompleta;
    return (
      filtrar(
        arvoreCompleta,
        (a) => (!soAvaliados || a.situacao === "avaliado") && (!termo || a.caminho.toLowerCase().includes(termo)),
      ) ?? { ...arvoreCompleta, filhos: [] }
    );
  }, [arvoreCompleta, busca, soAvaliados]);

  const abertasEfetivas = useMemo(() => {
    if (!busca.trim()) return abertas;
    const todas = new Set<string>();
    const juntar = (no: typeof arvore) => {
      if (no.tipo === "pasta") {
        if (no.caminho) todas.add(no.caminho);
        no.filhos.forEach(juntar);
      }
    };
    juntar(arvore);
    return todas;
  }, [abertas, arvore, busca]);

  function alternar(caminho: string) {
    setAbertas((atual) => {
      const nova = new Set(atual);
      if (nova.has(caminho)) nova.delete(caminho);
      else nova.add(caminho);
      return nova;
    });
  }

  function irPara(caminho: string) {
    setSelecionado(caminho);
    setAbertas((atual) => new Set([...atual, ...pastasAte(arvoreCompleta, caminho)]));
  }

  const arquivoSelecionado = resultado.arquivos.find((a) => a.caminho === selecionado) ?? null;
  const naoAvaliados = resumo.arquivos_py - resumo.avaliados;

  return (
    <div className="pagina-analise">
      <header className="cabecalho-analise">
        <div>
          <h1 className="titulo-analise">{resultado.repositorio}</h1>
          <p className="meta-analise">
            <span className="etiqueta-ramo">{resultado.ramo}</span>
            <code>{resultado.commit.slice(0, 10)}</code>
            <span>{resultado.commits.toLocaleString("pt-BR")} commits</span>
            <span>analisado em {resultado.duracao_s.toLocaleString("pt-BR")} s</span>
            <span>modelo: {resultado.modelo.nome}</span>
          </p>
        </div>
        <Link href="/" className="botao-secundario">
          Nova análise
        </Link>
      </header>

      {resultado.aviso && <p className="aviso">{resultado.aviso}</p>}

      <section className="cartoes cartoes-analise">
        <div className="cartao-numero">
          <strong>{resumo.avaliados}</strong>
          <span>
            arquivos avaliados de {resumo.arquivos_py}
            {naoAvaliados > 0 && ` (${naoAvaliados} sem nota)`}
          </span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-alto">{resumo.risco_alto}</strong>
          <span>acima do limiar de {porcento(limiar, 0)}</span>
        </div>
        <div className="cartao-numero">
          <strong className={`cor-${nivel(resumo.risco_maximo, limiar)}`}>{porcento(resumo.risco_maximo)}</strong>
          <span>maior nota de risco</span>
        </div>
        <div className="cartao-numero">
          <strong className={`cor-${nivel(resumo.risco_medio, limiar)}`}>{porcento(resumo.risco_medio)}</strong>
          <span>média dos avaliados</span>
        </div>
      </section>

      <CommitsRevisar resultado={resultado} selecionado={selecionado} selecionar={irPara} />

      <div className="grade-analise">
        <section className="cartao coluna-arvore">
          <div className="barra-ferramentas">
            <input
              className="campo-busca"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Filtrar por caminho…"
              aria-label="Filtrar arquivos por caminho"
            />
            <div className="alternador" role="group" aria-label="Ordenar">
              <button type="button" className={ordem === "risco" ? "ativo" : ""} onClick={() => setOrdem("risco")}>
                risco
              </button>
              <button type="button" className={ordem === "nome" ? "ativo" : ""} onClick={() => setOrdem("nome")}>
                nome
              </button>
            </div>
            <label className="caixa">
              <input type="checkbox" checked={soAvaliados} onChange={(e) => setSoAvaliados(e.target.checked)} />
              só avaliados
            </label>
          </div>

          <p className="legenda">
            <span className="legenda-item"><i className="fundo-alto" /> alto (≥ {porcento(limiar, 0)})</span>
            <span className="legenda-item"><i className="fundo-medio" /> médio</span>
            <span className="legenda-item"><i className="fundo-baixo" /> baixo</span>
            <span className="legenda-nota">
              O risco de um arquivo é o do último commit que o alterou. Pastas mostram o maior risco entre os arquivos
              dentro delas.
            </span>
          </p>

          {arvore.filhos.length === 0 ? (
            <p className="vazio">Nenhum arquivo corresponde ao filtro.</p>
          ) : (
            <Arvore
              raiz={arvore}
              limiar={limiar}
              ordem={ordem}
              abertas={abertasEfetivas}
              alternar={alternar}
              selecionado={selecionado}
              selecionar={setSelecionado}
            />
          )}
        </section>

        <div className="coluna-lateral">
          <PainelArquivo arquivo={arquivoSelecionado} resultado={resultado} />

          <section className="cartao">
            <h2 className="titulo-cartao">Arquivos com a última mudança mais arriscada</h2>
            <ol className="ranking">
              {ranking.slice(0, 10).map((a) => (
                <li key={a.caminho}>
                  <button
                    type="button"
                    className={a.caminho === selecionado ? "ranking-ativo" : ""}
                    onClick={() => irPara(a.caminho)}
                  >
                    <span className="ranking-posicao">{a.posicao}</span>
                    <span className="ranking-caminho" title={a.caminho}>
                      {a.caminho}
                    </span>
                    <span className={`cor-${nivel(a.probabilidade, limiar)}`}>{porcento(a.probabilidade, 0)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}