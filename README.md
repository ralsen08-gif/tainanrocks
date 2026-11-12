# Workshop Live

Each group designs one piece (a cube) in Rhino and presses **Publish**. The class screen picks up new models by itself within about a minute, or straight away when you press **Update**, and has five views; the pieces glide between them:

- **Combined**: all pieces together at their real Rhino coordinates (e.g. eight cubes forming one 2×2×2 cube)
- **Exploded**: the same, with every piece pushed away from the centre; a slider sets the separation
- **One by one**: one group's piece on its own; step through the groups with ‹ › or the arrow keys
- **Matrix**: every group's piece side by side in a grid, with empty spots for groups that haven't published
- **Interfaces**: a group's cube with the cubes it touches, pulled apart, with each shared face drawn in the gap; click a face to see in 2D where the cubes touch and where their voids connect, with the areas

Every publish is kept, so the **history bar** can step back through the session, version by version, or replay it. **Sun** (S) lights the model with the real sun for any date and time in Tainan, with long shadows, the sun's path and a compass. **Animals** (A) brings the structure to life with chibi Taiwanese wildlife.

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
   In `WorkshopPublish.py`, also describe where the cubes are in your template (in metres), because the script only publishes what lies inside the group's own cube:
   ```python
   CUBE_SIZE_M = 0.45
   CUBE_ORIGIN_M = (0.9, 0.0, 0.0)   # south-west bottom corner of the whole 2 x 2 x 2 cube (Group 1 starts at x 900, y 0, z 0 mm)
   GROUP_CELLS = {1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0),
                  5: (0, 0, 1), 6: (1, 0, 1), 7: (1, 1, 1), 8: (0, 1, 1)}
   ```
   Each cell is (x, y, z), with 0 = west / south / bottom and 1 = east / north / top. This is the workshop's order: 1–4 anticlockwise round the bottom floor from the south-west corner, and 5–8 the same on the top floor (north up):
   ```
   top floor   8 7      bottom floor   4 3
               5 6                     1 2
   ```
   Each group touches the groups on either side of it on its floor (1–2–3–4–1 and 5–6–7–8–5) and the one directly above or below it (*n* ± 4). `ONLY_INSIDE_CUBE = False` turns the filter off.

## Before the workshop

- **Template file:** give every group the same .3dm with each group's cube already at its place in the combined shape (real coordinates), so the **Combined** view assembles itself without anyone moving anything. The viewer centres each group's piece on its own plate, so position only matters for Combined.
- **Group numbers:** the publish script asks each group for its number (Group 1 … 8) and uploads under that number, so it matches the chip with the same number on the screen. For more or fewer groups, change `GROUPS` at the top of `WorkshopPublish.py` and open the screen with `?groups=`.
- **Colours:** by default each group has its own colour: 1 vermilion, 2 marigold, 3 leaf green, 4 jade, 5 blue, 6 violet, 7 rose, 8 earth brown. **C** switches to each object's own colour from Rhino (object colour, or the layer colour if that isn't black) or to a white model.
- **Logos:** put the official logo files in `public/logos/` as `mvrdv.svg` and `ncku.svg` (`.png` works too). Until they're there, the bottom left shows the names as text.
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
5. Optional: click **ShowCube** to turn it **On**. Your group's cube is drawn in red in every viewport: only what's inside it is published. Like PublishOnSave, it's remembered in the file; after restarting Rhino, run the script once to bring it back.

What gets published: every visible object that lies **completely inside your group's cube** (1 mm leeway). Anything else (hidden objects, hidden layers, sketches next to the cube, a neighbour's reference geometry, stray objects far away) is left out. The command line says how many objects were left out, and after a manual publish they're selected so you can see them. If nothing is inside your cube, the script says where it expects the cube: check the group number and that your model sits where it is in the template. Blocks over 4 MB are refused with a message saying so.

## On the screen

Open your Vercel URL and press **P** (or the Fullscreen button) for fullscreen with only the model: every control disappears and the model fills the screen. The keys keep working, so you can switch views while presenting; moving the mouse shows an Exit button, and Esc brings the controls back. Drag to orbit (all the way round, so you can look at the bottom too), scroll to zoom.

| Key | Does |
|---|---|
| **1** **2** **3** **4** **5** | Combined / Exploded / One by one / Matrix / Interfaces |
| **←** **→** | Previous / next group (opens One by one) |
| **[** **]** | Previous / next update in the history |
| **S** | Sun on/off |
| **A** | Animals on/off |
| **R** | Slow orbit on/off (dragging pauses it for 20 s; the matrix never orbits) |
| **C** | Colours: group colours / model colours / white model |
| **T** | Rock: show the cubes in stone |
| **X** | Section: cut the model with planes along X, Y and Z |
| **Esc** | Close the cube's card |
| **L** | Group labels |
| **F** | Fit the view |
| **P** | Fullscreen with only the model (Esc to come back) |
| **H** | Show or hide the history bar |
| **U** | Update: load the newest models now (see below) |

