import { defineConfig, type Plugin } from "vite";
import { resolve } from "node:path";

/** The app page starts its data load from a tiny separate script (src/early.ts) so the requests begin while the big app script is still downloading.
 *  Vite folds every <script> of an HTML page into one chunk, so early.ts is a second build input and this plugin adds its tag to app/index.html after the build. */
const earlyScript = (): Plugin => ({
  name: "early-script",
  transformIndexHtml: {
    order: "post",
    handler(_html, ctx) {
      if (!ctx.filename.replaceAll("\\", "/").endsWith("/app/index.html")) return;
      const chunk = ctx.bundle && Object.values(ctx.bundle).find((c) => c.type === "chunk" && c.isEntry && c.name === "early");
      const src = chunk ? `${ctx.server ? "" : (process.env.BASE ?? "/")}${chunk.fileName}` : "/src/early.ts"; // dev server: the source file
      // A module script waits for the stylesheets before it in the page; a classic inline script ahead of them does not, and its import() starts the download at once.
      return [chunk ? { tag: "script", children: `import(${JSON.stringify(src)})`, injectTo: "head-prepend" as const } : { tag: "script", attrs: { type: "module", src }, injectTo: "head-prepend" as const }];
    },
  },
});

// Custom domain https://abang.earth serves from the root -> base "/".
// For a project-pages URL (/abang_on_earth/) build with BASE=/abang_on_earth/.
export default defineConfig({
  base: process.env.BASE ?? "/",
  plugins: [earlyScript()],
  build: {
    target: "es2022",
    rollupOptions: {
      input: {
        home: resolve(import.meta.dirname, "index.html"),
        app: resolve(import.meta.dirname, "app/index.html"),
        credits: resolve(import.meta.dirname, "credits/index.html"),
        early: resolve(import.meta.dirname, "src/early.ts"),
      },
    },
  },
});
