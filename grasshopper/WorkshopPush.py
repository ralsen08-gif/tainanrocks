# -*- coding: utf-8 -*-
"""
Workshop Live: push geometry from Grasshopper straight to the class screen.

SET-UP (once)
  1. Drop a Python script component on the canvas
     (Rhino 7: Maths > Script > GhPython Script; Rhino 8: Maths > Script > Python 3 Script or IronPython 2 Script).
  2. Open it and paste this whole file in, replacing what's there.
  3. Set up the inputs (zoom in on the component, use + / - and right-click a name to rename it):
       G       Item access: List Access   Type hint: GeometryBase   your cube: Breps, meshes, SubDs, extrusions
       group   Type hint: int             your group number, 1-8 (a Number Slider or Panel)
       push    Type hint: bool            connect a Button: each click publishes once
       auto    Type hint: bool            optional: a Boolean Toggle; publishes whenever G changes,
                                          at most once every 15 seconds
       colour  Type hint: Color           optional: colour of your cube on the screen
       server  Type hint: str             optional: overrides SERVER_URL below
       key     Type hint: str             optional: overrides WORKSHOP_KEY below
  4. Rename the output to: status
  5. Optional: right-click the component > "Create User Object..." so it's in your toolbar next time.

Everything in G is published together as your group's cube (as meshes, converted to metres),
replacing what your group published before, just like the Publish button in Rhino.

Works in Rhino 7 and Rhino 8 (Windows and Mac).
"""
import os
import json
import time
import System
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import Grasshopper

# ---------------------------------------------------------------------------
# Instructor: same two lines as in WorkshopPublish.py.
SERVER_URL = "https://tainanrocks.vercel.app"
WORKSHOP_KEY = "blocks-2026"
# ---------------------------------------------------------------------------

GROUPS = 8
MAX_BYTES = 4 * 1024 * 1024
AUTO_EVERY_S = 15     # auto: at most one publish per this many seconds


def inp(name, default=None):
    """An input's value, or `default` if the input doesn't exist or isn't connected."""
    value = globals().get(name, None)
    return default if value is None else value


def warn(text, error=False):
    level = Grasshopper.Kernel.GH_RuntimeMessageLevel.Error if error else Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning
    ghenv.Component.AddRuntimeMessage(level, text)


# ---------------------------------------------------------------- geometry
def as_geometry(item):
    """Grasshopper hands over geometry, wrapped geometry or Rhino object ids; return RhinoCommon geometry."""
    if item is None:
        return None
    if isinstance(item, System.Guid):
        obj = Rhino.RhinoDoc.ActiveDoc.Objects.FindId(item)
        return obj.Geometry if obj else None
    if isinstance(item, rg.Box):
        return item.ToBrep()
    if hasattr(item, "Value") and not isinstance(item, rg.GeometryBase):
        return as_geometry(item.Value)
    return item


def to_meshes(geom, mp):
    """Meshes for any surface-like geometry, else []."""
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


def collect(items):
    """All input geometry as meshes in metres. Returns (meshes, skipped count)."""
    doc = Rhino.RhinoDoc.ActiveDoc
    try:
        mp = doc.GetMeshingParameters(doc.MeshingParameterStyle)
    except Exception:
        mp = rg.MeshingParameters.Default
    to_m = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    scale = rg.Transform.Scale(rg.Point3d.Origin, to_m)
    meshes, skipped = [], 0
    for item in items or []:
        parts = [m for m in to_meshes(as_geometry(item), mp) if m is not None and m.Faces.Count > 0]
        if not parts:
            skipped += 1
            continue
        for m in parts:
            m.Transform(scale)
            m.Normals.ComputeNormals()
            m.Compact()
            meshes.append(m)
    return meshes, skipped


def fingerprint(meshes, extra):
    """Cheap signature of the geometry, so auto only publishes when something really changed."""
    out = [extra]
    for m in meshes:
        b = m.GetBoundingBox(False)
        out.append("%d/%d/%.5f,%.5f,%.5f,%.5f,%.5f,%.5f" % (m.Vertices.Count, m.Faces.Count,
                                                          b.Min.X, b.Min.Y, b.Min.Z, b.Max.X, b.Max.Y, b.Max.Z))
    return "|".join(out)


