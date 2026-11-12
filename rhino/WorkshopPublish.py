# -*- coding: utf-8 -*-
"""
Workshop Live: publish your group's cube to the class screen.

Run it from a toolbar button or alias:
    ! _-RunPythonScript "C:\\path\\to\\WorkshopPublish.py"

First run asks which group you are (Group 1..8). The choice is saved in the
Rhino file, and after that pressing Enter publishes. Options on the command
line let you change the group number, turn on "PublishOnSave", which
publishes automatically every time you press Ctrl+S, and turn on "ShowCube",
which draws your group's cube in the viewports: only what's inside it is
published.

Each group publishes as its number ("1".."8"), which is the group chip with
the same number on the class screen.

What gets published: every visible object that lies completely inside your
group's own cube in the template (hidden objects, objects on hidden layers and
anything sticking out of your cube are left out; you're told how many, and on
a manual publish they're selected so you can see them). Surfaces,
polysurfaces, extrusions and SubDs are turned into meshes, curves into
polylines, and block instances are exploded. Geometry is converted to meters
so mixed-unit files still line up.

Works in Rhino 7 and Rhino 8 (Windows and Mac). No plug-ins required.
"""
import os
import json
import System
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

# ---------------------------------------------------------------------------
# Instructor: set these before handing the script out.
SERVER_URL = "https://tainanrocks.vercel.app"
WORKSHOP_KEY = "blocks-2026"

# Where the groups' cubes are in the template file, in metres. Only objects that lie
# completely inside the group's own cube are published.
CUBE_SIZE_M = 0.45
CUBE_ORIGIN_M = (0.9, 0.0, 0.0)   # south-west bottom corner of the whole 2 x 2 x 2 cube (= where Group 1 starts: x 900, y 0, z 0 mm)
# The cell each group fills: (x, y, z), 0 = west / south / bottom, 1 = east / north / top.
# The workshop's order: 1-4 anticlockwise round the bottom floor from the south-west corner,
# 5-8 the same on the top floor, so each group sits directly above the one 4 lower.
#     top floor     8 7        bottom floor     4 3      (north up)
#                   5 6                         1 2
GROUP_CELLS = {
    1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0),
    5: (0, 0, 1), 6: (1, 0, 1), 7: (1, 1, 1), 8: (0, 1, 1),
}
ONLY_INSIDE_CUBE = True           # False publishes everything visible, as before
INSIDE_TOLERANCE_M = 0.001        # how far something may poke out and still count as inside
# ---------------------------------------------------------------------------

GROUPS = 8          # number of groups; keep it the same as ?groups= on the class screen
SECTION = "WorkshopLive"
STICKY_HANDLER = "workshoplive_publish_on_save"
STICKY_CONDUIT = "workshoplive_cube_drawing"
MAX_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 8  # nested block definitions


# ---------------------------------------------------------------- settings
def get_setting(doc, key, default=None):
    value = doc.Strings.GetValue(SECTION, key)
    return value if value else default


def set_setting(doc, key, value):
    doc.Strings.SetString(SECTION, key, value)


def saved_group(doc):
    """The group number saved in this file, or None (also for files that still hold an old A1..D4 block)."""
    value = get_setting(doc, "group")
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= GROUPS else None


def pick_group(current):
    import rhinoscriptsyntax as rs
    names = ["Group %d" % n for n in range(1, GROUPS + 1)]
    choice = rs.ListBox(names, "Which group are you?", "Workshop Live",
                        names[current - 1] if current else None)
    return names.index(choice) + 1 if choice else None


# ---------------------------------------------------------------- the group's cube
def group_box_m(group):
    """The group's cube (in metres, with the tolerance added), or None if it has no cell."""
    cell = GROUP_CELLS.get(group)
    if cell is None:
        return None
    lo = [CUBE_ORIGIN_M[i] + cell[i] * CUBE_SIZE_M - INSIDE_TOLERANCE_M for i in range(3)]
    hi = [CUBE_ORIGIN_M[i] + (cell[i] + 1) * CUBE_SIZE_M + INSIDE_TOLERANCE_M for i in range(3)]
    return rg.BoundingBox(rg.Point3d(lo[0], lo[1], lo[2]), rg.Point3d(hi[0], hi[1], hi[2]))


def describe_box(box):
    t = INSIDE_TOLERANCE_M
    return "x %.2f-%.2f, y %.2f-%.2f, z %.2f-%.2f m" % (
        box.Min.X + t, box.Max.X - t, box.Min.Y + t, box.Max.Y - t, box.Min.Z + t, box.Max.Z - t)


