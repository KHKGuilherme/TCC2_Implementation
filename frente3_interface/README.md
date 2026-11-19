# Frente 3: interface

O site. Mostra o formulário para colar o endereço de um repositório, o andamento da análise e o resultado. Não tem lógica de modelo, fila ou banco: só chama a API da Frente 2, descrita em `../contratos/api.openapi.json`.

Next.js exportado como site estático, para hospedar na Cloudflare.

## Desenvolvimento

```
npm ci
npm run dev
```

O endereço da API vem de `NEXT_PUBLIC_DEFECTLENS_API`. Em desenvolvimento, `.env.development` aponta para `http://127.0.0.1:8000`.

Para trabalhar sem a Frente 2, suba a API simulada, que devolve os exemplos de `../contratos/exemplos/`:

```
npm run mock
```

## Tipos

Os tipos de `src/tipos/api.d.ts` saem do contrato. Depois de mudar o `api.openapi.json`:

```
npm run tipos
```

## Build

```
NEXT_PUBLIC_DEFECTLENS_API=https://endereco-da-api npm run build
```

O build falha se a variável não estiver definida. O site fica em `out/`.

## Publicação na Cloudflare

No painel da Cloudflare, em Workers e Pages, crie um projeto a partir do repositório do GitHub, com estes campos:

| Campo | Valor |
|---|---|
| Diretório raiz | `frente3_interface` |
| Comando de build | `npm ci && npm run build` |
| Comando de deploy | `npx wrangler deploy` |
| Variável de ambiente | `NEXT_PUBLIC_DEFECTLENS_API` com o endereço da API |

O `wrangler.jsonc` já aponta para a pasta `out/`. A versão do Node vem de `.node-version`.

Na API, defina `DEFECTLENS_CORS` com o endereço do site (ou `*`) para o navegador poder chamá-la.
