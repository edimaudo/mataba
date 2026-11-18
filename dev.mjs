import { build } from 'esbuild';
import { cp, mkdir, rm } from 'node:fs/promises';
import { existsSync, watch } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(root, 'dist');
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.mjs':'text/javascript; charset=utf-8', '.map':'application/json' };
let rebuilding = false;
let queued = false;

async function copyStatic() {
  await mkdir(out, { recursive: true });
  await cp(path.join(root, 'index.html'), path.join(out, 'index.html'));
  await cp(path.join(root, 'src/styles.css'), path.join(out, 'styles.css'));
  await cp(path.join(root, 'public/config.js'), path.join(out, 'config.js'));
  await mkdir(path.join(out, 'assets'), { recursive: true });
  const worker = path.join(root, 'node_modules/pdfjs-dist/build/pdf.worker.min.mjs');
  if (existsSync(worker)) await cp(worker, path.join(out, 'assets/pdf.worker.min.mjs'));
}

async function compile() {
  if (rebuilding) { queued = true; return; }
  rebuilding = true;
  try {
    await build({ entryPoints:[path.join(root,'src/main.ts')], outfile:path.join(out,'app.js'), bundle:true, platform:'browser', format:'esm', target:['es2022'], sourcemap:true, logLevel:'silent' });
    await copyStatic();
    console.log('Mataba refreshed.');
  } catch (error) { console.error(error); }
  rebuilding = false;
  if (queued) { queued = false; await compile(); }
}

await rm(out, { recursive:true, force:true });
await compile();
const server = http.createServer(async (req, res) => {
  const pathname = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname);
  const safePath = path.normalize(path.join(out, pathname === '/' ? 'index.html' : pathname));
  if (!safePath.startsWith(out)) { res.writeHead(403); res.end('Forbidden'); return; }
  try {
    const { readFile } = await import('node:fs/promises');
    const data = await readFile(safePath);
    res.writeHead(200, { 'Content-Type': mime[path.extname(safePath)] || 'application/octet-stream', 'Cache-Control':'no-store' });
    res.end(data);
  } catch { res.writeHead(404); res.end('Not found'); }
});
server.listen(4173, '0.0.0.0', () => console.log('Mataba running at http://localhost:4173'));
for (const dir of ['src','public']) watch(path.join(root,dir), { recursive:true }, () => compile());
