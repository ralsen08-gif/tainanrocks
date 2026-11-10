// GET /api/state          -> the current manifest: which blocks are published and where their files are.
// GET /api/state?fresh=1  -> the same, read past the CDN (the screen's Update button).
//
// The normal response is cached at Vercel's edge for a few seconds, so any number of open viewers
// cost at most ~10 manifest reads per minute. Those reads go through the Blob CDN, which can serve
// a manifest up to a minute old. ?fresh=1 costs two Blob operations per request (head + one
// uncached read), so it's only used when someone presses Update.
import * as blob from '@vercel/blob';
import { json, readManifest, readManifestFresh } from '../lib/manifest.js';

export default {
  async fetch(request) {
    const fresh = new URL(request.url).searchParams.get('fresh') === '1';
    try {
      if (fresh) {
        let manifest, isFresh = true;
        try {
          ({ manifest } = await readManifestFresh(blob));
        } catch (err) {
          console.error(err);
          ({ manifest } = await readManifest(blob)); // storage hiccup: better a cached list than none
          isFresh = false;
        }
        return json({ ...manifest, fresh: isFresh }, 200, {
          'cache-control': 'no-store',
          'cdn-cache-control': 'no-store',
        });
      }
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
