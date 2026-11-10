// POST   /api/publish?block=B3   body: .3dm bytes, header x-workshop-key  -> publish a block
// DELETE /api/publish?block=B3   header x-workshop-key                    -> remove one block
// DELETE /api/publish?block=ALL  header x-workshop-key                    -> clear everything
import * as blob from '@vercel/blob';
import { checkKey, json, looksLike3dm, MAX_BYTES, normaliseBlock, publishBlock, removeBlock } from '../lib/manifest.js';

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-methods': 'POST, DELETE, OPTIONS',
          'access-control-allow-headers': 'content-type, x-workshop-key',
        },
      });
    }
    if (request.method !== 'POST' && request.method !== 'DELETE') {
      return json({ ok: false, error: 'Use POST to publish or DELETE to remove.' }, 405);
    }

    const keyError = checkKey(request);
    if (keyError) return json({ ok: false, error: keyError }, 401);

    const url = new URL(request.url);
    const block = normaliseBlock(url.searchParams.get('block'));
    if (!block) return json({ ok: false, error: 'Missing or invalid ?block= (letters, digits, - and _ only).' }, 400);

    try {
      if (request.method === 'DELETE') {
        return json({ ok: true, block, ...(await removeBlock(blob, block)) });
      }

      if (block === 'ALL') return json({ ok: false, error: '"ALL" is reserved for clearing.' }, 400);
      const bytes = new Uint8Array(await request.arrayBuffer());
      if (bytes.length === 0) return json({ ok: false, error: 'Empty upload.' }, 400);
      if (bytes.length > MAX_BYTES) {
        return json({ ok: false, error: `Model is ${(bytes.length / 1048576).toFixed(1)} MB; the limit is 4 MB. Simplify or hide detail and try again.` }, 413);
      }
      if (!looksLike3dm(bytes)) return json({ ok: false, error: 'That is not a Rhino .3dm file.' }, 400);

      return json({ ok: true, ...(await publishBlock(blob, block, bytes)) });
    } catch (err) {
      console.error(err);
      return json({ ok: false, error: String((err && err.message) || err) }, 500);
    }
  },
};
