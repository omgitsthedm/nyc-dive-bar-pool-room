"""Shared 9-foot playfield geometry for rendering and pooltool playback.

The JSON is exported from the local pooltool 0.6.0 9-foot table configured
from the WPA dimensions.  Blender consumes the exact same straight cushions,
rounded jaw transitions, angled facings, and pocket centres that the solver
uses.  This module is intentionally Blender-free so the contract can also be
audited with normal Python.
"""
from __future__ import annotations

import hashlib
import json
import math
import os


HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(ROOT, "assets", "data", "table_wpa_geometry.json")

POCKET_NAMES = {
    "lb": "corner_SW",
    "rb": "corner_SE",
    "lt": "corner_NW",
    "rt": "corner_NE",
    "lc": "side_W",
    "rc": "side_E",
}

POCKET_ORDER = ("lb", "lc", "lt", "rb", "rc", "rt")
EXPECTED_CUT_ANGLES_DEG = {"corner": 142.0, "side": 104.0}
WPA_MOUTH_RANGES_M = {
    "corner": (4.5 * 0.0254, 4.625 * 0.0254),
    "side": (5.0 * 0.0254, 5.125 * 0.0254),
}

_POINT_TOLERANCE_M = 1e-7
_ARC_MATCH_TOLERANCE_M = 1e-6


def _xy(point):
    return (float(point[0]), float(point[1]))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, scalar):
    return (a[0] * scalar, a[1] * scalar)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _length(v):
    return math.hypot(v[0], v[1])


def _unit(v):
    length = _length(v)
    if length <= 1e-12:
        raise ValueError("zero-length geometry vector")
    return (v[0] / length, v[1] / length)


def distance(a, b):
    return _length(_sub(a, b))


def _feature_key(value):
    """Natural, deterministic order for pooltool IDs such as ``10t``."""
    text = str(value)
    index = 0
    while index < len(text) and text[index].isdigit():
        index += 1
    number = int(text[:index]) if index else math.inf
    return (number, text[index:], text)


def _clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


def _signed_area(points):
    return 0.5 * sum(
        _cross(points[index], points[(index + 1) % len(points)])
        for index in range(len(points))
    )


def _polygon_centroid(points):
    twice_area = 2.0 * _signed_area(points)
    if abs(twice_area) <= 1e-14:
        raise ValueError("degenerate pocket outline")
    scale = 1.0 / (3.0 * twice_area)
    x = y = 0.0
    for index, point in enumerate(points):
        other = points[(index + 1) % len(points)]
        cross = _cross(point, other)
        x += (point[0] + other[0]) * cross
        y += (point[1] + other[1]) * cross
    return (x * scale, y * scale)


def _dedupe_consecutive(points, tolerance=_POINT_TOLERANCE_M):
    result = []
    for point in points:
        if not result or distance(point, result[-1]) > tolerance:
            result.append(point)
    if len(result) > 1 and distance(result[0], result[-1]) <= tolerance:
        result.pop()
    return result


def _canonical_polygon(points):
    """Return a CCW polygon with a stable lexicographic first vertex."""
    result = _dedupe_consecutive(points)
    if len(result) < 3:
        raise ValueError("pocket outline has fewer than three unique points")
    if _signed_area(result) < 0.0:
        result.reverse()
    start = min(range(len(result)), key=lambda index: (
        round(result[index][0], 12), round(result[index][1], 12), index))
    return result[start:] + result[:start]


def _line_intersection(first, second):
    """Intersection of two infinite lines represented by linear rows."""
    p = first["p1_pool"]
    r = _sub(first["p2_pool"], p)
    q = second["p1_pool"]
    s = _sub(second["p2_pool"], q)
    denominator = _cross(r, s)
    if abs(denominator) <= 1e-12:
        raise ValueError("parallel jaw and main cushion")
    t = _cross(_sub(q, p), s) / denominator
    return _add(p, _mul(r, t))


