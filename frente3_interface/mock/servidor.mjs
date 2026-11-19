import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const exemplos = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "contratos", "exemplos");
const ler = (nome) => JSON.parse(readFileSync(join(exemplos, nome), "utf8"));
const porta = Number(process.env.PORT ?? 8000);

const IDENTIFICADOR = "7b40bcf8-7dc0-4cdc-b791-cffb028c6be9";

const rotas = [
  [/^\/api\/saude\/$/, () => ({ ok: true })],
  [/^\/api\/modelo\/$/, () => ler("modelo.json")],
  [/^\/api\/analises\/$/, (req) => (req.method === "POST"
    ? { id: IDENTIFICADOR, reaproveitada: true }
    : ler("recentes.json"))],
  [/^\/api\/analises\/[0-9a-f-]+\/$/, () => ler("analise_flask.json")],
];

createServer((req, res) => {
  const cabecalhos = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };

  if (req.method === "OPTIONS") {
    res.writeHead(204, cabecalhos).end();
    return;
  }

  const caminho = new URL(req.url, "http://localhost").pathname;
  const rota = rotas.find(([padrao]) => padrao.test(caminho));

  if (!rota) {
    res.writeHead(404, cabecalhos).end(JSON.stringify({ erro: "Rota inexistente" }));
    return;
  }

  res.writeHead(200, cabecalhos).end(JSON.stringify(rota[1](req)));
}).listen(porta, "127.0.0.1", () => {
  console.log(`API simulada em http://127.0.0.1:${porta}`);
});