def group_box_doc(doc, group):
    """The group's cube in the file's own units (without the tolerance), or None."""
    cell = GROUP_CELLS.get(group)
    if cell is None:
        return None
    from_m = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    lo = [(CUBE_ORIGIN_M[i] + cell[i] * CUBE_SIZE_M) * from_m for i in range(3)]
    hi = [(CUBE_ORIGIN_M[i] + (cell[i] + 1) * CUBE_SIZE_M) * from_m for i in range(3)]
    return rg.BoundingBox(rg.Point3d(lo[0], lo[1], lo[2]), rg.Point3d(hi[0], hi[1], hi[2]))


def cube_drawing():
    """Shared state of the ShowCube drawing. Its display hooks are added once per Rhino session
    (kept in sc.sticky), so running the script again only updates what they draw."""
    state = sc.sticky.get(STICKY_CONDUIT)
    if state is not None:
        return state
    state = {"box": None, "label": "", "doc": None}

    def mine(e):
        try:
            return e.RhinoDoc is None or e.RhinoDoc.RuntimeSerialNumber == state["doc"]
        except Exception:
            return True

    def on_bounding_box(sender, e):
        if state["box"] is not None and mine(e):
            e.IncludeBoundingBox(state["box"])

    def on_draw(sender, e):
        box = state["box"]
        if box is None or not mine(e):
            return
        red = System.Drawing.Color.FromArgb(214, 48, 39)
        e.Display.DrawBox(box, red, 2)
        e.Display.DrawDot(rg.Point3d(box.Min.X, box.Min.Y, box.Max.Z), state["label"], red, System.Drawing.Color.White)

    Rhino.Display.DisplayPipeline.CalculateBoundingBox += on_bounding_box
    Rhino.Display.DisplayPipeline.DrawForeground += on_draw   # on top of the model, so it's never hidden
    state["hooks"] = (on_bounding_box, on_draw)
    sc.sticky[STICKY_CONDUIT] = state
    return state


def show_cube(doc, group, on):
    """Draw (or stop drawing) the group's cube in this file's viewports."""
    if not on and sc.sticky.get(STICKY_CONDUIT) is None:
        return
    state = cube_drawing()
    state["box"] = group_box_doc(doc, group) if on else None
    state["label"] = "Group %d: only what's inside is published" % group
    state["doc"] = doc.RuntimeSerialNumber
    doc.Views.Redraw()


def parts_box(parts):
    """Bounding box of a list of ("mesh"|"curve", geometry, color) parts, or None."""
    box = None
    for _, geom, _ in parts:
        b = geom.GetBoundingBox(True)
        if not b.IsValid:
            continue
        box = b if box is None else rg.BoundingBox.Union(box, b)
    return box


# ---------------------------------------------------------------- geometry
def meshing_parameters(doc):
    try:
        return doc.GetMeshingParameters(doc.MeshingParameterStyle)
    except Exception:
        return rg.MeshingParameters.Default


def to_meshes(geom, mp):
    """Return a list of meshes for any surface-like geometry, else []."""
    if isinstance(geom, rg.Mesh):
        return [geom.DuplicateMesh()]
    brep = None
    if isinstance(geom, rg.Brep):
        brep = geom
    elif isinstance(geom, rg.Extrusion):
        brep = geom.ToBrep(True)
    elif isinstance(geom, rg.Surface):
        brep = rg.Brep.CreateFromSurface(geom)
    elif isinstance(geom, rg.SubD):
        try:
            m = rg.Mesh.CreateFromSubD(geom, 3)
        except Exception:
            m = rg.Mesh.CreateFromSubDControlNet(geom)
        return [m] if m else []
    if brep is None:
        return []
    meshes = rg.Mesh.CreateFromBrep(brep, mp)
    return [m for m in meshes] if meshes else []


def to_polyline(curve, tol):
    ok, pl = curve.TryGetPolyline()
    if ok:
        return rg.PolylineCurve(pl)
    try:
        return curve.ToPolyline(tol, Rhino.RhinoMath.ToRadians(3.0), 0.0, 0.0)
    except Exception:
        return None


