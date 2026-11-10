// GET /api/state -> the current manifest: which blocks are published and where their files are.
// The response is cached at Vercel's edge for a few seconds, so any number of open viewers
// cost at most ~10 manifest reads per minute.
import * as blob from '@vercel/blob';
import { json, readManifest } from '../lib/manifest.js';

export default {
  async fetch() {
    try {
      const { manifest } = await readManifest(blob);
      return json(manifest, 200, {
        'cache-control': 'public, max-age=0, must-revalidate',
        'cdn-cache-control': 'public, s-maxage=6, stale-while-revalidate=20',
      });
    } catch (err) {
      console.error(err);
      return json({ error: String((err && err.message) || err), blocks: {} }, 500, { 'cache-control': 'no-store' });
    }
  },
};
