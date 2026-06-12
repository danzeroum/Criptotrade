/**
 * Build de producao do Console React (P3-1).
 *
 * O console e' um app de "classic scripts": React/ReactDOM sao globais UMD e os
 * 13 arquivos compartilham escopo global (componentes referenciados por nome
 * bare, ex.: <Badge/>, sem import/export). Em dev isso roda via @babel/standalone
 * transpilando JSX no browser e React 'development' por CDN.
 *
 * Este build NAO modulariza (preservaria-se o acoplamento global): apenas
 *   1. pre-transpila cada .jsx -> .js (JSX -> React.createElement) e minifica,
 *   2. minifica os .js/.css,
 *   3. self-hosta o React/ReactDOM *production* (sem CDN em runtime),
 *   4. reescreve o index.html removendo o Babel e o React dev.
 *
 * Resultado em dist/: JS minificado, zero transpile no browser, zero CDN.
 * Saida e' gitignored; gerada na CI e no deploy.
 */
import { build } from "esbuild";
import { readFile, writeFile, rm, mkdir, copyFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(here, "dist");
const vendor = path.join(dist, "vendor");

const log = (m) => console.log(`[console-build] ${m}`);

// 1. Limpa a saida
await rm(dist, { recursive: true, force: true });
await mkdir(vendor, { recursive: true });

// 2. Transpila + minifica os fontes.
//    bundle:false => cada arquivo e' transpilado isoladamente, SEM resolver
//    imports e SEM renomear identificadores top-level (tratados como globais),
//    o que preserva exatamente a semantica de classic-script (refs bare como
//    <Badge/> continuam resolvendo entre arquivos via escopo global).
const jsx = (await readdir(here)).filter((f) => f.endsWith(".jsx")).sort();
const js = ["apiClient.js", "data.js"].filter((f) => existsSync(path.join(here, f)));
log(`transpilando ${jsx.length} .jsx + ${js.length} .js (minify)`);
await build({
  entryPoints: [...jsx, ...js].map((f) => path.join(here, f)),
  outdir: dist,
  bundle: false,
  minify: true,
  jsx: "transform",
  jsxFactory: "React.createElement",
  jsxFragment: "React.Fragment",
  loader: { ".jsx": "jsx" },
  logLevel: "warning",
});

// 3. Minifica o CSS
if (existsSync(path.join(here, "styles.css"))) {
  await build({
    entryPoints: [path.join(here, "styles.css")],
    outdir: dist,
    minify: true,
    loader: { ".css": "css" },
    logLevel: "warning",
  });
}

// 4. Self-host do React/ReactDOM de producao (sem CDN em runtime)
const umd = [
  ["react/umd/react.production.min.js", "react.production.min.js"],
  ["react-dom/umd/react-dom.production.min.js", "react-dom.production.min.js"],
];
for (const [from, to] of umd) {
  const src = path.join(here, "node_modules", from);
  if (!existsSync(src)) {
    throw new Error(`UMD ausente: ${src}. Rode 'npm ci' antes do build.`);
  }
  await copyFile(src, path.join(vendor, to));
}
log("React/ReactDOM production self-hosted em dist/vendor/");

// 5. Reescreve o index.html para producao:
//    - React dev CDN  -> vendor local (production)
//    - remove @babel/standalone
//    - <script type="text/babel" src="X.jsx"> -> <script src="X.js">
let html = await readFile(path.join(here, "index.html"), "utf8");
html = html
  .replace(
    /<script src="https:\/\/unpkg\.com\/react@[^"]*"[^>]*><\/script>/,
    '<script src="vendor/react.production.min.js"></script>',
  )
  .replace(
    /<script src="https:\/\/unpkg\.com\/react-dom@[^"]*"[^>]*><\/script>/,
    '<script src="vendor/react-dom.production.min.js"></script>',
  )
  .replace(/\n\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone[^"]*"[^>]*><\/script>/, "")
  .replace(/<script type="text\/babel" src="([^"]+)\.jsx"><\/script>/g, '<script src="$1.js"></script>');

if (/text\/babel|@babel\/standalone|react\.development/.test(html)) {
  throw new Error("index.html ainda referencia Babel/React dev apos a reescrita.");
}
await writeFile(path.join(dist, "index.html"), html);
log("dist/index.html reescrito (sem Babel, sem React dev, sem CDN)");
log("OK: build em docs/design/pages/dist/");
