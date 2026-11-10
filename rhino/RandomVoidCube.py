# -*- coding: utf-8 -*-
"""
Random void cube: a 0.45 x 0.45 x 0.45 m cube with random organic voids,
made as one closed polysurface.

Run it from a toolbar button or alias:
    ! _-RunPythonScript "C:\\path\\to\\RandomVoidCube.py"
or open it in the script editor (EditPythonScript / ScriptEditor) and press Run.

The command line asks for the cube's corner point (Enter = 0,0,0) and has options:
    VoidPercent  how much of the cube becomes void (default 25)
    VoidSize     typical width of a cave in cm (default 12)
    Seed         0 = a new random cube every time; any other number gives the same cube again

Each void is a "cave": a short wandering chain of overlapping, slightly squashed bubbles,
subtracted from the cube with a Boolean difference. Caves are added until the void
percentage is reached. Rules that keep it a usable workshop piece:
  - the eight corners stay solid, so the outer size stays exactly 0.45 m and the cube
    still sits flush against its neighbours;
  - a cave is skipped if it would split the cube into loose pieces or the Boolean fails.

Works in Rhino 7 and Rhino 8 (Windows and Mac). Sizes are converted to the file's units.
"""
import math
import random
import System
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

SIZE_M = 0.45
CORNER_MARGIN = 0.12      # keep this fraction of the cube's size clear around each corner
MAX_CAVES = 80            # attempts before giving up on reaching the void percentage
STICKY = "random_void_cube_organic"


def brep_list(items):
    lst = System.Collections.Generic.List[rg.Brep]()
    for b in items:
        lst.Add(b)
    return lst


def random_unit(rng):
    z = rng.uniform(-1.0, 1.0)
    t = rng.uniform(0.0, 2.0 * math.pi)
    s = math.sqrt(max(0.0, 1.0 - z * z))
    return rg.Vector3d(s * math.cos(t), s * math.sin(t), z)


def bubble(center, radius, rng):
    """A sphere squashed differently along three random axes: an ellipsoid, as a closed Brep."""
    surface = rg.Sphere(center, radius).ToNurbsSurface()
    plane = rg.Plane(center, random_unit(rng))
    stretch = [rng.uniform(0.75, 1.3) for _ in range(3)]
    surface.Transform(rg.Transform.Scale(plane, stretch[0], stretch[1], stretch[2]))
    return rg.Brep.CreateFromSurface(surface), radius * max(stretch)


def cave(rng, origin, size, radius, corners):
    """A chain of 2-6 overlapping bubbles wandering through the cube. Returns a list of Breps."""
    margin = size * CORNER_MARGIN
    lo, hi = 0.05 * size, 0.95 * size
    p = rg.Point3d(origin.X + rng.uniform(lo, hi), origin.Y + rng.uniform(lo, hi), origin.Z + rng.uniform(lo, hi))
    direction = random_unit(rng)
    parts = []
    for _ in range(rng.randint(2, 6)):
        r = radius * rng.uniform(0.6, 1.35)
        b, reach = bubble(p, r, rng)
        if b is None or any(p.DistanceTo(c) < reach + margin for c in corners):
            break   # this bubble would eat into a corner: end the cave here
        parts.append(b)
        # wander on: turn a little, and step so the next bubble overlaps this one
        direction = direction + random_unit(rng) * 0.8
        direction.Unitize()
        p = p + direction * (0.55 * (r + radius))
        p = rg.Point3d(min(max(p.X, origin.X + lo), origin.X + hi),
                       min(max(p.Y, origin.Y + lo), origin.Y + hi),
                       min(max(p.Z, origin.Z + lo), origin.Z + hi))
    return parts


def volume(brep):
    props = rg.VolumeMassProperties.Compute(brep)
    return props.Volume if props else None


