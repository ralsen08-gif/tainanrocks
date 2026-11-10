// Shared logic for the workshop API.
//
// Storage layout in the (public) Vercel Blob store:
//   blocks/<BLOCK>/<timestamp>.3dm   one file per published version (old ones are deleted)
//   manifest.json                    { updatedAt, blocks: { B3: { url, size, publishedAt } } }
//
// The manifest is updated with optimistic concurrency (ETag / ifMatch), so two groups
// publishing at the same moment can't overwrite each other's entry.
//
// Blob operations per publish: 2 "advanced" (put model + put manifest) + 1 "simple" (read manifest).
// list() is never used on the hot path, because it is an advanced operation and the
// Hobby plan only includes 2,000 of those per month.

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

export async function readManifest(blob) {
  const res = await blob.get(MANIFEST_PATH, { access: 'public', useCache: false });
  if (!res || res.statusCode !== 200) return { manifest: { updatedAt: null, blocks: {} }, etag: null };
  const text = await new Response(res.stream).text();
  let manifest;
  try {
    manifest = JSON.parse(text);
  } catch {
    manifest = {};
  }
  if (!manifest.blocks || typeof manifest.blocks !== 'object') manifest.blocks = {};
  return { manifest, etag: res.blob.etag };
}

async function writeManifest(blob, manifest, etag) {
  const opts = {
    access: 'public',
    contentType: 'application/json',
    addRandomSuffix: false,
    cacheControlMaxAge: 60,
  };
  // Existing manifest: only overwrite the exact version we read.
  // No manifest yet: fail if another request created it meanwhile (we then retry).
  if (etag) opts.ifMatch = etag;
  else opts.allowOverwrite = false;
  return blob.put(MANIFEST_PATH, JSON.stringify(manifest), opts);
}

// Apply `mutate(manifest)` and save, retrying if another request changed the manifest first.
// Returns the list of blob URLs that are no longer referenced (safe to delete).
export async function updateManifest(blob, mutate, attempts = 6) {
  let lastErr;
  for (let i = 0; i < attempts; i++) {
    const { manifest, etag } = await readManifest(blob);
    const orphaned = mutate(manifest) || [];
    manifest.updatedAt = new Date().toISOString();
    try {
      await writeManifest(blob, manifest, etag);
      return { manifest, orphaned };
    } catch (err) {
      const conflict =
        err instanceof blob.BlobPreconditionFailedError ||
        /already exists|precondition/i.test(String(err && err.message));
      if (!conflict) throw err;
      lastErr = err;
      await new Promise((r) => setTimeout(r, 100 + Math.random() * 300));
    }
  }
  throw lastErr || new Error('Could not update manifest');
}

export async function publishBlock(blob, block, bytes) {
  const pathname = `blocks/${block}/${Date.now()}.3dm`;
  const stored = await blob.put(pathname, Buffer.from(bytes), {
    access: 'public',
    contentType: 'application/octet-stream',
    addRandomSuffix: false,
  });
  const entry = { url: stored.url, size: bytes.length, publishedAt: new Date().toISOString() };
  const { manifest, orphaned } = await updateManifest(blob, (m) => {
    const previous = m.blocks[block];
    m.blocks[block] = entry;
    return previous && previous.url !== entry.url ? [previous.url] : [];
  });
  if (orphaned.length) await blob.del(orphaned).catch(() => {});
  return { block, ...entry, blocksPublished: Object.keys(manifest.blocks).length };
}

export async function removeBlock(blob, block) {
  if (block === 'ALL') {
    const urls = [];
    let cursor;
    do {
      const page = await blob.list({ prefix: 'blocks/', cursor });
      urls.push(...page.blobs.map((b) => b.url));
      cursor = page.hasMore ? page.cursor : undefined;
    } while (cursor);
    await updateManifest(blob, (m) => {
      m.blocks = {};
      return [];
    });
    if (urls.length) await blob.del(urls);
    return { removed: urls.length };
  }
  const { orphaned } = await updateManifest(blob, (m) => {
    const previous = m.blocks[block];
    delete m.blocks[block];
    return previous ? [previous.url] : [];
  });
  if (orphaned.length) await blob.del(orphaned).catch(() => {});
  return { removed: orphaned.length };
}

export function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*', ...headers },
  });
}
