import { build } from 'esbuild';
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const out = path.join(root, 'dist');
await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });
await build({
  entryPoints: [path.join(root, 'src/main.ts')],
  outfile: path.join(out, 'app.js'),
  bundle: true,
  platform: 'browser',
  format: 'esm',
  target: ['es2022'],
  sourcemap: true,
  minify: false,
  logLevel: 'info'
});
await cp(path.join(root, 'index.html'), path.join(out, 'index.html'));
await cp(path.join(root, 'src/styles.css'), path.join(out, 'styles.css'));
await cp(path.join(root, 'public/config.js'), path.join(out, 'config.js'));
await mkdir(path.join(out, 'assets'), { recursive: true });
const worker = path.join(root, 'node_modules/pdfjs-dist/build/pdf.worker.min.mjs');
if (existsSync(worker)) await cp(worker, path.join(out, 'assets/pdf.worker.min.mjs'));
console.log('Mataba build created in dist/.');