def carve(origin, size, void_percent, radius, rng, tol):
    """Returns (brep, void fraction, number of caves)."""
    box = rg.Box(rg.Plane(origin, rg.Vector3d.XAxis, rg.Vector3d.YAxis),
                 rg.Interval(0, size), rg.Interval(0, size), rg.Interval(0, size)).ToBrep()
    corners = [origin + rg.Vector3d(i * size, j * size, k * size) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    full = size ** 3
    goal = full * void_percent / 100.0
    current, current_volume, caves = box, full, 0

    for _ in range(MAX_CAVES):
        if full - current_volume >= goal * 0.97:
            break
        parts = cave(rng, origin, size, radius, corners)
        if not parts:
            continue
        cutters = rg.Brep.CreateBooleanUnion(brep_list(parts), tol) if len(parts) > 1 else parts
        if not cutters:
            cutters = parts
        result, ok = current, True
        for cutter in cutters:
            out = rg.Brep.CreateBooleanDifference(result, cutter, tol)
            if out is None:
                continue                      # this bubble missed or the Boolean failed: skip it
            if len(out) != 1 or not out[0].IsSolid:
                ok = False                    # would split the cube or leave it open
                break
            result = out[0]
        if not ok or result is current:
            continue
        v = volume(result)
        if v is None or v >= current_volume - full * 1e-6:
            continue
        if full - v > goal * 1.08 + full * 0.01:
            continue                          # overshoots the void percentage: try a smaller cave
        current, current_volume, caves = result, v, caves + 1

    return current, (full - current_volume) / full, caves


def main():
    doc = sc.doc
    saved = sc.sticky.get(STICKY, (25.0, 12.0, 0))
    opt_void = Rhino.Input.Custom.OptionDouble(saved[0], 0.0, 60.0)
    opt_size = Rhino.Input.Custom.OptionDouble(saved[1], 2.0, 30.0)
    opt_seed = Rhino.Input.Custom.OptionInteger(saved[2], 0, 999999)

    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt("Corner of the 0.45 m cube (Enter for 0,0,0)")
    gp.AcceptNothing(True)
    gp.AddOptionDouble("VoidPercent", opt_void)
    gp.AddOptionDouble("VoidSize", opt_size)
    gp.AddOptionInteger("Seed", opt_seed)
    while True:
        res = gp.Get()
        if res == Rhino.Input.GetResult.Option:
            continue
        if res == Rhino.Input.GetResult.Point:
            origin = gp.Point()
            break
        if res == Rhino.Input.GetResult.Nothing:
            origin = rg.Point3d.Origin
            break
        return  # Escape

    void_percent, void_cm, seed = opt_void.CurrentValue, opt_size.CurrentValue, opt_seed.CurrentValue
    sc.sticky[STICKY] = (void_percent, void_cm, seed)
    if seed == 0:
        seed = random.randint(1, 999999)

    to_doc = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    size = SIZE_M * to_doc
    radius = void_cm / 200.0 * to_doc   # VoidSize is a width; bubbles are made from a radius
    tol = doc.ModelAbsoluteTolerance

    Rhino.RhinoApp.WriteLine("Random void cube: carving (a few seconds)...")
    brep, achieved, caves = carve(origin, size, void_percent, radius, random.Random(seed), tol)
    brep.MergeCoplanarFaces(tol)

    attrs = doc.CreateDefaultAttributes()
    attrs.Name = "Void cube %d%% void, seed %d" % (round(achieved * 100), seed)
    obj_id = doc.Objects.AddBrep(brep, attrs)
    doc.Objects.UnselectAll()
    doc.Objects.Select(obj_id)
    doc.Views.Redraw()

    note = "" if achieved * 100 >= void_percent * 0.9 else " (fewer voids fit than asked; try a smaller VoidSize)"
    Rhino.RhinoApp.WriteLine(
        "Random void cube: 0.45 m, %d caves, %d%% void%s, seed %d. Run again with Seed=%d for the same cube."
        % (caves, round(achieved * 100), note, seed, seed))


if __name__ == "__main__":
    main()
