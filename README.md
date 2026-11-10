# Workshop Live

Each group designs one piece (a cube) in Rhino and presses **Publish**. The class screen shows the pieces the way the reference Rhino file lays them out, and updates within about 10 seconds:

- **Combined**: all pieces together at their real Rhino coordinates (e.g. eight cubes forming one 2×2×2 cube)
- **Combined exploded**: the same, with every piece pushed away from the centre so you can see each one
- **Group 1 … Group 8**: a row of plates, each showing one group's piece on its own, with when it was last published

```
Rhino (each group)                 Vercel                          Class screen (browser)
WorkshopPublish.py  ── .3dm ──▶  /api/publish ──▶ Blob storage ◀── index.html polls /api/state
                                                                   every 5 s, loads changed groups
Rhino (optional)    ◀───────────  /api/state  (WorkshopSync.py pulls everything into Rhino)
```

## What's in here

| Path | What it is |
|---|---|
| `public/index.html` | The class-screen viewer: Combined, Combined exploded and one plate per group, all in one 3D scene |
| `api/publish.js` | Receives uploads from Rhino (and lets you remove a group or clear everything) |
| `api/state.js` | Tells viewers which groups have published and where their files are |
| `lib/manifest.js` | Shared storage logic |
| `rhino/WorkshopPublish.py` | The Publish button for students (Rhino 7 and 8, Windows and Mac) |
| `rhino/WorkshopSync.py` | Optional: shows all published pieces inside your own Rhino |

## Set up (once, about 10 minutes)

1. **Push this folder to your GitHub repository.**
2. **Import it in Vercel.** Add New → Project → pick the repo. Leave Framework Preset on *Other* and deploy. You'll get a URL like `https://your-project.vercel.app`.
3. **Add Blob storage.** In the project: Storage → Create → Blob → set access to **Public** → connect it to the project (all environments).
4. **Set the passcode.** Settings → Environment Variables → add `WORKSHOP_KEY` with any passcode you like (e.g. `blocks-2026`).
5. **Redeploy** (Deployments → ⋯ → Redeploy) so the new storage and passcode are picked up.
6. **Open your URL.** You should see the empty plates (Combined, Combined exploded, Group 1–8) and "No groups yet."
7. **Edit the Rhino scripts.** At the top of `rhino/WorkshopPublish.py` and `rhino/WorkshopSync.py`, set:
   ```python
   SERVER_URL = "https://your-project.vercel.app"
   WORKSHOP_KEY = "blocks-2026"      # publish script only
   ```

## Before the workshop

- **Template file:** give every group the same .3dm with each group's cube already at its place in the combined shape (real coordinates), so the **Combined** view assembles itself without anyone moving anything. The viewer centres each group's piece on its own plate, so position only matters for Combined.
- **Group IDs:** when the publish script asks which block you're designing, groups answer with their number: `1` … `8` (`G3` or `GROUP3` also work). Any other ID gets an extra plate at the end of the row.
- **Colours:** the screen uses each object's colour from Rhino (object colour, or the layer colour if that isn't black). Pieces without a colour get the group's colour: 1 grey, 2 yellow, 3 green, 4 dark green, 5 red, 6 light red, 7 cyan, 8 purple.
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

Open your Vercel URL fullscreen (F11). Drag to orbit, scroll to zoom. Keys: **R** slowly spins each model on its plate, **C** colours (model colours / group colours / white model), **L** plate labels, **F** fit everything. A plate is tinted for 90 seconds after its group publishes.

URL options: `?title=Studio%20Rotterdam` sets the heading, `?poll=5` the refresh interval in seconds, `?groups=8` the number of group plates, `?explode=1` how far the exploded view pushes pieces apart (1 = each piece moves its own distance from the centre again; 0.5 = half that).

## Optional: blocks inside your own Rhino

Run `WorkshopSync.py` on the presentation laptop. Each group arrives on its own layer `Workshop Live::3` and is replaced whenever that group publishes. Run it again to stop. Don't model on those layers.

## Clearing between workshops

```bash
# remove everything
curl -X DELETE "https://your-project.vercel.app/api/publish?block=ALL" -H "x-workshop-key: blocks-2026"
# remove one group
curl -X DELETE "https://your-project.vercel.app/api/publish?block=3" -H "x-workshop-key: blocks-2026"
```
(`curl` is built into Windows 10+ and macOS.)

## Limits on the free Vercel plan

- Each publish uses 2 of the 2,000 monthly "advanced" Blob operations, so roughly 900 publishes a month. A 3-hour workshop with 8 groups publishing every 10 minutes uses about 300.
- The screen reads the server about 10 times a minute no matter how many browsers are open, well inside the free read allowance. Close the viewer outside class hours.
- Uploads are capped at 4 MB per group (Vercel's request limit is 4.5 MB). Massing models are usually well under 1 MB.

## Troubleshooting

| Message | Fix |
|---|---|
| "Wrong workshop passcode" | `WORKSHOP_KEY` in the script doesn't match the Vercel environment variable (and redeploy after changing it). |
| "Server is missing the WORKSHOP_KEY environment variable" | Add it in Vercel and redeploy. |
| "can't reach https://…" | Check the URL in the script and the laptop's internet. |
| Viewer says "Can't reach the server" | Blob storage not connected to the project, or not redeployed after connecting. |
| A piece is in the wrong place in Combined | That group's file isn't based on the shared template coordinates. |
| A group's piece doesn't show | Publish it as meshes (or with render meshes saved). Only meshes, curves, and breps/extrusions that carry a render mesh can be drawn in the browser. |