def collect_parts(doc, geom, xform, color, mp, tol, out, depth=0):
    """Append ("mesh"|"curve", geometry, color) tuples to `out`."""
    if isinstance(geom, rg.InstanceReferenceGeometry):
        if depth >= MAX_DEPTH:
            return
        idef = doc.InstanceDefinitions.FindId(geom.ParentIdefId)
        if idef is None:
            return
        child_xform = xform * geom.Xform
        for child in idef.GetObjects():
            child_color = child.Attributes.DrawColor(doc)
            collect_parts(doc, child.Geometry, child_xform, child_color, mp, tol, out, depth + 1)
        return

    if isinstance(geom, rg.Curve):
        pl = to_polyline(geom, tol)
        if pl is not None:
            pl.Transform(xform)
            out.append(("curve", pl, color))
        return

    meshes = to_meshes(geom, mp)
    if not meshes:
        return
    joined = rg.Mesh()
    for m in meshes:
        if m is not None:
            joined.Append(m)
    if joined.Faces.Count == 0:
        return
    joined.Transform(xform)
    joined.Normals.ComputeNormals()
    joined.Compact()
    out.append(("mesh", joined, color))


def build_file(doc, group):
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.VisibleFilter = True
    settings.HiddenObjects = False
    settings.LockedObjects = True
    settings.NormalObjects = True
    settings.ReferenceObjects = False   # skip worksession / linked references
    settings.IncludeLights = False
    settings.IncludeGrips = False

    mp = meshing_parameters(doc)
    tol = doc.ModelAbsoluteTolerance * 10
    to_m = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    world = rg.Transform.Scale(rg.Point3d.Origin, to_m)

    cube = group_box_m(group) if ONLY_INSIDE_CUBE else None
    parts, outside = [], []
    for obj in doc.Objects.GetObjectList(settings):
        try:
            mine = []
            collect_parts(doc, obj.Geometry, world, obj.Attributes.DrawColor(doc), mp, tol, mine)
            if cube is not None and mine:
                b = parts_box(mine)
                if b is None or not (cube.Contains(b.Min) and cube.Contains(b.Max)):
                    outside.append(obj.Id)   # (partly) outside the group's cube: leave it out
                    continue
            parts.extend(mine)
        except Exception as ex:
            Rhino.RhinoApp.WriteLine("Workshop Live: skipped one object (%s)" % ex)

    f = Rhino.FileIO.File3dm()
    f.Settings.ModelUnitSystem = Rhino.UnitSystem.Meters
    faces = 0
    for kind, geom, color in parts:
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        attr.ObjectColor = color
        if kind == "mesh":
            faces += geom.Faces.Count
            f.Objects.AddMesh(geom, attr)
        else:
            f.Objects.AddCurve(geom, attr)

    path = os.path.join(System.IO.Path.GetTempPath(), "workshoplive_group%d.3dm" % group)
    if not f.Write(path, 7):
        raise Exception("could not write the temporary file %s" % path)
    return path, len(parts), faces, outside


def select_objects(doc, ids):
    doc.Objects.UnselectAll()
    for i in ids:
        doc.Objects.Select(i)
    doc.Views.Redraw()


# ---------------------------------------------------------------- network
def http_send(method, url, data=None):
    try:
        System.Net.ServicePointManager.SecurityProtocol = (
            System.Net.ServicePointManager.SecurityProtocol | System.Net.SecurityProtocolType.Tls12)
    except Exception:
        pass
    wc = System.Net.WebClient()
    wc.Headers.Add("x-workshop-key", WORKSHOP_KEY)
    wc.Headers.Add("Content-Type", "application/octet-stream")
    try:
        if data is None:
            data = System.Array.CreateInstance(System.Byte, 0)
        raw = wc.UploadData(url, method, data)
        return 200, System.Text.Encoding.UTF8.GetString(raw)
    except System.Net.WebException as ex:
        if ex.Response is None:
            raise Exception("can't reach %s (%s)" % (SERVER_URL, ex.Message))
        status = System.Convert.ToInt32(ex.Response.StatusCode)
        reader = System.IO.StreamReader(ex.Response.GetResponseStream())
        return status, reader.ReadToEnd()


