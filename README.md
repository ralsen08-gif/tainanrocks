# Workshop Live

Students design their block in Rhino and press **Publish**. The class screen shows all blocks of the 4×4 grid together in 3D and updates within about 10 seconds.

```
Rhino (each group)                 Vercel                          Class screen (browser)
WorkshopPublish.py  ── .3dm ──▶  /api/publish ──▶ Blob storage ◀── index.html polls /api/state
                                                                   every 5 s, loads changed blocks
Rhino (optional)    ◀───────────  /api/state  (WorkshopSync.py pulls everything into Rhino)
```

## What's in here

| Path | What it is |
|---|---|
| `public/index.html` | The class-screen viewer: 3D model of all blocks plus a key plan showing who published when |
| `api/publish.js` | Receives uploads from Rhino (and lets you remove a block or clear everything) |
| `api/state.js` | Tells viewers which blocks exist and where their files are |
| `lib/manifest.js` | Shared storage logic |
| `rhino/WorkshopPublish.py` | The Publish button for students (Rhino 7 and 8, Windows and Mac) |
| `rhino/WorkshopSync.py` | Optional: shows all published blocks inside your own Rhino |

## Set up (once, about 10 minutes)

1. **Push this folder to your GitHub repository.**
2. **Import it in Vercel.** Add New → Project → pick the repo. Leave Framework Preset on *Other* and deploy. You'll get a URL like `https://your-project.vercel.app`.
3. **Add Blob storage.** In the project: Storage → Create → Blob → set access to **Public** → connect it to the project (all environments).
4. **Set the passcode.** Settings → Environment Variables → add `WORKSHOP_KEY` with any passcode you like (e.g. `blocks-2026`).
5. **Redeploy** (Deployments → ⋯ → Redeploy) so the new storage and passcode are picked up.
6. **Open your URL.** You should see the empty key plan and "No blocks yet."
7. **Edit the Rhino scripts.** At the top of `rhino/WorkshopPublish.py` and `rhino/WorkshopSync.py`, set:
   ```python
   SERVER_URL = "https://your-project.vercel.app"
   WORKSHOP_KEY = "blocks-2026"      # publish script only
   ```

## Before the workshop

- **Template file:** give every group the same .3dm with the 4×4 grid at real coordinates, so blocks land in the right place without anyone moving anything. Block IDs are rows A–D (A at the top of the key plan) and columns 1–4.
- **Context:** in your own file with the streets and the 8 unassigned blocks, run the publish script and choose `CONTEXT`. It shows in white.
- **Dry run:** publish from two laptops on the classroom Wi-Fi and check the screen updates.

## Students: installing the Publish button

1. Save `WorkshopPublish.py` somewhere permanent (e.g. Documents).
2. In Rhino, create a toolbar button or an alias with this macro (use your own path):
   ```
   ! _-RunPythonScript "C:\Users\you\Documents\WorkshopPublish.py"
   ```
   On Mac: `! _-RunPythonScript "/Users/you/Documents/WorkshopPublish.py"`
3. Click it. The first time it asks which block you're designing. After that, **Enter publishes**.
4. Optional: click **PublishOnSave** on the command line to turn it **On**. Every Ctrl+S then publishes automatically. After restarting Rhino, click the button once to re-arm it.

What gets published: everything visible. Hidden objects and hidden layers are skipped, so hide anything that shouldn't be on the big screen. Blocks over 4 MB are refused with a message saying so.

## On the screen

Open your Vercel URL fullscreen (F11). Keys: **R** slow orbit on/off, **C** colors (group / model colors / white model), **L** labels, **F** fit everything. Dragging pauses the orbit for 20 seconds.

URL options: `?title=Studio%20Rotterdam` sets the heading, `?poll=5` the refresh interval in seconds, `?rows=ABCD&cols=4` the grid.

## Optional: blocks inside your own Rhino

Run `WorkshopSync.py` on the presentation laptop. Each block arrives on its own layer `Workshop Live::B3` and is replaced whenever that group publishes. Run it again to stop. Don't model on those layers.

## Clearing between workshops

```bash
# remove everything
curl -X DELETE "https://your-project.vercel.app/api/publish?block=ALL" -H "x-workshop-key: blocks-2026"
# remove one block
curl -X DELETE "https://your-project.vercel.app/api/publish?block=B3" -H "x-workshop-key: blocks-2026"
```
(`curl` is built into Windows 10+ and macOS.)

## Limits on the free Vercel plan

- Each publish uses 2 of the 2,000 monthly "advanced" Blob operations, so roughly 900 publishes a month. A 3-hour workshop with 8 groups publishing every 10 minutes uses about 300.
- The screen reads the server about 10 times a minute no matter how many browsers are open, well inside the free read allowance. Close the viewer outside class hours.
- Uploads are capped at 4 MB per block (Vercel's request limit is 4.5 MB). Massing models are usually well under 1 MB.

## Troubleshooting

| Message | Fix |
|---|---|
| "Wrong workshop passcode" | `WORKSHOP_KEY` in the script doesn't match the Vercel environment variable (and redeploy after changing it). |
| "Server is missing the WORKSHOP_KEY environment variable" | Add it in Vercel and redeploy. |
| "can't reach https://…" | Check the URL in the script and the laptop's internet. |
| Viewer says "Can't reach the server" | Blob storage not connected to the project, or not redeployed after connecting. |
| Block appears in the wrong place | That group's file isn't based on the shared template coordinates. |
