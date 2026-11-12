// Managing the timeline from the class screen's Manage panel. Header x-workshop-key, JSON body:
//   { action: 'hide' | 'show',   url }      hide one version from the screen, or show it again
//   { action: 'delete',          url }      delete one version for good
//   { action: 'hide-group' | 'show-group', block }   all versions of a group
//   { action: 'delete-group',    block }    delete a group with all its versions
// Answers with the updated manifest, so the screen can show the change straight away.
import * as blob from '@vercel/blob';
import { checkKey, deleteVersion, json, normaliseBlock, removeBlock, setGroupHidden, setVersionHidden, syncManifest } from '../lib/manifest.js';

export default {
  async fetch(request) {
    if (request.method !== 'POST') return json({ ok: false, error: 'Use POST.' }, 405);
    const keyError = checkKey(request);
    if (keyError) return json({ ok: false, error: keyError }, 401);

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ ok: false, error: 'Send a JSON body.' }, 400);
    }
    const { action, url } = body || {};
    const block = normaliseBlock(body && body.block);
    try {
      let manifest;
      if (action === 'hide' || action === 'show') {
        if (typeof url !== 'string') return json({ ok: false, error: 'Missing url.' }, 400);
        manifest = await setVersionHidden(blob, url, action === 'hide');
      } else if (action === 'delete') {
        if (typeof url !== 'string') return json({ ok: false, error: 'Missing url.' }, 400);
        manifest = await deleteVersion(blob, url);
      } else if (action === 'hide-group' || action === 'show-group') {
        if (!block || block === 'ALL') return json({ ok: false, error: 'Missing or invalid block.' }, 400);
        manifest = await setGroupHidden(blob, block, action === 'hide-group');
      } else if (action === 'delete-group') {
        if (!block || block === 'ALL') return json({ ok: false, error: 'Missing or invalid block.' }, 400);
        await removeBlock(blob, block);
        manifest = (await syncManifest(blob)).manifest;
      } else {
        return json({ ok: false, error: 'Unknown action.' }, 400);
      }
      return json({ ok: true, ...manifest, fresh: true }, 200, { 'cache-control': 'no-store' });
    } catch (err) {
      console.error(err);
      return json({ ok: false, error: String((err && err.message) || err) }, err && err.status ? err.status : 500);
    }
  },
};
