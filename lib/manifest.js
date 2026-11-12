// Shared logic for the workshop API.
//
// Storage layout in the (public) Vercel Blob store:
//   blocks/<BLOCK>/<timestamp>.3dm   the published models, every version: the source of truth
//   blocks/<BLOCK>/<timestamp>.hidden.3dm   a version hidden from the class screen (kept, can be shown again)
//   manifest.json                    { updatedAt, blocks: { 3: { url, size, publishedAt,
//                                        versions: [{ url, size, publishedAt }, … oldest first] } } }
//                                    (url/size/publishedAt are the newest visible version's; versions
//                                    hidden from the screen carry hidden: true, and a group with only
//                                    hidden versions carries hidden: true itself)
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
export const MAX_VERSIONS = 100;           // per group; older versions are deleted
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
      const hidden = /\.hidden\.3dm$/i.test(file);
      const stamp = Number(file.replace(/(\.hidden)?\.3dm$/i, ''));
      const at = Number.isFinite(stamp) && stamp > 0 ? stamp : new Date(b.uploadedAt).getTime();
      models.push({ block, url: b.url, pathname: b.pathname, size: b.size, at, hidden });
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return models;
}

// Every version per block (oldest first, at most MAX_VERSIONS), plus the URLs of versions beyond
// that cap (safe to delete). The newest version's url/size/publishedAt also sit on the entry itself.
function summarise(models) {
  const byBlock = {};
  for (const m of models) {
    const list = (byBlock[m.block] ||= []);
    // A page can list a file twice while other uploads change the folder: keep each file once.
    if (!list.some((x) => x.url === m.url)) list.push(m);
  }
  const blocks = {};
  const older = [];
  for (const [block, list] of Object.entries(byBlock)) {
    list.sort((a, b) => a.at - b.at);
    while (list.length > MAX_VERSIONS) older.push(list.shift().url);
    const versions = list.map((m) => ({ url: m.url, size: m.size, publishedAt: new Date(m.at).toISOString(), ...(m.hidden ? { hidden: true } : {}) }));
    const shown = versions.filter((v) => !v.hidden);
    blocks[block] = shown.length ? { ...shown[shown.length - 1], versions } : { hidden: true, versions };
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

// Rebuild manifest.json from the stored models (dropping versions beyond the cap). Returns the manifest.
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
  let entry = manifest.blocks[block];
  if (!entry || entry.url !== stored.url) {   // list() didn't show the new file yet
    const latest = { url: stored.url, size: bytes.length, publishedAt: new Date().toISOString() };
    const versions = ((entry && entry.versions) || []).filter((v) => v.url !== stored.url).concat([latest]);
    entry = manifest.blocks[block] = { ...latest, versions };
    await writeManifest(blob, manifest);
  }
  return { block, url: entry.url, size: entry.size, publishedAt: entry.publishedAt,
    version: entry.versions.length, blocksPublished: Object.keys(manifest.blocks).length };
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

// ---- managing the timeline (passcode-protected, see api/manage.js)
// Only files that are in the model listing can be touched, so nothing else in the store can be
// renamed or deleted through these.
async function findModel(blob, url) {
  const model = (await listModels(blob)).find((m) => m.url === url);
  if (!model) throw Object.assign(new Error('That version no longer exists. Press Update to refresh.'), { status: 404 });
  return model;
}
const RENAME_OPTS = { access: 'public', addRandomSuffix: false, contentType: 'application/octet-stream' };
const hiddenPath = (m) => m.pathname.replace(/(\.hidden)?\.3dm$/i, '.hidden.3dm');
const shownPath = (m) => m.pathname.replace(/(\.hidden)?\.3dm$/i, '.3dm');

// Hide a version from the class screen (or show it again): the file is renamed, nothing is lost.
export async function setVersionHidden(blob, url, hidden) {
  const m = await findModel(blob, url);
  if (m.hidden !== hidden) await blob.rename(m.url, hidden ? hiddenPath(m) : shownPath(m), RENAME_OPTS);
  return (await syncManifest(blob)).manifest;
}
// Hide (or show) every version of a group.
export async function setGroupHidden(blob, block, hidden) {
  const models = (await listModels(blob)).filter((m) => m.block === block && m.hidden !== hidden);
  for (const m of models) await blob.rename(m.url, hidden ? hiddenPath(m) : shownPath(m), RENAME_OPTS);
  return (await syncManifest(blob)).manifest;
}
// Delete one version for good.
export async function deleteVersion(blob, url) {
  const m = await findModel(blob, url);
  await blob.del(m.url);
  return (await syncManifest(blob)).manifest;
}

export function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*', ...headers },
  });
}
