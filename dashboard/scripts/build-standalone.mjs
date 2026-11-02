import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Self-contained distribution of the built frontend: no server or npm needed.
const root = fileURLToPath(new URL('../../', import.meta.url));
const dist = path.join(root, 'dist-dashboard');
const output = path.join(root, 'dashboard/docs/TRANSIT_ATLAS_CONNECTED.html');
let html = await readFile(path.join(dist, 'index.html'), 'utf8');
const assetPath = (url) => {
  const resolved = path.resolve(dist, url.replace(/^\//, ''));
  if (!resolved.startsWith(dist + path.sep)) throw new Error('Invalid build asset path');
  return resolved;
};
for (const match of [...html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*>/g)]) {
  const href = match[0].match(/href="([^"]+)"/)?.[1];
  if (!href) continue;
  let css = await readFile(assetPath(href), 'utf8');
  const urls = [...new Set([...css.matchAll(/url\(([^)]+)\)/g)].map(m => m[1].replace(/^['"]|['"]$/g, '')))];
  for (const url of urls) {
    if (url.startsWith('data:')) continue;
    if (/^https?:/.test(url)) throw new Error('Standalone build cannot require external CSS assets');
    const absolute = url.startsWith('/') ? assetPath(url) : path.resolve(path.dirname(assetPath(href)), url);
    if (!absolute.startsWith(dist + path.sep)) throw new Error('Invalid CSS asset path');
    const mime = absolute.endsWith('.woff2') ? 'font/woff2' : absolute.endsWith('.woff') ? 'font/woff' : absolute.endsWith('.svg') ? 'image/svg+xml' : null;
    if (!mime) throw new Error('Unsupported standalone asset: ' + path.extname(absolute));
    const data = await readFile(absolute);
    css = css.split(url).join(`data:${mime};base64,${data.toString('base64')}`);
  }
  html = html.replace(match[0], () => `<style>${css}</style>`);
}
for (const match of [...html.matchAll(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g)]) {
  const js = await readFile(assetPath(match[1]), 'utf8');
  html = html.replace(match[0], () => `<script type="module">${js.replace(/<\/script/gi, '<\\/script')}</script>`);
}
html = html.replace(/<link\b[^>]*rel="modulepreload"[^>]*>/g, '');
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, html);
console.log(`Standalone HTML created: ${output} (${Buffer.byteLength(html)} bytes)`);
