import { readFileSync, writeFileSync } from "node:fs";

for (const arquivo of process.argv.slice(2)) {
  const limpo = readFileSync(arquivo, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((linha) => !/^\s*\/\//.test(linha))
    .map((linha) => linha.replace(/\s+$/, ""))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^\n+/, "")
    .replace(/\n*$/, "\n");
  writeFileSync(arquivo, limpo);
}
