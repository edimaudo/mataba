import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
const root = path.join(process.cwd(), 'dist');
const types = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.mjs':'text/javascript; charset=utf-8' };
http.createServer(async (req,res) => {
  const requested = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname);
  const file = path.normalize(path.join(root, requested === '/' ? 'index.html' : requested));
  if (!file.startsWith(root)) { res.writeHead(403).end(); return; }
  try { res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'}); res.end(await readFile(file)); }
  catch { res.writeHead(404).end('Not found'); }
}).listen(4173, '0.0.0.0', () => console.log('Serving dist at http://localhost:4173'));
