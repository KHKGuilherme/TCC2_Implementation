import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "DefectLens",
  description: "Chance de defeito por arquivo e porcentagem estimada de um repositório Python do GitHub",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="cabecalho">
          <div className="cabecalho-interno">
            <Link href="/" className="marca">
              DefectLens
            </Link>
          </div>
        </header>

        <main>{children}</main>

        <footer className="rodape">
          Trabalho de Conclusão de Curso, Engenharia de Computação, UTFPR Apucarana.
        </footer>
      </body>
    </html>
  );
}
