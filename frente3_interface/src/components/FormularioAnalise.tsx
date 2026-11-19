"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { pedirAnalise } from "@/lib/api";

export default function FormularioAnalise({ inicial = "" }: { inicial?: string }) {
  const router = useRouter();
  const [endereco, setEndereco] = useState(inicial);
  const [ramo, setRamo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!endereco.trim() || enviando) return;

    setEnviando(true);
    setErro("");

    try {
      const { id } = await pedirAnalise(endereco.trim(), ramo.trim());
      router.push(`/analise/?id=${id}`);
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <label htmlFor="endereco">Repositório</label>
      <div className="linha-endereco">
        <input
          id="endereco"
          value={endereco}
          onChange={(e) => setEndereco(e.target.value)}
          placeholder="pallets/flask"
          spellCheck={false}
          autoComplete="off"
        />
        <button type="submit" className="botao" disabled={enviando || !endereco.trim()}>
          {enviando ? "Enviando" : "Analisar"}
        </button>
      </div>

      <label htmlFor="ramo">Ramo, se não for o principal</label>
      <input
        id="ramo"
        className="campo-ramo"
        value={ramo}
        onChange={(e) => setRamo(e.target.value)}
        spellCheck={false}
        autoComplete="off"
      />

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
    </form>
  );
}
