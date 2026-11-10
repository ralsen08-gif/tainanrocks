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
  return { manifest: parseManifest(await new Response(res.stream).text()), etag: res.blob.etag };
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

const bareEtag = (e) => String(e || '').replace(/^W\//, '').replace(/"/g, '').trim();

// The latest manifest, for read-modify-write. readManifest() above is fine for viewers, but it
// reads through Vercel's CDN, which keeps serving the previous manifest for up to 60 s after a
// write (get()'s useCache:false only bypasses that for private stores). Writing with that stale
// ETag fails with "Precondition failed: ETag mismatch", so every publish within a minute of the
// previous one failed. Here head() asks the Blob API for the current version, and the content
// is fetched with a unique query string so the CDN has to go to storage. The ETag check makes
// sure a stale copy is never used, so no group's entry can be lost.
export async function readManifestFresh(blob) {
  let meta;
  try {
    meta = await blob.head(MANIFEST_PATH);
  } catch (err) {
    if (err instanceof blob.BlobNotFoundError || /not.?found|does not exist/i.test(String(err && err.message))) {
      return { manifest: parseManifest('{}'), etag: null };
    }
    throw err;
  }
  for (let i = 0; i < 5; i++) {
    const url = new URL(meta.url);
    url.searchParams.set('fresh', `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`);
    const res = await fetch(url, { cache: 'no-store' });
    if (res.ok) {
      const etag = res.headers.get('etag');
      if (!etag || bareEtag(etag) === bareEtag(meta.etag)) {
        return { manifest: parseManifest(await res.text()), etag: meta.etag };
      }
    }
    await new Promise((r) => setTimeout(r, 250 * (i + 1)));
  }
  throw new Error('Could not read the latest list of published groups from Blob storage. Publish again in a minute.');
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
    const { manifest, etag } = await readManifestFresh(blob);
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
  let result;
  try {
    result = await updateManifest(blob, (m) => {
      const previous = m.blocks[block];
      m.blocks[block] = entry;
      return previous && previous.url !== entry.url ? [previous.url] : [];
    });
  } catch (err) {
    await blob.del(stored.url).catch(() => {}); // don't leave an unlisted model in storage
    throw err;
  }
  const { manifest, orphaned } = result;
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
