"""Deterministic billiards systems shared by the physics test/export scripts.

This module is deliberately Blender-free.  It runs under the isolated Python
3.12 environment beside the project and uses Pooltool 0.6.0 as the event-based
shot authority.  Blender only consumes exported trajectories.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pooltool as pt

from pooltool.objects.ball.datatypes import Ball, BallState
from pooltool.objects.cue.datatypes import Cue, CueSpecs
from pooltool.objects.table.components import (
    CircularCushionSegment,
    CushionDirection,
    CushionSegments,
    LinearCushionSegment,
    Pocket,
)
from pooltool.objects.table.specs import TableType
from pooltool.physics import PhysicsEngine
from pooltool.physics.resolve.ball_ball.friction import AverageBallBallFriction
from pooltool.physics.resolve.ball_ball.frictional_inelastic import (
    FrictionalInelastic,
)
from pooltool.physics.resolve.ball_cushion.stronge_compliant.model import (
    StrongeCompliantCircular,
    StrongeCompliantLinear,
)
from pooltool.physics.resolve.ball_pocket import CanonicalBallPocket
from pooltool.physics.resolve.resolver import Resolver
from pooltool.physics.resolve.stick_ball.instantaneous_point import (
    InstantaneousPoint,
)
from pooltool.physics.resolve.transition import CanonicalTransition
from trajectory_contract import (
    TRAJECTORY_HASH_REQUIRED_FIELDS,
    TRAJECTORY_HASH_VOLATILE_FIELDS,
    recompute_trajectory_sha256,
    trajectory_hash_payload,
    verify_trajectory_sha256,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROFILE_PATH = ROOT / "assets" / "data" / "pool_physics_profile.json"
GEOMETRY_PATH = ROOT / "assets" / "data" / "table_wpa_geometry.json"
POOLTOOL_REQUIRED = "0.6.0"
STATE_NAMES = {
    0: "stationary",
    1: "spinning",
    2: "sliding",
    3: "rolling",
    4: "pocketed",
}

def sha256_file(path: os.PathLike[str] | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: os.PathLike[str] | str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_profile(path: os.PathLike[str] | str = PROFILE_PATH) -> dict[str, Any]:
    profile = load_json(path)
    if profile.get("schema") != "pool-physics-profile/v1":
        raise ValueError("unsupported pool physics profile")
    if profile["solver"]["version"] != POOLTOOL_REQUIRED:
        raise ValueError("profile Pooltool version is not pinned to 0.6.0")
    if pt.__version__ != POOLTOOL_REQUIRED:
        raise RuntimeError(
            "Pooltool %s is required, found %s" %
            (POOLTOOL_REQUIRED, pt.__version__)
        )
    return profile


def load_geometry(path: os.PathLike[str] | str = GEOMETRY_PATH) -> dict[str, Any]:
    data = load_json(path)
    required = {"w", "l", "bed", "ball_R", "nose", "linear", "circular", "pockets"}
    missing = required - set(data)
    if missing:
        raise ValueError("incomplete geometry contract: " + ", ".join(sorted(missing)))
    if (len(data["linear"]), len(data["circular"]), len(data["pockets"])) != (18, 12, 6):
        raise ValueError("unexpected table contact feature count")
    return data


def build_table(geometry: dict[str, Any] | None = None) -> pt.Table:
    geometry = geometry or load_geometry()
    linear = {
        str(key): LinearCushionSegment(
            id=str(key),
            p1=np.asarray(row["p1"], dtype=np.float64),
            p2=np.asarray(row["p2"], dtype=np.float64),
            direction=CushionDirection.BOTH,
        )
        for key, row in geometry["linear"].items()
    }
    circular = {
        str(key): CircularCushionSegment(
            id=str(key),
            center=np.asarray(row["center"], dtype=np.float64),
            radius=float(row["radius"]),
        )
        for key, row in geometry["circular"].items()
    }
    pockets = {
        str(key): Pocket(
            id=str(key),
            center=np.asarray(row["center"], dtype=np.float64),
            radius=float(row["radius"]),
            depth=float(row["depth"]),
        )
        for key, row in geometry["pockets"].items()
    }
    return pt.Table(
        cushion_segments=CushionSegments(linear=linear, circular=circular),
        pockets=pockets,
        table_type=TableType.POCKET,
        height=float(geometry["bed"]),
    )


def ball_parameter_kwargs(profile: dict[str, Any] | None = None) -> dict[str, float]:
    profile = profile or load_profile()
    row = profile["ball"]
    gravity = float(row["gravity_mps2"])
    spin_alpha = float(row["sidespin_deceleration_rad_s2"])
    return {
        "m": float(row["mass_kg"]),
        "R": float(row["radius_m"]),
        "u_s": float(row["sliding_friction"]),
        "u_r": float(row["rolling_deceleration_mps2"]) / gravity,
        # alpha_z = 5 * (proportionality * R) * g / (2R)
        "u_sp_proportionality": 2.0 * spin_alpha / (5.0 * gravity),
        "u_b": float(row["ball_ball_friction"]),
        "e_b": float(row["ball_ball_restitution"]),
        "e_c": float(row["cushion_restitution_parameter"]),
        "f_c": float(row["cushion_friction"]),
        "g": gravity,
    }


def cue_specs(profile: dict[str, Any] | None = None) -> CueSpecs:
    profile = profile or load_profile()
    row = profile["cue"]
    return CueSpecs(
        brand="Unbranded house cue",
        M=float(row["mass_kg"]),
        length=float(row["length_m"]),
        tip_radius=float(row["tip_curvature_radius_m"]),
        shaft_radius_at_tip=float(row["shaft_radius_at_tip_m"]),
        shaft_radius_at_butt=float(row["shaft_radius_at_butt_m"]),
        end_mass=float(row["end_mass_kg"]),
    )


def explicit_engine(profile: dict[str, Any] | None = None) -> PhysicsEngine:
    """Return an engine that never reads mutable user configuration."""
    profile = profile or load_profile()
    omega_ratio = float(profile["solver"]["cushion_omega_ratio"])
    resolver = Resolver(
        ball_ball=FrictionalInelastic(friction=AverageBallBallFriction()),
        ball_linear_cushion=StrongeCompliantLinear(omega_ratio=omega_ratio),
        ball_circular_cushion=StrongeCompliantCircular(omega_ratio=omega_ratio),
        ball_pocket=CanonicalBallPocket(),
        stick_ball=InstantaneousPoint(
            english_throttle=1.0,
            squirt_throttle=1.0,
        ),
        transition=CanonicalTransition(),
        version=int(profile["solver"]["resolver_version"]),
    )
    return PhysicsEngine(resolver=resolver)


def make_ball(
    ball_id: str,
    xy: Iterable[float],
    profile: dict[str, Any] | None = None,
) -> Ball:
    return Ball.create(
        str(ball_id),
        xy=tuple(float(value) for value in xy),
        **ball_parameter_kwargs(profile),
    )


def set_motion(
    ball: Ball,
    velocity: Iterable[float],
    omega: Iterable[float],
    state: int,
) -> Ball:
    ball.state.rvw[1] = np.asarray(tuple(velocity), dtype=np.float64)
    ball.state.rvw[2] = np.asarray(tuple(omega), dtype=np.float64)
    ball.state.s = int(state)
    return ball


def rack_layout(
    profile: dict[str, Any] | None = None,
    geometry: dict[str, Any] | None = None,
) -> dict[str, tuple[float, float]]:
    profile = profile or load_profile()
    geometry = geometry or load_geometry()
    radius = float(profile["ball"]["radius_m"])
    diameter = radius * 2.0
    gap = diameter * float(profile["rack"]["contact_gap_ratio"])
    step = diameter + gap
    pitch = math.sqrt(3.0) * 0.5 * step
    apex_x, apex_y = (float(value) for value in profile["rack"]["apex_pool_xy_m"])
    order = profile["rack"]["order"]
    positions: dict[str, tuple[float, float]] = {}
    for row_index, row in enumerate(order):
        y = apex_y - row_index * pitch
        x0 = apex_x - (len(row) - 1) * step * 0.5
        for column, number in enumerate(row):
            positions[str(number)] = (x0 + column * step, y)
    if sorted(int(key) for key in positions) != list(range(1, 16)):
        raise ValueError("rack must contain balls 1 through 15 exactly once")
    if not (0.0 < min(y for _x, y in positions.values()) < float(geometry["l"])):
        raise ValueError("rack lies outside the playfield")
    return positions


def system_from_positions(
    positions: dict[str, Iterable[float]],
    *,
    cue_ball_id: str = "cue",
    cue_state: dict[str, float] | None = None,
    profile: dict[str, Any] | None = None,
    geometry: dict[str, Any] | None = None,
) -> pt.System:
    profile = profile or load_profile()
    geometry = geometry or load_geometry()
    balls = {
        str(ball_id): make_ball(str(ball_id), xy, profile)
        for ball_id, xy in positions.items()
    }
    cue_state = cue_state or {}
    cue = Cue(
        cue_ball_id=str(cue_ball_id),
        specs=cue_specs(profile),
        **cue_state,
    )
    return pt.System(cue=cue, table=build_table(geometry), balls=balls)


def control_break_system(
    profile: dict[str, Any] | None = None,
    geometry: dict[str, Any] | None = None,
) -> pt.System:
    profile = profile or load_profile()
    geometry = geometry or load_geometry()
    positions: dict[str, Iterable[float]] = rack_layout(profile, geometry)
    positions["cue"] = tuple(profile["control_break"]["cue_ball_pool_xy_m"])
    row = profile["control_break"]
    cue_state = {
        "V0": float(row["cue_speed_mps"]),
        "phi": float(row["phi_deg"]),
        "theta": float(row["theta_deg"]),
        "a": float(row["side_offset_a"]),
        "b": float(row["vertical_offset_b"]),
    }
    return system_from_positions(
        positions,
        cue_ball_id="cue",
        cue_state=cue_state,
        profile=profile,
        geometry=geometry,
    )


def simulate(
    system: pt.System,
    *,
    profile: dict[str, Any] | None = None,
    continuous: bool = False,
    sample_rate_hz: int | None = None,
    max_events: int = 20000,
) -> pt.System:
    profile = profile or load_profile()
    if sample_rate_hz is None:
        sample_rate_hz = int(profile["solver"]["sample_rate_hz"])
    return pt.simulate(
        system,
        engine=explicit_engine(profile),
        inplace=True,
        continuous=continuous,
        dt=1.0 / sample_rate_hz if continuous else None,
        max_events=max_events,
    )


def event_rows(system: pt.System) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in system.events:
        if event.event_type.value == "none":
            continue
        row: dict[str, Any] = {
            "type": event.event_type.value,
            "time_s": round(float(event.time), 12),
            "ids": [str(value) for value in event.ids],
        }
        ball_agents = []
        for agent in event.agents:
            initial = getattr(agent, "initial", None)
            final = getattr(agent, "final", None)
            if not isinstance(initial, Ball):
                continue
            payload: dict[str, Any] = {"id": str(agent.id)}
            for label, ball in (("initial", initial), ("final", final)):
                if not isinstance(ball, Ball):
                    continue
                payload[label] = {
                    "position_m": [round(float(v), 12) for v in ball.xyz],
                    "velocity_mps": [round(float(v), 12) for v in ball.vel],
                    "omega_rad_s": [round(float(v), 12) for v in ball.avel],
                    "state": STATE_NAMES[int(ball.state.s)],
                }
            ball_agents.append(payload)
        if ball_agents:
            row["balls"] = ball_agents
        rows.append(row)
    return rows


def final_state_rows(system: pt.System) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for ball_id in sorted(system.balls, key=lambda value: (value != "cue", int(value) if value.isdigit() else -1)):
        ball = system.balls[ball_id]
        result[str(ball_id)] = {
            "state": STATE_NAMES[int(ball.state.s)],
            "rvw": [
                [round(float(value), 12) for value in vector]
                for vector in ball.state.rvw
            ],
        }
    return result


def simulation_fingerprint(system: pt.System) -> tuple[str, dict[str, Any]]:
    payload = {
        "duration_s": round(float(system.t), 12),
        "events": event_rows(system),
        "final": final_state_rows(system),
    }
    return canonical_sha256(payload), payload


def provenance(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    try:
        import numba
        numba_version = numba.__version__
    except Exception:
        numba_version = "unavailable"
    return {
        "pooltool": pt.__version__,
        "python": platform.python_version(),
        "python_executable": Path(sys.executable).name,
        "numpy": np.__version__,
        "numba": numba_version,
        "resolver_version": int(profile["solver"]["resolver_version"]),
        "profile_sha256": sha256_file(PROFILE_PATH),
        "geometry_contract_sha256": sha256_file(GEOMETRY_PATH),
    }


def quaternion_multiply(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float, float]:
    aw, ax, ay, az = (float(value) for value in a)
    bw, bx, by, bz = (float(value) for value in b)
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quaternion_normalize(q: Iterable[float]) -> tuple[float, float, float, float]:
    values = tuple(float(value) for value in q)
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1e-15:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(value / length for value in values)  # type: ignore[return-value]


def deterministic_initial_quaternion(ball_id: str, seed: int) -> tuple[float, float, float, float]:
    digest = hashlib.sha256((str(seed) + ":" + str(ball_id)).encode("ascii")).digest()
    axis = np.array([
        int.from_bytes(digest[0:2], "big") / 32767.5 - 1.0,
        int.from_bytes(digest[2:4], "big") / 32767.5 - 1.0,
        int.from_bytes(digest[4:6], "big") / 32767.5 - 1.0,
    ], dtype=np.float64)
    norm = float(np.linalg.norm(axis))
    if norm <= 1e-12:
        axis = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    else:
        axis /= norm
    angle = (int.from_bytes(digest[6:10], "big") / 2**32) * 2.0 * math.pi
    half = angle * 0.5
    return quaternion_normalize((
        math.cos(half),
        axis[0] * math.sin(half),
        axis[1] * math.sin(half),
        axis[2] * math.sin(half),
    ))


def integrate_quaternions(
    states: list[BallState],
    initial: Iterable[float],
    *,
    interval_end_omegas: Iterable[Iterable[float]] | None = None,
) -> list[tuple[float, float, float, float]]:
    if not states:
        return []
    if interval_end_omegas is None:
        end_omegas = [state.rvw[2] for state in states]
    else:
        end_omegas = [
            np.asarray(tuple(omega), dtype=np.float64)
            for omega in interval_end_omegas
        ]
        if len(end_omegas) != len(states):
            raise ValueError("interval_end_omegas must match states")
    result = [quaternion_normalize(initial)]
    for index, (previous, current) in enumerate(zip(states, states[1:]), start=1):
        dt = max(0.0, float(current.t) - float(previous.t))
        # `current` is the post-event state when its timestamp is a collision.
        # Rotation over [previous.t, current.t] must instead end at the
        # physically evolved left limit.  Averaging through the instantaneous
        # omega jump invents rotation before contact.
        omega = 0.5 * (previous.rvw[2] + end_omegas[index])
        magnitude = float(np.linalg.norm(omega))
        if magnitude <= 1e-12 or dt <= 0.0:
            result.append(result[-1])
            continue
        axis = omega / magnitude
        half = magnitude * dt * 0.5
        delta = (
            math.cos(half),
            float(axis[0]) * math.sin(half),
            float(axis[1]) * math.sin(half),
            float(axis[2]) * math.sin(half),
        )
        result.append(quaternion_normalize(quaternion_multiply(delta, result[-1])))
    return result


def union_sample_times(system: pt.System, sample_rate_hz: int) -> list[float]:
    dt = 1.0 / float(sample_rate_hz)
    count = int(math.ceil(float(system.t) / dt))
    # Preserve the solver's exact Float64 event times.  Rounding here can put a
    # nominal event sample infinitesimally before the event, selecting the
    # pre-contact history state and delaying the discontinuity to a later key.
    times = {min(index * dt, float(system.t)) for index in range(count + 1)}
    times.add(float(system.t))
    for event in system.events:
        times.add(float(event.time))
    return sorted(times)


def interval_end_angular_velocities(
    ball: Ball,
    times: Iterable[float],
    event_times: Iterable[float],
) -> list[np.ndarray]:
    """Return physical left-limit omega for every integration endpoint.

    The exported state at an event time is intentionally the post-event state.
    For the interval ending there, however, angular motion must be integrated
    to the pre-event state.  All event times split the integration timeline;
    same-time contact islands have zero duration and therefore add no rotation.
    """
    values = [float(value) for value in times]
    discontinuities = {float(value) for value in event_times}
    queries = [
        float(np.nextafter(value, -np.inf))
        if value > 0.0 and value in discontinuities else value
        for value in values
    ]
    states = pt.interpolate_ball_states(ball, queries, extrapolate=True)
    return [np.asarray(state.rvw[2], dtype=np.float64) for state in states]


def pocket_events(system: pt.System) -> dict[str, tuple[float, str, Ball]]:
    result: dict[str, tuple[float, str, Ball]] = {}
    for event in system.events:
        if event.event_type.value != "ball_pocket":
            continue
        ball_id, pocket_id = str(event.ids[0]), str(event.ids[1])
        initial_ball = next(
            agent.initial for agent in event.agents
            if str(agent.id) == ball_id and isinstance(agent.initial, Ball)
        )
        result[ball_id] = (float(event.time), pocket_id, initial_ball)
    return result


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def export_trajectory(
    system: pt.System,
    *,
    shot_id: str,
    profile: dict[str, Any] | None = None,
    geometry: dict[str, Any] | None = None,
    sample_rate_hz: int | None = None,
) -> dict[str, Any]:
    profile = profile or load_profile()
    geometry = geometry or load_geometry()
    sample_rate_hz = sample_rate_hz or int(profile["solver"]["sample_rate_hz"])
    if not system.simulated:
        raise ValueError("system must be simulated before export")

    base_times = union_sample_times(system, sample_rate_hz)
    captures = pocket_events(system)
    drop_duration = float(profile["playback"]["pocket_drop_duration_s"])
    duration = float(system.t)
    for capture_time, _pocket_id, _ball in captures.values():
        duration = max(duration, capture_time + drop_duration)
    if duration > float(system.t):
        extra_count = int(math.ceil((duration - float(system.t)) * sample_rate_hz))
        base_times.extend(
            round(float(system.t) + (index + 1) / sample_rate_hz, 12)
            for index in range(extra_count)
        )
        base_times.append(round(duration, 12))
        base_times = sorted(set(base_times))

    seed = int(profile["solver"]["random_seed"])
    event_times = {float(event.time) for event in system.events}
    trajectories: dict[str, Any] = {}
    for ball_id in sorted(system.balls, key=lambda value: (value != "cue", int(value) if value.isdigit() else -1)):
        ball = system.balls[ball_id]
        solver_times = [min(float(system.t), value) for value in base_times]
        states = pt.interpolate_ball_states(ball, solver_times, extrapolate=True)
        interval_end_omegas = interval_end_angular_velocities(
            ball,
            base_times,
            event_times,
        )
        for state, time_s in zip(states, base_times):
            state.t = float(time_s)

        capture = captures.get(ball_id)
        if capture:
            capture_time, pocket_id, initial_ball = capture
            pocket = system.table.pockets[pocket_id]
            start = initial_ball.xyz.copy()
            target = np.array([pocket.center[0], pocket.center[1], -pocket.depth], dtype=np.float64)
            for index, (state, time_s) in enumerate(zip(states, base_times)):
                if time_s < capture_time:
                    continue
                progress = (time_s - capture_time) / drop_duration
                blend = _smoothstep(progress)
                state.rvw[0] = start * (1.0 - blend) + target * blend
                state.rvw[1:] = 0.0
                state.s = 4
                if time_s > capture_time:
                    interval_end_omegas[index] = np.zeros(
                        3, dtype=np.float64
                    )

        quaternions = integrate_quaternions(
            states,
            deterministic_initial_quaternion(ball_id, seed),
            interval_end_omegas=interval_end_omegas,
        )
        samples = []
        for state, quaternion in zip(states, quaternions):
            samples.append({
                "t": round(float(state.t), 9),
                "p": [round(float(value), 9) for value in state.rvw[0]],
                "v": [round(float(value), 9) for value in state.rvw[1]],
                "w": [round(float(value), 9) for value in state.rvw[2]],
                "q": [round(float(value), 10) for value in quaternion],
                "s": STATE_NAMES[int(state.s)],
            })
        trajectories[ball_id] = {
            "number": 0 if ball_id == "cue" else int(ball_id),
            "initial_quaternion_wxyz": samples[0]["q"],
            "pocket_id": capture[1] if capture else None,
            "capture_time_s": round(capture[0], 9) if capture else None,
            "samples": samples,
        }

    fingerprint, canonical = simulation_fingerprint(system)
    payload: dict[str, Any] = {
        "schema": "pool-shot-trajectory/v1",
        "shot_id": shot_id,
        "sample_rate_hz": int(sample_rate_hz),
        "duration_s": round(duration, 9),
        "solver_duration_s": round(float(system.t), 9),
        "solver_fingerprint_sha256": fingerprint,
        "profile_sha256": sha256_file(PROFILE_PATH),
        "geometry_contract_sha256": sha256_file(GEOMETRY_PATH),
        "provenance": provenance(profile),
        "cue": {
            "id": system.cue.id,
            "cue_ball_id": system.cue.cue_ball_id,
            "V0_mps": float(system.cue.V0),
            "phi_deg": float(system.cue.phi),
            "theta_deg": float(system.cue.theta),
            "a": float(system.cue.a),
            "b": float(system.cue.b),
            "mass_kg": float(system.cue.specs.M),
            "length_m": float(system.cue.specs.length),
        },
        "ball_parameters": ball_parameter_kwargs(profile),
        "rack": {
            "positions_pool_xy_m": {
                key: [round(value[0], 9), round(value[1], 9)]
                for key, value in rack_layout(profile, geometry).items()
            },
            "order": profile["rack"]["order"],
            "contact_gap_ratio": profile["rack"]["contact_gap_ratio"],
        },
        "events": event_rows(system),
        "canonical_solver_state": canonical,
        "balls": trajectories,
        "coordinate_contract": {
            "pool_origin": "southwest cushion-nose intersection, bed z=0",
            "blender_world_from_pool": [
                "x = pool_x - 0.385",
                "y = pool_y + 0.880",
                "z = pool_z + 0.762"
            ],
        },
        "pocket_drop": {
            "duration_s": drop_duration,
            "method": "continuous monotonic solver-capture tail",
        },
    }
    payload["trajectory_sha256"] = recompute_trajectory_sha256(payload)
    verify_trajectory_sha256(payload)
    return payload


def write_json(path: os.PathLike[str] | str, value: Any, *, compact: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            value,
            handle,
            sort_keys=True,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
            ensure_ascii=True,
            allow_nan=False,
        )
        handle.write("\n")