**Click a cube** for its card: size, volume, void (share of its bounding box left empty), estimated weight in concrete (2.4 t/m³), surface area, which cubes it touches and over how much area, triangle count and file size, plus buttons for One by one and Interfaces. The card also **downloads the published .3dm files**: this version, all versions of the group (zip), or every group as shown (zip; when you're looking back in the history, the versions of that moment). These are the files the Publish button sent, so meshes in metres, not the students' working files. Volume needs a closed model; otherwise the card says so. Clicking empty space or **Esc** closes it.

Clicking a group chip at the bottom left opens that group in One by one with its card. Each chip shows when the group last published; a dot marks the ones published in the last 90 seconds.

**Section** (X) cuts the model with up to three planes, one along each axis. Tick X, Y or Z, slide the plane through the model (its position is a share of what's on screen, so it works in every view), and ⇄ keeps the other side. A plane that's switched on removes the side the camera is on, so the cut faces you. Cut material shows as dark poché; coloured patches inside it are the faces of voids. Thin red lines mark the planes, and clicking skips what's cut away.

**Rock** (T) shows the cubes in stone: a sandstone-like pattern (made in the browser, no image files) about 35 cm across, tinted with the group colour, or plain stone together with the white model.

The address keeps the current view, so you can bookmark one: `…/#matrix`, `…/#exploded`, `…/#single-3`, `…/#interfaces-3`.

**History.** The bar above the group chips has a tick for every publish, in the group's colour. Drag the slider, use ‹ › or **[** **]**, or press ▶ to replay the session one update per second. Everything follows the point in time you pick, the interface drawings included; the status line says you're looking back. **● Live** returns to the newest version of every group. The × at the end of the bar (or **H**) hides it; the browser remembers that. The server keeps the last 100 versions per group.

**Sun.** Date and time sliders set the sun for Tainan (latitude 22.99°, longitude 120.21°, UTC+8); ▶ plays the day from 5:00 to 19:30. The model's +Y is taken as north. The orange arc is the sun's path that day, the grey ring the horizon.

**Animals.** Eight little residents: Formosan black bears, leopard cats (石虎), a Formosan rock macaque, a pangolin and Taiwan blue magpies. They find places to stand on the cubes (tops, and cave floors with enough headroom), hop between them, fly and perch (the magpies), turn round to look at you, and now and then say something. They ride along when the cubes move between views and move house when a cube is covered, hidden or replaced by a new version. Click one and it jumps and tells you its name. `?animals=1` starts with them on.

**Interfaces.** The 3D view shows the selected group's cube and the cubes it touches (three each in a 2×2×2 cube), pulled apart. In each gap floats a drawing of the shared face, so you can see at a glance where voids run on into the neighbour. Click a face (in 3D, or its tab in the panel; clicking a neighbouring cube moves the focus to it) to open it in the panel. The drawing is the face as seen from the neighbour, with four kinds of area:

- **grey**: both cubes solid, so the surfaces touch;
- **red hatch**: both open, so **the voids connect**;
- **one group's colour**: only that cube has material there and the other is open.

A solid line shows this cube's edges in the plane, a dashed line the neighbour's. Next to it are the areas in m² and as a share of the shared face: solid surface touching, voids connecting, each one-sided area, and how much of each cube's voids on that face open into the other's. Areas are counted on a fine raster (about 0.6 mm per pixel on a 0.45 m face). Faces count as touching when the cubes' bounding boxes sit within 3% of a cube's size of each other. **Print** prints the selected face's drawing and numbers.

URL options: `?title=Studio%20Rotterdam` sets the heading, `?poll=5` the refresh interval in seconds, `?groups=8` the number of groups, `?explode=1` the starting separation (1 = each piece moves its own distance from the centre again; 0–3), `?view=matrix` the starting view, `?colors=model` (or `white`) the starting colours, `?rock=1` starts in stone. Sun: `?sun=1` starts with the sun on, `?day=172&time=15:00` (day of the year, 1–365) the moment, `?lat=…&lon=…&tz=…&place=…` another location, `?north=30` if north in the Rhino model is turned 30° anticlockwise from +Y.

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

- Each publish uses 3 of the 2,000 monthly "advanced" Blob operations, so roughly 650 publishes a month. A 3-hour workshop with 8 groups publishing every 10 minutes uses about 450.
- The screen reads the server about 10 times a minute no matter how many browsers are open, well inside the free read allowance. Close the viewer outside class hours.
- Those reads go through Vercel's cache, which can be up to a minute behind, so a new publish takes up to a minute to appear by itself. **Update** (U) skips the cache: it lists the stored models and rebuilds the list from them, which costs 2 advanced Blob operations per press. Pressing it a few dozen times a session is fine; don't script it.
- Uploads are capped at 4 MB per group (Vercel's request limit is 4.5 MB). Massing models are usually well under 1 MB.
- Every version is kept (up to 100 per group) for the history, so storage grows with each publish: 8 groups × 100 versions × 200 KB is 160 MB. Check the storage your Vercel plan includes. Clear everything between workshops (see below).

## Troubleshooting

| Message | Fix |
|---|---|
| "Wrong workshop passcode" | `WORKSHOP_KEY` in the script doesn't match the Vercel environment variable (and redeploy after changing it). |
| "Server is missing the WORKSHOP_KEY environment variable" | Add it in Vercel and redeploy. |
| "can't reach https://…" | Check the URL in the script and the laptop's internet. |
| Viewer says "Can't reach the server" | Blob storage not connected to the project, or not redeployed after connecting. |
| A piece is in the wrong place in Combined | That group's file isn't based on the shared template coordinates. |
| A group's piece doesn't show | Publish it as meshes (or with render meshes saved). Only meshes, curves, and breps/extrusions that carry a render mesh can be drawn in the browser. |
