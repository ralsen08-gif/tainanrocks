// Shared logic for the workshop API.
//
// Storage layout in the (public) Vercel Blob store:
//   blocks/<BLOCK>/<timestamp>.3dm   the published models: the source of truth
//   manifest.json                    { updatedAt, blocks: { 3: { url, size, publishedAt } } }
//
// manifest.json is only a cheap, cacheable summary for the class screens. It is rebuilt from a
// list() of blocks/ after every publish or removal, never read-modified-written: reading it back
// goes through Vercel's CDN, which serves old copies whose ETags the Blob API then rejects
// ("Precondition failed: ETag mismatch"). list() goes to the Blob API and is always current.
//
// If two groups publish at the same instant, the manifest written last can miss the other
// group's new model. That heals itself on the next publish or when someone presses Update on the
// screen (which rebuilds the manifest too), because the model file itself is safely stored.
//
// Blob operations per publish: 3 "advanced" (put model, list, put manifest). The Hobby plan
// includes 2,000 advanced operations a month, so roughly 650 publishes.

export const MANIFEST_PATH = 'manifest.json';
export const MAX_BYTES = 4 * 1024 * 1024; // Vercel Functions reject request bodies over 4.5 MB
const BLOCK_RE = /^[A-Z0-9_-]{1,24}$/;
const RHINO_MAGIC = '3D Geometry File Format';

export function normaliseBlock(raw) {
  const block = String(raw || '').trim().toUpperCase();
  return BLOCK_RE.test(block) ? block : null;
}

export function looksLike3dm(bytes) {
  if (bytes.length < RHINO_MAGIC.length) return false;
  const head = new TextDecoder().decode(bytes.subarray(0, RHINO_MAGIC.length));
  return head === RHINO_MAGIC;
}

export function checkKey(request) {
  const expected = process.env.WORKSHOP_KEY;
  if (!expected) return 'Server is missing the WORKSHOP_KEY environment variable.';
  const given = request.headers.get('x-workshop-key') || '';
  return given === expected ? null : 'Wrong workshop passcode.';
}

function parseManifest(text) {
  let manifest;
  try {
    manifest = JSON.parse(text);
  } catch {
    manifest = {};
  }
  if (!manifest || typeof manifest !== 'object') manifest = {};
  if (!manifest.blocks || typeof manifest.blocks !== 'object') manifest.blocks = {};
  return manifest;
}

// The manifest as the class screens see it: through the CDN, so up to about a minute old.
export async function readManifest(blob) {
  const res = await blob.get(MANIFEST_PATH, { access: 'public' });
  if (!res || res.statusCode !== 200) return { manifest: { updatedAt: null, blocks: {} } };
  return { manifest: parseManifest(await new Response(res.stream).text()) };
}

// Every stored model, straight from the Blob API.
async function listModels(blob) {
  const models = [];
  let cursor;
  do {
    const page = await blob.list({ prefix: 'blocks/', cursor, limit: 1000 });
    for (const b of page.blobs) {
      const [, block, file] = b.pathname.split('/');
      if (!block || !file) continue;
      const stamp = Number(file.replace(/\.3dm$/i, ''));
      const at = Number.isFinite(stamp) && stamp > 0 ? stamp : new Date(b.uploadedAt).getTime();
      models.push({ block, url: b.url, size: b.size, at });
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return models;
}

// Newest model per block, plus the URLs of the older versions (safe to delete).
function summarise(models) {
  const blocks = {};
  const newest = {};
  const older = [];
  for (const m of models) {
    const cur = newest[m.block];
    // A page can list a file twice while other uploads change the folder: never treat a file as
    // older than itself, or the only copy of a group's model would be deleted.
    if (cur && (cur.url === m.url || cur.at === m.at)) continue;
    if (!cur || m.at > cur.at) {
      if (cur) older.push(cur.url);
      newest[m.block] = m;
    } else {
      older.push(m.url);
    }
  }
  for (const [block, m] of Object.entries(newest)) {
    blocks[block] = { url: m.url, size: m.size, publishedAt: new Date(m.at).toISOString() };
  }
  return { manifest: { updatedAt: new Date().toISOString(), blocks }, older };
}

async function writeManifest(blob, manifest) {
  await blob.put(MANIFEST_PATH, JSON.stringify(manifest), {
    access: 'public',
    contentType: 'application/json',
    addRandomSuffix: false,
    allowOverwrite: true,
    cacheControlMaxAge: 60,
  });
}

// Rebuild manifest.json from the stored models (and tidy up old versions). Returns the manifest.
export async function syncManifest(blob, { skipBlock } = {}) {
  const models = await listModels(blob);
  const removed = skipBlock ? models.filter((m) => m.block === skipBlock).map((m) => m.url) : [];
  const { manifest, older } = summarise(skipBlock ? models.filter((m) => m.block !== skipBlock) : models);
  if (removed.length) await blob.del(removed);
  await writeManifest(blob, manifest);
  if (older.length) await blob.del(older).catch(() => {});
  return { manifest, removed: removed.length };
}

export async function publishBlock(blob, block, bytes) {
  const pathname = `blocks/${block}/${Date.now()}.3dm`;
  const stored = await blob.put(pathname, Buffer.from(bytes), {
    access: 'public',
    contentType: 'application/octet-stream',
    addRandomSuffix: false,
  });
  const { manifest } = await syncManifest(blob);
  // list() may not show the brand-new file yet; never leave it out of the manifest we report.
  const entry = manifest.blocks[block] && manifest.blocks[block].url === stored.url
    ? manifest.blocks[block]
    : { url: stored.url, size: bytes.length, publishedAt: new Date().toISOString() };
  if (manifest.blocks[block] !== entry) {
    manifest.blocks[block] = entry;
    await writeManifest(blob, manifest);
  }
  return { block, ...entry, blocksPublished: Object.keys(manifest.blocks).length };
}

export async function removeBlock(blob, block) {
  if (block === 'ALL') {
    const urls = (await listModels(blob)).map((m) => m.url);
    if (urls.length) await blob.del(urls);
    await writeManifest(blob, { updatedAt: new Date().toISOString(), blocks: {} });
    return { removed: urls.length };
  }
  const { removed } = await syncManifest(blob, { skipBlock: block });
  return { removed };
}

export function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*', ...headers },
  });
}
