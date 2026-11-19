import type { Metadata } from "next";
import Link from "next/link";

import "@fontsource-variable/exo-2";
import "@fontsource-variable/orbitron";
import "@fontsource-variable/quicksand";

import Tema from "@/components/Tema";
import "./globals.css";

export const metadata: Metadata = {
  title: "DefectLens",
  description: "Chance de defeito por arquivo e porcentagem estimada de um repositório Python do GitHub",
};

const INICIAR = `try{var d=document.documentElement,t=localStorage.getItem("defectlens-tema"),m=localStorage.getItem("defectlens-modo");if(t==="1"||t==="2")d.dataset.tema=t;if(m==="claro"||m==="escuro")d.dataset.modo=m}catch(e){}`;

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: INICIAR }} />
      </head>
      <body>
        <header className="cabecalho">
          <div className="cabecalho-interno">
            <Link href="/" className="marca">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
                <circle cx="10.5" cy="10.5" r="6.5" />
                <path d="M15.5 15.5L21 21" />
                <rect x="7.5" y="7.5" width="2.6" height="2.6" rx="0.6" className="marca-ponto" />
                <rect x="11" y="11" width="2.6" height="2.6" rx="0.6" className="marca-ponto" />
              </svg>
              <span>DefectLens</span>
            </Link>
            <Tema />
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