def _segment_circle_intersection(start, end, center, radius):
    """Unique crossing of a jaw segment and its pocket capture circle."""
    vector = _sub(end, start)
    offset = _sub(start, center)
    a = _dot(vector, vector)
    b = 2.0 * _dot(offset, vector)
    c = _dot(offset, offset) - radius * radius
    discriminant = b * b - 4.0 * a * c
    if discriminant < -1e-12:
        raise ValueError("jaw does not intersect its pocket circle")
    discriminant = max(0.0, discriminant)
    roots = [(-b - math.sqrt(discriminant)) / (2.0 * a),
             (-b + math.sqrt(discriminant)) / (2.0 * a)]
    valid = sorted(root for root in roots
                   if -_POINT_TOLERANCE_M <= root <=
                   1.0 + _POINT_TOLERANCE_M)
    unique = []
    for root in valid:
        root = _clamp(root, 0.0, 1.0)
        if not unique or abs(root - unique[-1]) > 1e-9:
            unique.append(root)
    if len(unique) != 1:
        raise ValueError("jaw must cross its pocket circle exactly once")
    return _add(start, _mul(vector, unique[0]))


def load(path=DATA_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    required = {"w", "l", "bed", "ball_R", "nose", "linear",
                "circular", "pockets"}
    missing = required - set(data)
    if missing:
        raise ValueError("incomplete pool geometry contract: " +
                         ", ".join(sorted(missing)))
    if not all(isinstance(data[key], dict)
               for key in ("linear", "circular", "pockets")):
        raise ValueError("pool geometry features must be JSON objects")
    if len(data["linear"]) != 18 or len(data["circular"]) != 12 or \
            len(data["pockets"]) != 6:
        raise ValueError("unexpected 9-foot geometry feature count")
    if set(data["pockets"]) != set(POCKET_ORDER):
        raise ValueError("unexpected pocket IDs")
    scalars = ("w", "l", "bed", "ball_R", "nose")
    if any(not math.isfinite(float(data[key])) for key in scalars):
        raise ValueError("non-finite pool geometry scalar")
    if any(float(data[key]) <= 0.0 for key in scalars):
        raise ValueError("pool geometry scalars must be positive")
    return data


def file_sha256(path=DATA_PATH):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def centered(data, point):
    """Pooltool bed coordinates -> playfield-centred XY coordinates."""
    return (float(point[0]) - float(data["w"]) / 2.0,
            float(point[1]) - float(data["l"]) / 2.0)


def pocket_rows(data=None):
    if data is None:
        data = load()
    result = []
    unknown = set(data["pockets"]) - set(POCKET_ORDER)
    if unknown:
        raise ValueError("unknown pocket IDs: " + ", ".join(sorted(unknown)))
    for key in POCKET_ORDER:
        if key not in data["pockets"]:
            raise ValueError("missing pocket ID: " + key)
        row = data["pockets"][key]
        result.append({
            "id": key,
            "name": POCKET_NAMES[key],
            "kind": "side" if key in ("lc", "rc") else "corner",
            "center_pool": _xy(row["center"]),
            "center": centered(data, row["center"]),
            "radius": float(row["radius"]),
            "depth": float(row.get("depth", 0.08)),
        })
    return result


def nearest_pocket(data, point):
    return min(pocket_rows(data), key=lambda row: distance(
        point, row["center_pool"]))


def linear_rows(data=None):
    """Return the six main rails plus the twelve angled jaw segments."""
    if data is None:
        data = load()
    table_center = (float(data["w"]) / 2.0, float(data["l"]) / 2.0)
    boundary_x = (0.0, float(data["w"]))
    boundary_y = (0.0, float(data["l"]))
    result = []
    for key in sorted(data["linear"], key=_feature_key):
        seg = data["linear"][key]
        p1_pool, p2_pool = _xy(seg["p1"]), _xy(seg["p2"])
        vector = _sub(p2_pool, p1_pool)
        seg_len = _length(vector)
        tangent = _unit(vector)
        normal = (-tangent[1], tangent[0])
        mid = _mul(_add(p1_pool, p2_pool), 0.5)
        vertical_main = (abs(p1_pool[0] - p2_pool[0]) <=
                         _POINT_TOLERANCE_M and
                         any(abs(p1_pool[0] - edge) <=
                             _POINT_TOLERANCE_M for edge in boundary_x))
        horizontal_main = (abs(p1_pool[1] - p2_pool[1]) <=
                           _POINT_TOLERANCE_M and
                           any(abs(p1_pool[1] - edge) <=
                               _POINT_TOLERANCE_M for edge in boundary_y))
        kind = "main" if vertical_main or horizontal_main else "jaw"
        pocket = nearest_pocket(data, mid) if kind == "jaw" else None
        target = _sub(pocket["center_pool"], mid) if pocket else \
            _sub(table_center, mid)
        if _dot(target, normal) < 0.0:
            normal = (-normal[0], -normal[1])
        result.append({
            "id": str(key),
            "kind": kind,
            "pocket": pocket,
            "p1_pool": p1_pool,
            "p2_pool": p2_pool,
            "p1": centered(data, p1_pool),
            "p2": centered(data, p2_pool),
            "length": seg_len,
            "tangent": tangent,
            "normal": normal,
        })
    return result


def _arc_connections(data, lines=None):
    """Match every transition arc to exactly one main and one jaw endpoint."""
    lines = lines if lines is not None else linear_rows(data)
    result = []
    for key in sorted(data["circular"], key=_feature_key):
        seg = data["circular"][key]
        center_pool = _xy(seg["center"])
        radius = float(seg["radius"])
        if not math.isfinite(radius) or radius <= 0.0:
            raise ValueError("arc %s has an invalid radius" % key)
        matches = []
        for line in lines:
            for endpoint in ("p1_pool", "p2_pool"):
                point = line[endpoint]
                error = abs(distance(point, center_pool) - radius)
                if error <= _ARC_MATCH_TOLERANCE_M:
                    matches.append({
                        "line": line,
                        "endpoint": endpoint,
                        "point": point,
                        "error": error,
                    })
        main = [row for row in matches if row["line"]["kind"] == "main"]
        jaw = [row for row in matches if row["line"]["kind"] == "jaw"]
        if len(main) != 1 or len(jaw) != 1 or len(matches) != 2:
            raise ValueError(
                "arc %s must join exactly one main and one jaw endpoint" % key)
        result.append({
            "id": str(key),
            "center_pool": center_pool,
            "radius": radius,
            "main": main[0],
            "jaw": jaw[0],
        })
    return result


def _sample_transition_arc(data, connection, steps):
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
        raise ValueError("arc steps must be a positive integer")
    center_pool = connection["center_pool"]
    start = connection["main"]["point"]
    end = connection["jaw"]["point"]
    start_angle = math.atan2(start[1] - center_pool[1],
                             start[0] - center_pool[0])
    end_angle = math.atan2(end[1] - center_pool[1],
                           end[0] - center_pool[0])
    sweep = (end_angle - start_angle + math.pi) % (2.0 * math.pi) - math.pi
    if abs(sweep) <= 1e-12:
        raise ValueError("arc %s has coincident endpoints" % connection["id"])

    start_radial = _unit(_sub(start, center_pool))
    end_radial = _unit(_sub(end, center_pool))
    start_alignment = _dot(start_radial,
                           connection["main"]["line"]["normal"])
    end_alignment = _dot(end_radial,
                         connection["jaw"]["line"]["normal"])
    if start_alignment * end_alignment <= 0.0:
        raise ValueError("arc %s has inconsistent endpoint normals" %
                         connection["id"])
    normal_sign = 1.0 if start_alignment + end_alignment >= 0.0 else -1.0

    path, normals = [], []
    for index in range(steps + 1):
        angle = start_angle + sweep * index / steps
        radial = (math.cos(angle), math.sin(angle))
        point = _add(center_pool,
                     _mul(radial, connection["radius"]))
        path.append(centered(data, point))
        normals.append(_mul(radial, normal_sign))
    # Preserve the source endpoints exactly instead of returning trigonometric
    # reconstructions that differ by a few floating-point ulps.
    path[0] = centered(data, start)
    path[-1] = centered(data, end)
    return path, normals, math.degrees(sweep)


def arc_rows(data=None, steps=10):
    """Return main-to-jaw nose transitions with play-side normals."""
    if data is None:
        data = load()
    lines = linear_rows(data)
    result = []
    for connection in _arc_connections(data, lines):
        path, normals, sweep = _sample_transition_arc(
            data, connection, steps)
        result.append({
            "id": connection["id"],
            "center": centered(data, connection["center_pool"]),
            "radius": connection["radius"],
            "path": path,
            "normals": normals,
            "sweep_deg": sweep,
            "main_id": connection["main"]["line"]["id"],
            "jaw_id": connection["jaw"]["line"]["id"],
            "profile_width": min(0.0508,
                                 connection["radius"] * 0.72),
        })
    return result


def _sample_outboard_arc(center, start, end, table_center, steps):
    """Sample the pocket-circle route farthest from the playing surface."""
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 2:
        raise ValueError("pocket arc steps must be an integer of at least two")
    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    ccw = (end_angle - start_angle) % (2.0 * math.pi)
    candidates = (ccw, ccw - 2.0 * math.pi)
    inward = _unit(_sub(table_center, center))

    def score(sweep):
        middle = start_angle + sweep / 2.0
        radial = (math.cos(middle), math.sin(middle))
        return (_dot(radial, inward), -abs(sweep), sweep)

    sweep = min(candidates, key=score)
    radius = distance(start, center)
    return [
        _add(center, _mul((math.cos(start_angle + sweep * index / steps),
                           math.sin(start_angle + sweep * index / steps)),
                          radius))
        for index in range(steps + 1)
    ]


def pocket_outline_details(data, pocket, arc_steps=8, pocket_steps=24):
    """Return a canonical pocket outline plus its semantic mouth edge.

    Each side follows the main-to-jaw transition, the jaw up to its capture
    circle, and then the outboard portion of that circle.  This preserves the
    JSON topology; polar-sorting unrelated endpoints can silently cross a
    concave pocket or omit its capture opening.  The canonical polygon is
    lexicographically rotated, so callers must use the returned mouth-edge
    index rather than assuming that the mouth is the closing edge.
    """
    lines = linear_rows(data)
    connections = [
        row for row in _arc_connections(data, lines)
        if row["jaw"]["line"]["pocket"]["id"] == pocket["id"]
    ]
    if len(connections) != 2:
        raise ValueError("pocket %s must own two transition arcs" %
                         pocket["id"])

    branches = []
    intersections = []
    for connection in connections:
        path, _, _ = _sample_transition_arc(data, connection, arc_steps)
        jaw = connection["jaw"]["line"]
        near = connection["jaw"]["point"]
        if distance(near, jaw["p1_pool"]) <= _POINT_TOLERANCE_M:
            far = jaw["p2_pool"]
        else:
            far = jaw["p1_pool"]
        crossing = _segment_circle_intersection(
            near, far, pocket["center_pool"], pocket["radius"])
        branches.append(path + [centered(data, crossing)])
        intersections.append(crossing)

    table_center = (float(data["w"]) / 2.0, float(data["l"]) / 2.0)
    capture_arc = _sample_outboard_arc(
        pocket["center_pool"], intersections[0], intersections[1],
        table_center, pocket_steps)
    capture_arc = [centered(data, point) for point in capture_arc]
    mouth_points = (branches[0][0], branches[1][0])
    points = (branches[0] + capture_arc[1:-1] +
              list(reversed(branches[1])))
    points = _canonical_polygon(points)
    centroid = _polygon_centroid(points)
    mouth_edges = []
    for index, point in enumerate(points):
        other = points[(index + 1) % len(points)]
        direct = (distance(point, mouth_points[0]) <= _POINT_TOLERANCE_M and
                  distance(other, mouth_points[1]) <= _POINT_TOLERANCE_M)
        reverse = (distance(point, mouth_points[1]) <= _POINT_TOLERANCE_M and
                   distance(other, mouth_points[0]) <= _POINT_TOLERANCE_M)
        if direct or reverse:
            mouth_edges.append(index)
    if len(mouth_edges) != 1:
        raise ValueError("pocket %s must have one semantic mouth edge" %
                         pocket["id"])
    return points, centroid, mouth_edges[0]


def pocket_outline(data, pocket, arc_steps=8, pocket_steps=24):
    """Return the canonical simple CCW outline and polygon centroid."""
    points, centroid, _mouth_edge = pocket_outline_details(
        data, pocket, arc_steps=arc_steps, pocket_steps=pocket_steps)
    return points, centroid


def pocket_shelf_cut_details(data, pocket, shelf,
                             arc_steps=8, pocket_steps=24):
    """Return the below-bed cut loop after preserving the WPA shelf.

    The cushion contact outline and the slate cut are different pieces of
    geometry.  ``pocket_outline_details`` describes the rail/jaw opening. The
    slate must remain at bed height from the theoretical sharp mouth line to
    the specified shelf depth, then drop.  Clip the outboard portion of the
    canonical pocket outline against that shelf line without moving any rail,
    jaw, fillet, or capture-circle source geometry.
    """
    shelf = float(shelf)
    if not math.isfinite(shelf) or shelf < 0.0:
        raise ValueError("pocket shelf must be a finite non-negative length")
    outline, _centroid, _mouth_edge = pocket_outline_details(
        data, pocket, arc_steps=arc_steps, pocket_steps=pocket_steps)
    metric = pocket_metrics(data)[pocket["name"]]
    first, second = metric["lip_points"]
    mouth_mid = _mul(_add(first, second), 0.5)
    outward = _unit(_sub(pocket["center"], mouth_mid))
    drop_mid = _add(mouth_mid, _mul(outward, shelf))
    if not _point_in_polygon(drop_mid, outline):
        raise ValueError("pocket shelf drop lies outside the capture outline")

    def signed(point):
        return _dot(_sub(point, drop_mid), outward)

    clipped = []
    previous = outline[-1]
    previous_distance = signed(previous)
    previous_inside = previous_distance >= -_POINT_TOLERANCE_M
    for current in outline:
        current_distance = signed(current)
        current_inside = current_distance >= -_POINT_TOLERANCE_M
        if current_inside != previous_inside:
            denominator = previous_distance - current_distance
            if abs(denominator) <= 1e-14:
                raise ValueError("shelf clip crossed a parallel polygon edge")
            fraction = previous_distance / denominator
            clipped.append(_add(
                previous, _mul(_sub(current, previous), fraction)))
        if current_inside:
            clipped.append(current)
        previous = current
        previous_distance = current_distance
        previous_inside = current_inside

    points = _canonical_polygon(clipped)
    if len(points) < 3 or _polygon_crossings(points):
        raise ValueError("pocket shelf produced an invalid cut outline")
    shelf_edges = []
    for index, point in enumerate(points):
        other = points[(index + 1) % len(points)]
        if abs(signed(point)) <= _POINT_TOLERANCE_M and \
                abs(signed(other)) <= _POINT_TOLERANCE_M:
            shelf_edges.append(index)
    if len(shelf_edges) != 1:
        raise ValueError("pocket shelf must produce one drop edge")
    measured = _dot(_sub(drop_mid, mouth_mid), outward)
    return {
        "outline": points,
        "centroid": _polygon_centroid(points),
        "shelf_edge": shelf_edges[0],
        "mouth_mid": mouth_mid,
        "drop_mid": drop_mid,
        "outward": outward,
        "shelf_m": measured,
    }


def pocket_metrics(data=None):
    """Measure mouths and cut angles from the actual solver segments."""
    if data is None:
        data = load()
    lines = linear_rows(data)
    connections = _arc_connections(data, lines)
    result = {}
    for pocket in pocket_rows(data):
        owned = [row for row in connections
                 if row["jaw"]["line"]["pocket"]["id"] == pocket["id"]]
        if len(owned) != 2:
            raise ValueError("pocket %s does not own two jaws" % pocket["id"])
        lips = []
        cuts = []
        jaw_ids = []
        for connection in owned:
            jaw = connection["jaw"]["line"]
            main = connection["main"]["line"]
            # WPA mouth points are theoretical sharp intersections.  The
            # solver rounds those intersections with transition arcs, so using
            # the arc endpoints understates the mouth.
            lips.append(_line_intersection(jaw, main))
            jaw_ids.append(jaw["id"])
            # The cut is measured against the connected main cushion, not the
            # nearest global X/Y axis.  That distinction is essential for side
            # pockets, whose jaws are nearly horizontal beside vertical rails.
            cosine = abs(_dot(jaw["tangent"], main["tangent"]))
            acute = math.acos(_clamp(cosine))
            cuts.append(180.0 - math.degrees(acute))
        result[pocket["name"]] = {
            "kind": pocket["kind"],
            "mouth_m": distance(lips[0], lips[1]),
            "cut_angles_deg": cuts,
            "lip_points": [centered(data, point) for point in lips],
            "jaw_ids": jaw_ids,
            "center": pocket["center"],
            "radius_m": pocket["radius"],
        }
    return result


def _point_on_segment(point, start, end, tolerance=1e-10):
    if abs(_cross(_sub(end, start), _sub(point, start))) > tolerance:
        return False
    return (min(start[0], end[0]) - tolerance <= point[0] <=
            max(start[0], end[0]) + tolerance and
            min(start[1], end[1]) - tolerance <= point[1] <=
            max(start[1], end[1]) + tolerance)


def _segments_intersect(a, b, c, d, tolerance=1e-10):
    ab_c = _cross(_sub(b, a), _sub(c, a))
    ab_d = _cross(_sub(b, a), _sub(d, a))
    cd_a = _cross(_sub(d, c), _sub(a, c))
    cd_b = _cross(_sub(d, c), _sub(b, c))
    if ((ab_c > tolerance and ab_d < -tolerance) or
            (ab_c < -tolerance and ab_d > tolerance)) and \
            ((cd_a > tolerance and cd_b < -tolerance) or
             (cd_a < -tolerance and cd_b > tolerance)):
        return True
    return ((abs(ab_c) <= tolerance and _point_on_segment(c, a, b)) or
            (abs(ab_d) <= tolerance and _point_on_segment(d, a, b)) or
            (abs(cd_a) <= tolerance and _point_on_segment(a, c, d)) or
            (abs(cd_b) <= tolerance and _point_on_segment(b, c, d)))


def _polygon_crossings(points):
    crossings = []
    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first or second == (first + 1) % count or \
                    first == (second + 1) % count:
                continue
            c, d = points[second], points[(second + 1) % count]
            if _segments_intersect(a, b, c, d):
                crossings.append((first, second))
    return crossings


def _point_in_polygon(point, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True
        if ((current[1] > point[1]) != (previous[1] > point[1])):
            x_cross = ((previous[0] - current[0]) *
                       (point[1] - current[1]) /
                       (previous[1] - current[1]) + current[0])
            if point[0] < x_cross:
                inside = not inside
        previous = current
    return inside


def point_segment_distance(point, start, end):
    """Shortest planar distance from a point to a finite segment."""
    edge = _sub(end, start)
    length_squared = _dot(edge, edge)
    if length_squared <= 1e-20:
        return distance(point, start)
    fraction = _clamp(_dot(_sub(point, start), edge) / length_squared,
                      0.0, 1.0)
    return distance(point, _add(start, _mul(edge, fraction)))


def polygon_boundary_distance(point, polygon):
    """Shortest planar distance from a point to a closed polygon boundary."""
    return min(point_segment_distance(
        point, polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon)))


def _proper_segment_intersection(a, b, c, d):
    first = _sub(b, a)
    second = _sub(d, c)
    denominator = _cross(first, second)
    if abs(denominator) <= 1e-14:
        raise ValueError("parallel buffer edges cannot be spliced")
    fraction = _cross(_sub(c, a), second) / denominator
    return _add(a, _mul(first, fraction))


def _clean_buffer_self_intersections(points, source):
    """Remove the small re-entrant loops produced by narrow pocket mouths."""
    result = _dedupe_consecutive(points, tolerance=1e-9)
    for _iteration in range(128):
        crossings = _polygon_crossings(result)
        if not crossings:
            return result
        first, second = crossings[0]
        crossing = _proper_segment_intersection(
            result[first], result[(first + 1) % len(result)],
            result[second], result[(second + 1) % len(result)])
        candidates = (
            [crossing] + result[first + 1:second + 1],
            [crossing] + result[second + 1:] + result[:first + 1],
        )
        candidates = [_dedupe_consecutive(candidate, tolerance=1e-9)
                      for candidate in candidates if len(candidate) >= 3]
        if not candidates:
            raise ValueError("buffer self-intersection cleanup collapsed")

        # The valid outside buffer is the loop containing the source polygon;
        # area is the deterministic tiebreaker for a crossing on the boundary.
        result = max(candidates, key=lambda candidate: (
            sum(_point_in_polygon(point, candidate) for point in source),
            abs(_signed_area(candidate))))
    raise ValueError("buffer self-intersection cleanup did not converge")


def outward_buffer(points, distance_m, max_arc_step_deg=7.5):
    """Round-join outward buffer for a simple CCW pocket polygon.

    This is the Blender-free derivation used for WPA pocket back-draft.  A
    centroid-radial scale does not preserve a constant face angle, especially
    at a side pocket.  Each edge is instead offset by the requested physical
    distance; convex turns receive a round join and concave turns intersect
    their two offset lines.  Narrow-mouth re-entrant loops are spliced away,
    producing one simple containing polygon with no holes.
    """
    if not math.isfinite(distance_m) or distance_m <= 0.0:
        raise ValueError("buffer distance must be positive and finite")
    if not math.isfinite(max_arc_step_deg) or not (0.0 < max_arc_step_deg <=
                                                   45.0):
        raise ValueError("buffer arc step must be within (0, 45] degrees")
    source = _canonical_polygon(points)
    step = math.radians(max_arc_step_deg)
    result = []
    count = len(source)
    for index, point in enumerate(source):
        prior = source[index - 1]
        following = source[(index + 1) % count]
        prior_edge = _unit(_sub(point, prior))
        next_edge = _unit(_sub(following, point))
        prior_normal = (prior_edge[1], -prior_edge[0])
        next_normal = (next_edge[1], -next_edge[0])
        turn = math.atan2(_cross(prior_edge, next_edge),
                          _dot(prior_edge, next_edge))
        if turn > 1e-9:
            start_angle = math.atan2(prior_normal[1], prior_normal[0])
            segments = max(1, int(math.ceil(turn / step)))
            for sample in range(segments + 1):
                angle = start_angle + turn * sample / segments
                result.append((point[0] + distance_m * math.cos(angle),
                               point[1] + distance_m * math.sin(angle)))
        elif turn < -1e-9:
            first = _add(point, _mul(prior_normal, distance_m))
            second = _add(point, _mul(next_normal, distance_m))
            denominator = _cross(prior_edge, next_edge)
            along = _cross(_sub(second, first), next_edge) / denominator
            result.append(_add(first, _mul(prior_edge, along)))
        else:
            result.append(_add(point, _mul(prior_normal, distance_m)))

    result = _clean_buffer_self_intersections(result, source)
    result = _canonical_polygon(result)
    crossings = _polygon_crossings(result)
    if crossings:
        raise ValueError("outward buffer is self-intersecting")
    if not all(_point_in_polygon(point, result) for point in source):
        raise ValueError("outward buffer does not contain its source")
    tolerance = max(2e-6, distance_m * 0.005)
    errors = [abs(polygon_boundary_distance(point, source) - distance_m)
              for point in result]
    if max(errors, default=0.0) > tolerance:
        raise ValueError("outward buffer exceeds distance tolerance")
    return result


def validate_geometry(data=None, angle_tolerance_deg=0.05,
                      mouth_tolerance_m=0.00025):
    """Validate topology and WPA-facing metrics without importing Blender.

    Returns a JSON-serializable report and raises ``ValueError`` when the
    source contract cannot produce coherent cushions and pocket cutters.
    """
    if data is None:
        data = load()
    lines = linear_rows(data)
    main = [row for row in lines if row["kind"] == "main"]
    jaws = [row for row in lines if row["kind"] == "jaw"]
    connections = _arc_connections(data, lines)
    failures = []
    if len(main) != 6 or len(jaws) != 12 or len(connections) != 12:
        failures.append("expected 6 mains, 12 jaws, and 12 transitions")
    connected_jaws = [row["jaw"]["line"]["id"] for row in connections]
    if len(set(connected_jaws)) != len(jaws) or \
            set(connected_jaws) != {row["id"] for row in jaws}:
        failures.append("every jaw must own exactly one transition arc")
    connected_main_ends = [
        (row["main"]["line"]["id"], row["main"]["endpoint"])
        for row in connections
    ]
    if len(set(connected_main_ends)) != len(connected_main_ends):
        failures.append("a main-cushion endpoint owns multiple transitions")

    arcs = arc_rows(data, steps=8)
    minimum_alignment = 1.0
    for arc, connection in zip(arcs, connections):
        if arc["id"] != connection["id"]:
            failures.append("transition ordering is not deterministic")
        for normal in arc["normals"]:
            if abs(_length(normal) - 1.0) > 1e-9:
                failures.append("arc %s has a non-unit normal" % arc["id"])
                break
        start_alignment = _dot(
            arc["normals"][0], connection["main"]["line"]["normal"])
        end_alignment = _dot(
            arc["normals"][-1], connection["jaw"]["line"]["normal"])
        minimum_alignment = min(minimum_alignment, start_alignment,
                                end_alignment)
        if min(start_alignment, end_alignment) < 0.99:
            failures.append("arc %s normals do not match its lines" %
                            arc["id"])

    metrics = pocket_metrics(data)
    outline_report = {}
    for pocket in pocket_rows(data):
        metric = metrics[pocket["name"]]
        expected_angle = EXPECTED_CUT_ANGLES_DEG[pocket["kind"]]
        if any(abs(angle - expected_angle) > angle_tolerance_deg
               for angle in metric["cut_angles_deg"]):
            failures.append("%s cut angle is not %.1f degrees" %
                            (pocket["name"], expected_angle))
        low, high = WPA_MOUTH_RANGES_M[pocket["kind"]]
        mouth = metric["mouth_m"]
        if mouth < low - mouth_tolerance_m or \
                mouth > high + mouth_tolerance_m:
            failures.append("%s mouth is outside the WPA range" %
                            pocket["name"])

        outline, centroid, mouth_edge = pocket_outline_details(data, pocket)
        area = _signed_area(outline)
        crossings = _polygon_crossings(outline)
        if area <= 0.0:
            failures.append("%s outline is not CCW" % pocket["name"])
        if crossings:
            failures.append("%s outline self-intersects" % pocket["name"])
        if not _point_in_polygon(centroid, outline):
            failures.append("%s outline centroid is outside" %
                            pocket["name"])
        outline_report[pocket["name"]] = {
            "area_m2": area,
            "centroid": centroid,
            "mouth_edge_index": mouth_edge,
            "mouth_edge_span_m": distance(
                outline[mouth_edge], outline[(mouth_edge + 1) % len(outline)]),
            "vertex_count": len(outline),
            "winding": "CCW" if area > 0.0 else "CW",
            "self_intersections": crossings,
        }

    if failures:
        raise ValueError("invalid pool geometry contract: " +
                         "; ".join(dict.fromkeys(failures)))
    return {
        "feature_counts": {
            "main": len(main),
            "jaw": len(jaws),
            "transition_arc": len(connections),
            "pocket": len(metrics),
        },
        "minimum_arc_normal_alignment": minimum_alignment,
        "pockets": metrics,
        "outlines": outline_report,
    }


def validate_against_config(config, data=None):
    if data is None:
        data = load()
    checks = {
        "play_w": (float(data["w"]), config.PLAY_W),
        "play_l": (float(data["l"]), config.PLAY_L),
        "bed_z": (float(data["bed"]), config.BED_Z),
        "ball_radius": (float(data["ball_R"]), config.BALL_R),
        "cushion_nose": (float(data["nose"]), config.CUSHION_NOSE),
    }
    failures = [name for name, (actual, expected) in checks.items()
                if abs(actual - expected) > 1e-7]
    if failures:
        raise ValueError("pooltool/render contract drift: " +
                         ", ".join(failures))
    return True


if __name__ == "__main__":
    print(json.dumps(validate_geometry(), indent=2, sort_keys=True))
