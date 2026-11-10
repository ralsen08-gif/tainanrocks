# -*- coding: utf-8 -*-
"""
Workshop Live: publish your group's cube to the class screen.

Run it from a toolbar button or alias:
    ! _-RunPythonScript "C:\\path\\to\\WorkshopPublish.py"

First run asks which group you are (Group 1..8). The choice is saved in the
Rhino file, and after that pressing Enter publishes. Options on the command
line let you change the group number or turn on "PublishOnSave", which
publishes automatically every time you press Ctrl+S.

Each group publishes as its number ("1".."8"), which is the group chip with
the same number on the class screen.

What gets published: every visible object (hidden objects and objects on
hidden layers are skipped). Surfaces, polysurfaces, extrusions and SubDs are
turned into meshes, curves into polylines, and block instances are exploded.
Geometry is converted to meters so mixed-unit files still line up.

Works in Rhino 7 and Rhino 8 (Windows and Mac). No plug-ins required.
"""
import os
import json
import System
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

# ---------------------------------------------------------------------------
# Instructor: set these two lines before handing the script out.
SERVER_URL = "https://tainanrocks.vercel.app"
WORKSHOP_KEY = "blocks-2026"
# ---------------------------------------------------------------------------

GROUPS = 8          # number of groups; keep it the same as ?groups= on the class screen
SECTION = "WorkshopLive"
STICKY_HANDLER = "workshoplive_publish_on_save"
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

    parts = []
    for obj in doc.Objects.GetObjectList(settings):
        try:
            collect_parts(doc, obj.Geometry, world, obj.Attributes.DrawColor(doc), mp, tol, parts)
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
    return path, len(parts), faces


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
    Rhino.RhinoApp.WriteLine("Workshop Live: preparing Group %d..." % group)
    path, count, faces = build_file(doc, group)
    if count == 0:
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
        return True, "Published Group %d to the class screen (%d objects, %.1f MB%s)." % (
            group, count, size / 1048576.0, extra)
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

    while True:
        auto = Rhino.Input.Custom.OptionToggle(get_setting(doc, "autopublish") == "1", "Off", "On")
        number = Rhino.Input.Custom.OptionInteger(group, 1, GROUPS)
        go = Rhino.Input.Custom.GetOption()
        go.SetCommandPrompt("Press Enter to publish Group %d" % group)
        go.AcceptNothing(True)
        opt_group = go.AddOptionInteger("Group", number)
        go.AddOptionToggle("PublishOnSave", auto)
        res = go.Get()

        if res == Rhino.Input.GetResult.Option:
            if go.OptionIndex() == opt_group:
                if number.CurrentValue != group:
                    group = number.CurrentValue
                    set_setting(doc, "group", str(group))
                    Rhino.RhinoApp.WriteLine("Workshop Live: this file now publishes as Group %d." % group)
            else:
                set_setting(doc, "autopublish", "1" if auto.CurrentValue else "0")
                Rhino.RhinoApp.WriteLine("Workshop Live: publish on save is %s." % ("on" if auto.CurrentValue else "off"))
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
