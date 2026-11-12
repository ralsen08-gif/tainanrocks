# -*- coding: utf-8 -*-
"""
Workshop Live: publish your group's cube to the class screen.

Run it from a toolbar button or alias:
    ! _-RunPythonScript "C:\\path\\to\\WorkshopPublish.py"

First run asks which group you are (Group 1..8). The choice is saved in the
Rhino file. Then select the ONE object that is your cube: only that object is
published. Press Enter instead of selecting to publish the same object as
last time.

Your cube has to be one object: join its parts into one polysurface or mesh,
or make a block of them. Surfaces, polysurfaces, extrusions, SubDs and meshes
work; blocks are exploded into meshes when published.

Options on the command line let you change the group number or turn on
"PublishOnSave", which publishes the object you published last every time you
press Ctrl+S.

Each group publishes as its number ("1".."8"), which is the group chip with
the same number on the class screen. Geometry is converted to meters, so
files in millimetres or centimetres line up with everyone else's.

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


def saved_object(doc):
    """The object published last time from this file, if it still exists."""
    value = get_setting(doc, "object")
    if not value:
        return None
    try:
        obj = doc.Objects.FindId(System.Guid.Parse(value))
    except Exception:
        return None
    return obj if obj is not None and not obj.IsDeleted else None


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


def collect_meshes(doc, geom, xform, color, mp, out, depth=0):
    """Append (mesh, color) pairs for the geometry (blocks are exploded) to `out`."""
    if isinstance(geom, rg.InstanceReferenceGeometry):
        if depth >= MAX_DEPTH:
            return
        idef = doc.InstanceDefinitions.FindId(geom.ParentIdefId)
        if idef is None:
            return
        child_xform = xform * geom.Xform
        for child in idef.GetObjects():
            collect_meshes(doc, child.Geometry, child_xform, child.Attributes.DrawColor(doc), mp, out, depth + 1)
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
    out.append((joined, color))


def build_file(doc, obj, group):
    """Write the one selected object, as meshes in metres, to a temporary .3dm. Returns (path, meshes)."""
    to_m = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    parts = []
    collect_meshes(doc, obj.Geometry, rg.Transform.Scale(rg.Point3d.Origin, to_m),
                   obj.Attributes.DrawColor(doc), meshing_parameters(doc), parts)
    f = Rhino.FileIO.File3dm()
    f.Settings.ModelUnitSystem = Rhino.UnitSystem.Meters
    for mesh, color in parts:
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        attr.ObjectColor = color
        f.Objects.AddMesh(mesh, attr)
    path = os.path.join(System.IO.Path.GetTempPath(), "workshoplive_group%d.3dm" % group)
    if not f.Write(path, 7):
        raise Exception("could not write the temporary file %s" % path)
    return path, len(parts)


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


def publish(doc, group, obj):
    """Publish one object as the group's cube. Returns (ok, message)."""
    if "your-project" in SERVER_URL.lower():
        return False, "The instructor still needs to set SERVER_URL at the top of WorkshopPublish.py."
    Rhino.RhinoApp.WriteLine("Workshop Live: preparing Group %d..." % group)
    path, meshes = build_file(doc, obj, group)
    if meshes == 0:
        return False, ("That object can't be published: select your cube itself (a polysurface, surface, "
                       "extrusion, SubD, mesh or block), not a curve, point or text.")
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        return False, ("Group %d's cube is %.1f MB; the limit is 4 MB. Simplify very smooth surfaces "
                       "or fine detail and publish again." % (group, size / 1048576.0))

    data = System.IO.File.ReadAllBytes(path)
    url = "%s/api/publish?block=%d" % (SERVER_URL.rstrip("/"), group)
    status, body = http_send("POST", url, data)
    try:
        result = json.loads(body)
    except Exception:
        result = {"error": body[:200]}
    if status == 200 and result.get("ok"):
        set_setting(doc, "object", str(obj.Id))   # Enter and PublishOnSave reuse it
        on_screen = result.get("blocksPublished")
        extra = ", %d groups on the screen" % on_screen if on_screen else ""
        return True, "Published Group %d to the class screen (%.2f MB%s)." % (group, size / 1048576.0, extra)
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
        obj = saved_object(doc)
        if obj is None:
            Rhino.RhinoApp.WriteLine("Workshop Live: not published on save: the object you published last is gone. "
                                     "Run the script and select your cube.")
            return
        ok, msg = publish(doc, group, obj)
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


def clear_old_cube_drawing():
    """An earlier version could draw a red box (ShowCube); switch it off if it's still on in this session."""
    state = sc.sticky.get("workshoplive_cube_drawing")
    if state is not None:
        state["box"] = None


# ---------------------------------------------------------------- command
def main():
    doc = sc.doc
    clear_old_cube_drawing()
    group = saved_group(doc)
    if not group:
        group = pick_group(None)
        if not group:
            return
        set_setting(doc, "group", str(group))

    install_save_handler()
    doc.Objects.UnselectAll()   # start from nothing selected, so exactly one object gets picked
    doc.Views.Redraw()

    while True:
        last = saved_object(doc)
        auto = Rhino.Input.Custom.OptionToggle(get_setting(doc, "autopublish") == "1", "Off", "On")
        number = Rhino.Input.Custom.OptionInteger(group, 1, GROUPS)
        go = Rhino.Input.Custom.GetObject()
        go.SetCommandPrompt("Select your cube to publish as Group %d%s" % (
            group, " (Enter = the same object as last time)" if last else ""))
        go.EnablePreSelect(False, True)
        go.SubObjectSelect = False
        go.GroupSelect = False
        go.AcceptNothing(last is not None)
        opt_group = go.AddOptionInteger("Group", number)
        opt_auto = go.AddOptionToggle("PublishOnSave", auto)
        res = go.Get()   # Get (not GetMultiple): exactly one object

        if res == Rhino.Input.GetResult.Option:
            if go.OptionIndex() == opt_group:
                if number.CurrentValue != group:
                    group = number.CurrentValue
                    set_setting(doc, "group", str(group))
                    Rhino.RhinoApp.WriteLine("Workshop Live: this file now publishes as Group %d." % group)
            elif go.OptionIndex() == opt_auto:
                set_setting(doc, "autopublish", "1" if auto.CurrentValue else "0")
                Rhino.RhinoApp.WriteLine("Workshop Live: publish on save is %s." % ("on" if auto.CurrentValue else "off"))
            continue
        if res == Rhino.Input.GetResult.Nothing and last is not None:
            obj = last
            break
        if res == Rhino.Input.GetResult.Object:
            obj = go.Object(0).Object()
            break
        return  # Escape

    doc.Objects.UnselectAll()
    doc.Views.Redraw()
    try:
        ok, msg = publish(doc, group, obj)
    except Exception as ex:
        ok, msg = False, "Publish failed: %s" % ex
    Rhino.RhinoApp.WriteLine("Workshop Live: " + msg)
    if not ok:
        Rhino.UI.Dialogs.ShowMessage(msg, "Workshop Live")


if __name__ == "__main__":
    main()