def write_3dm(meshes, colour, group):
    f = Rhino.FileIO.File3dm()
    f.Settings.ModelUnitSystem = Rhino.UnitSystem.Meters
    for m in meshes:
        attr = Rhino.DocObjects.ObjectAttributes()
        if colour is not None:
            attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            attr.ObjectColor = colour
        f.Objects.AddMesh(m, attr)
    path = os.path.join(System.IO.Path.GetTempPath(), "workshoplive_gh_group%d.3dm" % group)
    if not f.Write(path, 7):
        raise Exception("could not write the temporary file %s" % path)
    return path


# ---------------------------------------------------------------- network
def http_post(url, data, key):
    try:
        System.Net.ServicePointManager.SecurityProtocol = (
            System.Net.ServicePointManager.SecurityProtocol | System.Net.SecurityProtocolType.Tls12)
    except Exception:
        pass
    wc = System.Net.WebClient()
    wc.Headers.Add("x-workshop-key", key)
    wc.Headers.Add("Content-Type", "application/octet-stream")
    try:
        raw = wc.UploadData(url, "POST", data)
        return 200, System.Text.Encoding.UTF8.GetString(raw)
    except System.Net.WebException as ex:
        if ex.Response is None:
            raise Exception("can't reach %s (%s)" % (url, ex.Message))
        status = System.Convert.ToInt32(ex.Response.StatusCode)
        return status, System.IO.StreamReader(ex.Response.GetResponseStream()).ReadToEnd()


def publish(meshes, group, colour, server, key):
    """Returns (ok, message)."""
    if "your-project" in server.lower():
        return False, "Set SERVER_URL at the top of the script (or connect the server input)."
    path = write_3dm(meshes, colour, group)
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        return False, "Group %d's geometry is %.1f MB; the limit is 4 MB. Simplify it and push again." % (group, size / 1048576.0)
    status, body = http_post("%s/api/publish?block=%d" % (server.rstrip("/"), group), System.IO.File.ReadAllBytes(path), key)
    try:
        result = json.loads(body)
    except Exception:
        result = {"error": body[:200]}
    if status == 200 and result.get("ok"):
        return True, "Published Group %d at %s (%.2f MB)." % (group, time.strftime("%H:%M:%S"), size / 1048576.0)
    return False, "Publish failed (%s): %s" % (status, result.get("error", "unknown error"))


def run_again_in(seconds):
    """Ask Grasshopper to run this component again later (for auto's waiting time)."""
    component = ghenv.Component
    document = component.OnPingDocument()

    def again(doc):
        component.ExpireSolution(False)

    try:
        document.ScheduleSolution(int(seconds * 1000) + 200, Grasshopper.Kernel.GH_Document.GH_ScheduleDelegate(again))
    except Exception:
        pass   # then the next change (or the Push button) publishes it


# ---------------------------------------------------------------- the component
memory = sc.sticky.setdefault("workshoplive_gh_" + str(ghenv.Component.InstanceGuid),
                              {"time": 0.0, "fingerprint": None, "status": "Ready: connect geometry and press Push."})
group_number = int(inp("group", 0) or 0)
colour_value = inp("colour")
server_url = str(inp("server", SERVER_URL) or SERVER_URL)
workshop_key = str(inp("key", WORKSHOP_KEY) or WORKSHOP_KEY)
ghenv.Component.Message = "Group %d" % group_number if 1 <= group_number <= GROUPS else "no group"

meshes, skipped = collect(inp("G", []))
if skipped:
    warn("%d item(s) in G aren't surfaces, polysurfaces, meshes or SubDs and were left out." % skipped)

if not 1 <= group_number <= GROUPS:
    warn("Set group to your group number (1-%d)." % GROUPS, error=True)
    status = "Set group to your group number (1-%d)." % GROUPS
elif not meshes:
    status = "Connect your cube (Breps, meshes or SubDs) to G."
else:
    signature = fingerprint(meshes, "%d|%s" % (group_number, colour_value))
    wanted = bool(inp("push", False))
    if not wanted and inp("auto", False) and signature != memory["fingerprint"]:
        wait = AUTO_EVERY_S - (time.time() - memory["time"])
        if wait <= 0:
            wanted = True
        else:
            memory["status"] = "Changed: auto-publishing in %d s." % (int(wait) + 1)
            run_again_in(wait)
    if wanted:
        try:
            ok, message = publish(meshes, group_number, colour_value, server_url, workshop_key)
        except Exception as ex:
            ok, message = False, "Publish failed: %s" % ex
        memory["time"] = time.time()
        if ok:
            memory["fingerprint"] = signature
        memory["status"] = message
        if not ok:
            warn(message, error=True)
    status = memory["status"]
