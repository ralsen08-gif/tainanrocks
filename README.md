# Workshop Live

Each group designs one piece (a cube) in Rhino and presses **Publish**. The class screen picks up new models by itself within about a minute, or straight away when you press **Update**, and has four views; the pieces glide between them:

- **Combined**: all pieces together at their real Rhino coordinates (e.g. eight cubes forming one 2×2×2 cube)
- **Exploded**: the same, with every piece pushed away from the centre; a slider sets the separation
- **One by one**: one group's piece on its own; step through the groups with ‹ › or the arrow keys
- **Matrix**: every group's piece side by side in a grid, with empty spots for groups that haven't published

```
Rhino (each group)                 Vercel                          Class screen (browser)
WorkshopPublish.py  ── .3dm ──▶  /api/publish ──▶ Blob storage ◀── index.html polls /api/state
                                                                   every 5 s, loads changed groups
Rhino (optional)    ◀───────────  /api/state  (WorkshopSync.py pulls everything into Rhino)
```

## What's in here

| Path | What it is |
|---|---|
| `public/index.html` | The class-screen viewer: Combined, Exploded, One by one and Matrix views, plus a status chip per group |
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
6. **Open your URL.** You should see the view switcher, eight empty group chips and "No groups yet."
7. **Edit the Rhino scripts.** At the top of `rhino/WorkshopPublish.py` and `rhino/WorkshopSync.py`, set:
   ```python
   SERVER_URL = "https://your-project.vercel.app"
   WORKSHOP_KEY = "blocks-2026"      # publish script only
   ```

## Before the workshop

- **Template file:** give every group the same .3dm with each group's cube already at its place in the combined shape (real coordinates), so the **Combined** view assembles itself without anyone moving anything. The viewer centres each group's piece on its own plate, so position only matters for Combined.
- **Group numbers:** the publish script asks each group for its number (Group 1 … 8) and uploads under that number, so it matches the chip with the same number on the screen. For more or fewer groups, change `GROUPS` at the top of `WorkshopPublish.py` and open the screen with `?groups=`.
- **Colours:** the screen uses each object's colour from Rhino (object colour, or the layer colour if that isn't black). Pieces without a colour get the group's colour: 1 grey, 2 yellow, 3 green, 4 dark green, 5 red, 6 light red, 7 cyan, 8 purple.
- **Dry run:** publish from two laptops on the classroom Wi-Fi, press **Update** on the screen and check both cubes appear.

## Students: installing the Publish button

1. Save `WorkshopPublish.py` somewhere permanent (e.g. Documents).
2. In Rhino, create a toolbar button or an alias with this macro (use your own path):
   ```
   ! _-RunPythonScript "C:\Users\you\Documents\WorkshopPublish.py"
   ```
   On Mac: `! _-RunPythonScript "/Users/you/Documents/WorkshopPublish.py"`
3. Click it. The first time it asks which group you are (it remembers this in the Rhino file). After that, **Enter publishes**. Click **Group** on the command line to change the number.
4. Optional: click **PublishOnSave** on the command line to turn it **On**. Every Ctrl+S then publishes automatically. After restarting Rhino, click the button once to re-arm it.

What gets published: everything visible. Hidden objects and hidden layers are skipped, so hide anything that shouldn't be on the big screen. Blocks over 4 MB are refused with a message saying so.

## On the screen

Open your Vercel URL fullscreen (F11). Drag to orbit, scroll to zoom.

| Key | Does |
|---|---|
| **1** **2** **3** **4** | Combined / Exploded / One by one / Matrix |
| **←** **→** | Previous / next group (opens One by one) |
| **R** | Slow orbit on/off (dragging pauses it for 20 s; the matrix never orbits) |
| **C** | Colours: model colours / group colours / white model |
| **L** | Group labels |
| **F** | Fit the view |
| **U** | Update: load the newest models now (see below) |

Click a cube, or a group chip at the bottom left, to open that group in One by one. Each chip shows when the group last published; a dot marks the ones published in the last 90 seconds.

The address keeps the current view, so you can bookmark one: `…/#matrix`, `…/#exploded`, `…/#single-3`.

URL options: `?title=Studio%20Rotterdam` sets the heading, `?poll=5` the refresh interval in seconds, `?groups=8` the number of groups, `?explode=1` the starting separation (1 = each piece moves its own distance from the centre again; 0–3), `?view=matrix` the starting view.

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
- Those reads go through Vercel's cache, which can be up to a minute behind, so a new publish takes up to a minute to appear by itself. **Update** (U) skips the cache and costs 2 Blob operations per press, so pressing it a few dozen times a session is fine; don't script it.
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