def publish(doc, group, quiet=False):
    """Returns (ok, message)."""
    if "your-project" in SERVER_URL.lower():
        return False, "The instructor still needs to set SERVER_URL at the top of WorkshopPublish.py."
    if ONLY_INSIDE_CUBE and group_box_m(group) is None:
        return False, "Group %d has no place in GROUP_CELLS at the top of WorkshopPublish.py; ask the instructor." % group
    Rhino.RhinoApp.WriteLine("Workshop Live: preparing Group %d..." % group)
    path, count, faces, outside = build_file(doc, group)
    if outside and not quiet:
        select_objects(doc, outside)   # show the student what was left out
    if count == 0:
        if outside:
            return False, ("Nothing of yours is inside Group %d's cube (%s). %d visible object(s) are outside it%s. "
                           "Check that you picked the right group and that your model sits where it is in the template."
                           % (group, describe_box(group_box_m(group)), len(outside), "" if quiet else " (now selected)"))
        return False, "Nothing to publish: no visible geometry in this file."
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        return False, ("Group %d's model is %.1f MB; the limit is 4 MB. Hide detail you don't need on the "
                       "class screen (or simplify very smooth surfaces) and publish again." % (group, size / 1048576.0))

    data = System.IO.File.ReadAllBytes(path)
    url = "%s/api/publish?block=%d" % (SERVER_URL.rstrip("/"), group)
    status, body = http_send("POST", url, data)
    try:
        result = json.loads(body)
    except Exception:
        result = {"error": body[:200]}
    if status == 200 and result.get("ok"):
        on_screen = result.get("blocksPublished")
        extra = ", %d groups on the screen" % on_screen if on_screen else ""
        left = ""
        if outside:
            left = " Left out %d object(s) outside your cube%s." % (len(outside), "" if quiet else " (now selected)")
        return True, "Published Group %d to the class screen (%d objects, %.1f MB%s).%s" % (
            group, count, size / 1048576.0, extra, left)
    return False, "Publish failed (%s): %s" % (status, result.get("error", "unknown error"))


# ---------------------------------------------------------------- publish on save
def on_end_save(sender, e):
    try:
        if getattr(e, "ExportSelected", False) or not getattr(e, "Success", True):
            return
        doc = e.Document
        if doc is None or get_setting(doc, "autopublish") != "1":
            return
        group = saved_group(doc)
        if not group:
            return
        ok, msg = publish(doc, group, quiet=True)
        Rhino.RhinoApp.WriteLine("Workshop Live: " + msg)
    except Exception as ex:
        Rhino.RhinoApp.WriteLine("Workshop Live: publish on save failed (%s)" % ex)


def install_save_handler():
    old = sc.sticky.get(STICKY_HANDLER)
    if old is not None:
        try:
            Rhino.RhinoDoc.EndSaveDocument -= old
        except Exception:
            pass
    Rhino.RhinoDoc.EndSaveDocument += on_end_save
    sc.sticky[STICKY_HANDLER] = on_end_save


# ---------------------------------------------------------------- command
def main():
    doc = sc.doc
    group = saved_group(doc)
    if not group:
        group = pick_group(None)
        if not group:
            return
        set_setting(doc, "group", str(group))

    install_save_handler()
    show_cube(doc, group, get_setting(doc, "showcube") == "1")   # re-arm after a Rhino restart

    while True:
        auto = Rhino.Input.Custom.OptionToggle(get_setting(doc, "autopublish") == "1", "Off", "On")
        show = Rhino.Input.Custom.OptionToggle(get_setting(doc, "showcube") == "1", "Off", "On")
        number = Rhino.Input.Custom.OptionInteger(group, 1, GROUPS)
        go = Rhino.Input.Custom.GetOption()
        go.SetCommandPrompt("Press Enter to publish Group %d" % group)
        go.AcceptNothing(True)
        opt_group = go.AddOptionInteger("Group", number)
        opt_auto = go.AddOptionToggle("PublishOnSave", auto)
        opt_show = go.AddOptionToggle("ShowCube", show)
        res = go.Get()

        if res == Rhino.Input.GetResult.Option:
            if go.OptionIndex() == opt_group:
                if number.CurrentValue != group:
                    group = number.CurrentValue
                    set_setting(doc, "group", str(group))
                    Rhino.RhinoApp.WriteLine("Workshop Live: this file now publishes as Group %d." % group)
                    show_cube(doc, group, get_setting(doc, "showcube") == "1")
            elif go.OptionIndex() == opt_auto:
                set_setting(doc, "autopublish", "1" if auto.CurrentValue else "0")
                Rhino.RhinoApp.WriteLine("Workshop Live: publish on save is %s." % ("on" if auto.CurrentValue else "off"))
            elif go.OptionIndex() == opt_show:
                set_setting(doc, "showcube", "1" if show.CurrentValue else "0")
                show_cube(doc, group, show.CurrentValue)
                box = group_box_m(group)
                Rhino.RhinoApp.WriteLine("Workshop Live: %s Group %d's cube%s." % (
                    "showing" if show.CurrentValue else "no longer showing", group,
                    " (%s)" % describe_box(box) if (show.CurrentValue and box) else ""))
            continue

        if res != Rhino.Input.GetResult.Nothing:
            return  # Escape
        break

    try:
        ok, msg = publish(doc, group)
    except Exception as ex:
        ok, msg = False, "Publish failed: %s" % ex
    Rhino.RhinoApp.WriteLine("Workshop Live: " + msg)
    if not ok:
        Rhino.UI.Dialogs.ShowMessage(msg, "Workshop Live")


if __name__ == "__main__":
    main()
