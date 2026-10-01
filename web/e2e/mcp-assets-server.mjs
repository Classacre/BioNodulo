// Serve the actual production chunks from an origin different from the MCP
// host. The /build prefix and CORS match the deployed cloud editor assets.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
createServer(async (request, response) => {
  const pathname = new URL(request.url ?? '/', 'http://127.0.0.1:5176').pathname;
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
  response.setHeader('Cache-Control', 'no-store');
  if (pathname === '/health') { response.end('ready'); return; }
  if (!/^\/build\/assets\/[\w.-]+\.(?:js|css)$/.test(pathname)) {
    response.writeHead(404); response.end('Unknown production asset'); return;
  }
  const target = resolve(root, pathname.slice('/build/'.length));
  if (!target.startsWith(resolve(root) + sep)) {
    response.writeHead(400); response.end('Invalid asset path'); return;
  }
  try {
    const content = await readFile(target);
    response.setHeader('Content-Type', pathname.endsWith('.css') ? 'text/css' : 'text/javascript');
    response.end(content);
  } catch (error) {
    response.writeHead(error.code === 'ENOENT' ? 404 : 500);
    response.end('Production asset unavailable');
  }
}).listen(5176, '127.0.0.1');
