"""Run deterministic, source-backed billiards acceptance tests.

The report is independent from the static Blender dimension audit.  It tests
the event solver against analytic motion, collision, cushion, pocket, spin,
break and repeatability contracts while leaving every .blend untouched.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import math
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pooltool as pt
from pooltool.physics.evolve import evolve_ball_motion

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_game_physics as P  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "reports" / "physics_validation.json"


class Suite:
    def __init__(self) -> None:
        self.tests: list[dict[str, Any]] = []

    def run(self, test_id: str, description: str, func: Callable[[], dict[str, Any]]) -> None:
        try:
            details = func()
            status = "PASS"
            error = None
        except Exception as exc:  # keep the full suite useful after one failure
            details = {}
            status = "FAIL"
            error = "%s: %s" % (type(exc).__name__, exc)
        row: dict[str, Any] = {
            "id": test_id,
            "description": description,
            "required": True,
            "status": status,
            "observed": details,
        }
        if error:
            row["error"] = error
        self.tests.append(row)
        print("  [%s] %s" % (status, test_id))
        if error:
            print("         " + error)

    def summary(self) -> dict[str, int]:
        passed = sum(row["status"] == "PASS" for row in self.tests)
        failed = len(self.tests) - passed
        return {
            "total": len(self.tests),
            "passed": passed,
            "failed": failed,
            "required_failures": failed,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(actual: float, expected: float, tolerance: float, label: str) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            "%s %.12g differs from %.12g by %.3g (tolerance %.3g)" %
            (label, actual, expected, abs(actual - expected), tolerance)
        )


def motion_system(
    positions: dict[str, tuple[float, float]],
    motions: dict[str, tuple[tuple[float, float, float], tuple[float, float, float], int]],
    *,
    cue_state: dict[str, float] | None = None,
    profile: dict[str, Any],
    geometry: dict[str, Any],
) -> pt.System:
    system = P.system_from_positions(
        positions,
        cue_state=cue_state,
        profile=profile,
        geometry=geometry,
    )
    for ball_id, (velocity, omega, state) in motions.items():
        P.set_motion(system.balls[ball_id], velocity, omega, state)
    P.simulate(system, profile=profile)
    return system


def first_event(system: pt.System, event_type: str):
    return next(event for event in system.events if event.event_type.value == event_type)


def ball_agent(event, ball_id: str):
    return next(agent for agent in event.agents if str(agent.id) == str(ball_id))


def kinetic(ball) -> float:
    mass = float(ball.params.m)
    radius = float(ball.params.R)
    inertia = 0.4 * mass * radius * radius
    return 0.5 * mass * float(np.dot(ball.vel, ball.vel)) + \
        0.5 * inertia * float(np.dot(ball.avel, ball.avel))


def resolved_energy_ratios(system: pt.System) -> list[float]:
    # A tight rack resolves simultaneous contact islands as several stable,
    # same-time pair events.  Energy can legitimately move into one pair from
    # a third ball during that island, so audit the complete island rather than
    # demanding that every intermediate pair loses energy independently.
    groups: list[list[Any]] = []
    for event in system.events:
        if event.event_type.value in ("none", "stick_ball") or \
                event.event_type.is_transition():
            continue
        if not groups or abs(float(event.time) - float(groups[-1][0].time)) > 1e-7:
            groups.append([event])
        else:
            groups[-1].append(event)
    ratios = []
    for group in groups:
        initial: dict[str, Any] = {}
        final: dict[str, Any] = {}
        for event in group:
            for agent in event.agents:
                if not isinstance(getattr(agent, "initial", None), pt.Ball):
                    continue
                initial.setdefault(str(agent.id), agent.initial)
                if isinstance(getattr(agent, "final", None), pt.Ball):
                    final[str(agent.id)] = agent.final
        before = sum(kinetic(ball) for ball in initial.values())
        after = sum(kinetic(ball) for ball in final.values())
        if before > 1e-12:
            ratios.append(after / before)
    return ratios


def fixture_contract(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "position_tolerance_m": 1e-6,
        "velocity_tolerance_mps": 1e-6,
        "angular_velocity_tolerance_rad_s": 1e-4,
        "event_time_tolerance_s": 1e-7,
        "momentum_tolerance_kg_mps": 1e-10,
        "rack_contact_tolerance_m": 1e-8,
        "break_repeat_runs": 10,
        "parameters": P.ball_parameter_kwargs(profile),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--repeat", type=int, default=10)
    args = parser.parse_args()
    require(args.repeat >= 2, "--repeat must be at least two")

    profile = P.load_profile()
    geometry = P.load_geometry()
    radius = float(profile["ball"]["radius_m"])
    mass = float(profile["ball"]["mass_kg"])
    gravity = float(profile["ball"]["gravity_mps2"])
    rolling_a = float(profile["ball"]["rolling_deceleration_mps2"])
    suite = Suite()

    def profile_contract_test() -> dict[str, Any]:
        require(abs(radius - float(geometry["ball_R"])) <= 1e-12,
                "profile radius differs from geometry contract")
        require(0.156 <= mass <= 0.170, "ball mass is outside WPA range")
        require(profile["solver"]["version"] == P.POOLTOOL_REQUIRED,
                "solver version is not pinned")
        require(profile["solver"]["float_precision"] == "float64",
                "solver precision must be float64")
        inertia = 0.4 * mass * radius * radius
        params = P.ball_parameter_kwargs(profile)
        close(params["u_r"] * gravity, rolling_a, 1e-12,
              "rolling deceleration")
        spin_alpha = 2.5 * params["u_sp_proportionality"] * gravity
        close(spin_alpha, float(profile["ball"]["sidespin_deceleration_rad_s2"]),
              1e-12, "sidespin deceleration")
        return {
            "mass_kg": mass,
            "diameter_m": 2.0 * radius,
            "solid_sphere_inertia_kg_m2": inertia,
            "rolling_coefficient": params["u_r"],
            "spin_friction_proportionality": params["u_sp_proportionality"],
            "profile_sha256": P.sha256_file(P.PROFILE_PATH),
            "geometry_sha256": P.sha256_file(P.GEOMETRY_PATH),
        }

    suite.run("profile_contract", "Pinned mass, dimensions, coefficients and source contract", profile_contract_test)

    def slide_to_roll_test() -> dict[str, Any]:
        system = motion_system(
            {"cue": (0.300, 1.000)},
            {"cue": ((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), 2)},
            profile=profile, geometry=geometry,
        )
        event = first_event(system, "sliding_rolling")
        final = ball_agent(event, "cue").final
        expected_t = 2.0 / (7.0 * float(profile["ball"]["sliding_friction"]) * gravity)
        expected_v = 5.0 / 7.0
        expected_x = 0.300 + expected_t - 0.5 * \
            float(profile["ball"]["sliding_friction"]) * gravity * expected_t**2
        close(float(event.time), expected_t, 1e-10, "sliding transition time")
        close(float(final.vel[0]), expected_v, 1e-10, "natural-roll speed")
        close(float(final.xyz[0]), expected_x, 1e-10, "natural-roll position")
        slip = final.vel + np.cross(final.avel, np.array([0.0, 0.0, -radius]))
        require(float(np.linalg.norm(slip)) < 1e-9, "natural-roll contact slip remains")
        return {
            "transition_time_s": float(event.time),
            "position_x_m": float(final.xyz[0]),
            "velocity_x_mps": float(final.vel[0]),
            "omega_y_rad_s": float(final.avel[1]),
            "contact_slip_mps": float(np.linalg.norm(slip)),
        }

    suite.run("slide_to_roll", "Analytic sliding-to-natural-roll transition", slide_to_roll_test)

    def rolling_motion_test() -> dict[str, Any]:
        params = P.ball_parameter_kwargs(profile)
        rvw = np.array([
            [0.0, 0.0, radius],
            [1.0, 0.0, 0.0],
            [0.0, 1.0 / radius, 0.0],
        ], dtype=np.float64)
        half, half_state = evolve_ball_motion(
            3, rvw.copy(), radius, mass, params["u_s"],
            params["u_sp_proportionality"] * radius, params["u_r"], gravity, 0.5,
        )
        close(float(half[0, 0]), 0.5 - 0.5 * rolling_a * 0.25,
              1e-10, "rolling position at 0.5s")
        close(float(half[1, 0]), 1.0 - rolling_a * 0.5,
              1e-10, "rolling speed at 0.5s")
        require(half_state == 3, "rolling state changed early")
        stop_time = 1.0 / rolling_a
        stop, stop_state = evolve_ball_motion(
            3, rvw.copy(), radius, mass, params["u_s"],
            params["u_sp_proportionality"] * radius, params["u_r"], gravity,
            stop_time,
        )
        close(float(stop[0, 0]), 0.5 / rolling_a, 1e-9, "rolling stop distance")
        require(stop_state in (0, 1), "ball did not leave rolling state at stop")
        require(float(np.linalg.norm(stop[1])) <= 1e-9, "ball did not stop")
        return {
            "speed_at_0_5_s_mps": float(half[1, 0]),
            "position_at_0_5_s_m": float(half[0, 0]),
            "stop_time_s": stop_time,
            "stop_distance_m": float(stop[0, 0]),
        }

    suite.run("rolling_resistance", "Constant rolling deceleration and analytic stop", rolling_motion_test)

    def head_on_test() -> dict[str, Any]:
        system = motion_system(
            {"cue": (0.635, 0.800), "1": (0.635, 1.200)},
            {"cue": ((0.0, 1.0, 0.0), (-1.0 / radius, 0.0, 0.0), 3)},
            profile=profile, geometry=geometry,
        )
        event = first_event(system, "ball_ball")
        cue_agent = ball_agent(event, "cue")
        one_agent = ball_agent(event, "1")
        incoming = float(cue_agent.initial.vel[1] - one_agent.initial.vel[1])
        separating = float(one_agent.final.vel[1] - cue_agent.final.vel[1])
        restitution = separating / incoming
        close(restitution, float(profile["ball"]["ball_ball_restitution"]),
              1e-9, "head-on restitution")
        p_before = mass * (cue_agent.initial.vel + one_agent.initial.vel)
        p_after = mass * (cue_agent.final.vel + one_agent.final.vel)
        momentum_error = float(np.linalg.norm(p_after - p_before))
        require(momentum_error <= 1e-10, "head-on momentum changed")
        require(kinetic(cue_agent.final) + kinetic(one_agent.final) <=
                kinetic(cue_agent.initial) + kinetic(one_agent.initial) + 1e-10,
                "head-on collision gained energy")
        return {
            "event_time_s": float(event.time),
            "pre_speed_mps": float(cue_agent.initial.vel[1]),
            "cue_post_speed_mps": float(cue_agent.final.vel[1]),
            "object_post_speed_mps": float(one_agent.final.vel[1]),
            "normal_restitution": restitution,
            "momentum_error_kg_mps": momentum_error,
        }

    suite.run("head_on_transfer", "Equal-mass momentum transfer with measured restitution", head_on_test)

    def cut_test() -> dict[str, Any]:
        system = motion_system(
            {"cue": (0.300, 1.000), "1": (0.700, 1.028575)},
            {"cue": ((1.0, 0.0, 0.0), (0.0, 1.0 / radius, 0.0), 3)},
            profile=profile, geometry=geometry,
        )
        event = first_event(system, "ball_ball")
        cue_agent = ball_agent(event, "cue")
        one_agent = ball_agent(event, "1")
        normal = one_agent.initial.xyz[:2] - cue_agent.initial.xyz[:2]
        normal /= np.linalg.norm(normal)
        object_direction = one_agent.final.vel[:2] / np.linalg.norm(one_agent.final.vel[:2])
        angle_error = math.degrees(math.acos(float(np.clip(np.dot(normal, object_direction), -1.0, 1.0))))
        require(angle_error <= 2.0, "object ball left more than 2 degrees from line of centers")
        separation = float(np.linalg.norm(one_agent.initial.xyz - cue_agent.initial.xyz))
        close(separation, 2.0 * radius, 1e-6, "cut collision separation")
        p_before = mass * (cue_agent.initial.vel + one_agent.initial.vel)
        p_after = mass * (cue_agent.final.vel + one_agent.final.vel)
        momentum_error = float(np.linalg.norm(p_after - p_before))
        require(momentum_error <= 1e-10, "cut-shot momentum changed")
        return {
            "event_time_s": float(event.time),
            "object_direction_error_deg": angle_error,
            "contact_separation_m": separation,
            "momentum_error_kg_mps": momentum_error,
            "cue_post_velocity_mps": cue_agent.final.vel.tolist(),
            "object_post_velocity_mps": one_agent.final.vel.tolist(),
        }

    suite.run("cut_collision", "Oblique transfer, throw and no-overlap contact", cut_test)

    def cushion_test() -> dict[str, Any]:
        def run(spin: float):
            system = motion_system(
                {"cue": (0.350, 1.000)},
                {"cue": ((-1.0, 0.0, 0.0), (0.0, -1.0 / radius, spin), 3)},
                profile=profile, geometry=geometry,
            )
            event = first_event(system, "ball_linear_cushion")
            require(str(event.ids[1]) == "3", "wrong west cushion segment")
            return event, ball_agent(event, "cue")

        neutral_event, neutral = run(0.0)
        positive_event, positive = run(50.0)
        negative_event, negative = run(-50.0)
        ratio = abs(float(neutral.final.vel[0] / neutral.initial.vel[0]))
        target = float(profile["calibration"]["target_effective_normal_rebound_ratio"])
        tolerance = float(profile["calibration"]["target_effective_normal_rebound_tolerance"])
        close(ratio, target, tolerance, "effective cushion rebound")
        require(abs(float(neutral.final.vel[1])) <= 1e-9,
                "neutral rebound developed lateral velocity")
        close(float(positive.final.vel[0]), float(negative.final.vel[0]),
              1e-9, "mirrored spin normal response")
        close(float(positive.final.vel[1]), -float(negative.final.vel[1]),
              1e-9, "mirrored spin tangent response")
        angle = math.degrees(math.atan2(
            abs(float(positive.final.vel[1])), abs(float(positive.final.vel[0]))))
        require(angle >= 10.0, "sidespin cushion deflection is too small")
        return {
            "event_time_s": float(neutral_event.time),
            "effective_normal_rebound_ratio": ratio,
            "positive_spin_post_velocity_mps": positive.final.vel.tolist(),
            "negative_spin_post_velocity_mps": negative.final.vel.tolist(),
            "mirrored_exit_angle_deg": angle,
        }

    suite.run("cushion_spin", "Calibrated cushion restitution and mirrored English", cushion_test)

    def draw_follow_test() -> dict[str, Any]:
        displacements: dict[str, float] = {}
        for label, offset in (("draw", -0.40), ("stop", -0.10), ("follow", 0.20)):
            system = P.system_from_positions(
                {"cue": (0.635, 0.800), "1": (0.635, 1.300)},
                cue_state={"V0": 2.5, "phi": 90.0, "theta": 0.0,
                           "a": 0.0, "b": offset},
                profile=profile, geometry=geometry,
            )
            P.simulate(system, profile=profile)
            event = first_event(system, "ball_ball")
            states = pt.interpolate_ball_states(
                system.balls["cue"],
                [float(event.time), float(event.time) + 0.250],
                extrapolate=True,
            )
            displacements[label] = float(states[1].rvw[0, 1] - states[0].rvw[0, 1])
        require(displacements["draw"] <= -0.030, "draw did not reverse")
        require(abs(displacements["stop"]) <= 0.005, "stop shot did not stop")
        require(displacements["follow"] >= 0.060, "follow did not continue")
        return {"cue_displacement_0_25s_after_contact_m": displacements}

    suite.run("draw_stop_follow", "Vertical tip offsets produce draw, stop and follow", draw_follow_test)

    def pocket_test() -> dict[str, Any]:
        observations: dict[str, Any] = {}

        def rolling_shot(start, target=None, velocity=None):
            if velocity is None:
                direction = np.asarray(target, dtype=np.float64) - np.asarray(start, dtype=np.float64)
                direction /= np.linalg.norm(direction)
            else:
                direction = np.asarray(velocity, dtype=np.float64)
                direction /= np.linalg.norm(direction)
            omega = (-direction[1] / radius, direction[0] / radius, 0.0)
            return motion_system(
                {"cue": tuple(start)},
                {"cue": ((float(direction[0]), float(direction[1]), 0.0), omega, 3)},
                profile=profile, geometry=geometry,
            )

        corner = geometry["pockets"]["lb"]["center"][:2]
        capture = rolling_shot((0.300, 0.300), target=corner)
        capture_event = first_event(capture, "ball_pocket")
        require(str(capture_event.ids[1]) == "lb", "centered corner shot entered wrong pocket")
        observations["corner_capture_time_s"] = float(capture_event.time)

        reject_target = (
            corner[0] + 0.055 / math.sqrt(2.0),
            corner[1] - 0.055 / math.sqrt(2.0),
        )
        reject = rolling_shot((0.300, 0.300), target=reject_target)
        reject_events = [event for event in reject.events
                         if event.event_type.value == "ball_circular_cushion"]
        require([str(event.ids[1]) for event in reject_events[:2]] == ["1t", "2t"],
                "corner reject did not rattle through both jaws")
        require(not any(event.event_type.value == "ball_pocket" for event in reject.events),
                "corner reject was magnetically captured")
        observations["corner_reject_jaws"] = [str(event.ids[1]) for event in reject_events]

        side = geometry["pockets"]["lc"]["center"][:2]
        side_capture = rolling_shot((0.400, 1.270), target=side)
        side_event = first_event(side_capture, "ball_pocket")
        require(str(side_event.ids[1]) == "lc", "centered side shot entered wrong pocket")
        observations["side_capture_time_s"] = float(side_event.time)

        side_reject = rolling_shot((0.400, 1.325), velocity=(-1.0, 0.0))
        jaw_event = first_event(side_reject, "ball_circular_cushion")
        require(str(jaw_event.ids[1]) == "5t", "side reject missed the intended jaw")
        require(not any(event.event_type.value == "ball_pocket" for event in side_reject.events),
                "side reject was magnetically captured")
        observations["side_reject_jaw"] = str(jaw_event.ids[1])
        return observations

    suite.run("pocket_capture_reject", "Pocket acceptance and jaw rejection use the contract geometry", pocket_test)

    def no_tunneling_test() -> dict[str, Any]:
        cushion = motion_system(
            {"cue": (0.635, 1.000)},
            {"cue": ((-20.0, 0.0, 0.0), (0.0, -20.0 / radius, 0.0), 3)},
            profile=profile, geometry=geometry,
        )
        cushion_event = first_event(cushion, "ball_linear_cushion")
        cushion_agent = ball_agent(cushion_event, "cue")
        close(float(cushion_agent.initial.xyz[0]), radius, 1e-6,
              "high-speed cushion contact position")

        balls = motion_system(
            {"cue": (0.635, 0.300), "1": (0.635, 1.500)},
            {"cue": ((0.0, 20.0, 0.0), (-20.0 / radius, 0.0, 0.0), 3)},
            profile=profile, geometry=geometry,
        )
        collision = first_event(balls, "ball_ball")
        cue_agent = ball_agent(collision, "cue")
        one_agent = ball_agent(collision, "1")
        separation = float(np.linalg.norm(cue_agent.initial.xyz - one_agent.initial.xyz))
        close(separation, 2.0 * radius, 1e-6, "high-speed ball separation")
        return {
            "cushion_event_time_s": float(cushion_event.time),
            "cushion_contact_x_m": float(cushion_agent.initial.xyz[0]),
            "ball_event_time_s": float(collision.time),
            "ball_contact_separation_m": separation,
        }

    suite.run("continuous_collision_detection", "20 m/s cushion and ball contacts cannot tunnel", no_tunneling_test)

    break_cache: dict[str, Any] = {}

    def break_test() -> dict[str, Any]:
        system = P.control_break_system(profile, geometry)
        P.simulate(system, profile=profile)
        break_cache["system"] = system
        first_collision = first_event(system, "ball_ball")
        require(set(str(value) for value in first_collision.ids) == {"cue", "1"},
                "control break did not hit the apex ball first")
        stick = first_event(system, "stick_ball")
        cue_after = ball_agent(stick, "cue").final
        cue_speed = float(np.linalg.norm(cue_after.vel))
        close(cue_speed, float(profile["control_break"]["target_cue_ball_speed_mps"]),
              0.005, "control break cue-ball speed")
        displacements = {
            ball_id: float(np.linalg.norm(ball.state.rvw[0][:2] - ball.history[0].rvw[0][:2]))
            for ball_id, ball in system.balls.items() if ball_id != "cue"
        }
        moved = sum(value > 0.150 for value in displacements.values())
        mean_displacement = sum(displacements.values()) / len(displacements)
        rail_or_pocket = {
            str(event.ids[0]) for event in system.events
            if event.event_type.value in (
                "ball_linear_cushion", "ball_circular_cushion", "ball_pocket"
            ) and str(event.ids[0]) != "cue"
        }
        require(moved >= 12, "fewer than 12 object balls cleared 150 mm")
        require(mean_displacement >= 0.40, "mean rack spread is below 400 mm")
        require(len(rail_or_pocket) >= 4, "fewer than four object balls reached a rail/pocket")
        survivors = [ball for ball in system.balls.values() if int(ball.state.s) != 4]
        minimum_separation = min(
            float(np.linalg.norm(first.xyz - second.xyz))
            for index, first in enumerate(survivors)
            for second in survivors[index + 1:]
        )
        require(minimum_separation >= 2.0 * radius - 1e-6,
                "break ends with overlapping balls")
        ratios = resolved_energy_ratios(system)
        require(max(ratios, default=0.0) <= 1.0 + 1e-8,
                "a resolved contact increased mechanical energy")
        require(all(int(ball.state.s) in (0, 4) for ball in system.balls.values()),
                "break ended with unresolved moving balls")
        fingerprint, _payload = P.simulation_fingerprint(system)
        break_cache["fingerprint"] = fingerprint
        return {
            "duration_s": float(system.t),
            "event_count": len([event for event in system.events
                                if event.event_type.value != "none"]),
            "cue_ball_exit_speed_mps": cue_speed,
            "object_balls_over_0_15_m": moved,
            "mean_object_displacement_m": mean_displacement,
            "rail_or_pocket_object_balls": sorted(rail_or_pocket, key=int),
            "pocketed": sorted(
                (ball_id for ball_id, ball in system.balls.items() if int(ball.state.s) == 4),
                key=lambda value: (value != "cue", int(value) if value.isdigit() else -1),
            ),
            "minimum_final_separation_m": minimum_separation,
            "maximum_contact_energy_ratio": max(ratios, default=0.0),
            "canonical_sha256": fingerprint,
        }

    suite.run("control_break", "A sourced 24 mph control break disperses a legal tight rack", break_test)

    def wpa_travel_test() -> dict[str, Any]:
        speed = 6.0
        system = motion_system(
            {"cue": (0.635, 2.000)},
            {"cue": ((0.0, -speed, 0.0), (speed / radius, 0.0, 0.0), 3)},
            profile=profile, geometry=geometry,
        )
        points = [state.rvw[0][:2] for state in system.balls["cue"].history]
        distance = sum(float(np.linalg.norm(second - first))
                       for first, second in zip(points, points[1:]))
        table_lengths = distance / float(geometry["l"])
        require(table_lengths >= 4.0,
                "firm calibration stroke travels fewer than four table lengths")
        return {
            "initial_speed_mps": speed,
            "travel_distance_m": distance,
            "table_lengths": table_lengths,
            "cushion_contacts": sum(
                "cushion" in event.event_type.value for event in system.events),
        }

    suite.run("wpa_cushion_travel", "Firm center-ball stroke clears four table lengths", wpa_travel_test)

    def sampling_invariance_test() -> dict[str, Any]:
        hashes = {}
        for rate in (24, 30, 60, 240):
            system = P.system_from_positions(
                {"cue": (0.635, 0.800), "1": (0.635, 1.200)},
                profile=profile, geometry=geometry,
            )
            P.set_motion(system.balls["cue"],
                         (0.0, 1.0, 0.0), (-1.0 / radius, 0.0, 0.0), 3)
            P.simulate(system, profile=profile, continuous=True,
                       sample_rate_hz=rate)
            hashes[str(rate)] = P.simulation_fingerprint(system)[0]
        require(len(set(hashes.values())) == 1,
                "continuous sampling rate changed the authoritative solution")
        return {"hashes_by_hz": hashes, "unique_hashes": len(set(hashes.values()))}

    suite.run("sampling_invariance", "24/30/60/240 Hz sampling leaves the event solution unchanged", sampling_invariance_test)

    def trajectory_identity_test() -> dict[str, Any]:
        system = P.system_from_positions(
            {"cue": (0.635, 0.800), "1": (0.635, 1.200)},
            profile=profile, geometry=geometry,
        )
        P.set_motion(system.balls["cue"],
                     (0.0, 1.0, 0.0), (-1.0 / radius, 0.0, 0.0), 3)
        P.simulate(system, profile=profile)
        payload = P.export_trajectory(
            system,
            shot_id="trajectory_identity_probe",
            profile=profile,
            geometry=geometry,
            sample_rate_hz=120,
        )
        identity = P.verify_trajectory_sha256(payload)

        volatile = copy.deepcopy(payload)
        volatile["generated_utc"] = "2099-01-01T00:00:00+00:00"
        volatile["source_path"] = "/volatile/input.json"
        volatile["output_path"] = "/volatile/output.json"
        require(P.recompute_trajectory_sha256(volatile) == identity,
                "volatile timestamp/path metadata changed trajectory identity")

        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "schema": lambda row: row.__setitem__("schema", "tampered-schema"),
            "fixture": lambda row: row.__setitem__("shot_id", "tampered-fixture"),
            "sample_rate": lambda row: row.__setitem__(
                "sample_rate_hz", row["sample_rate_hz"] + 1),
            "duration": lambda row: row.__setitem__(
                "duration_s", row["duration_s"] + 1e-6),
            "ball_parameters": lambda row: row["ball_parameters"].__setitem__(
                "m", row["ball_parameters"]["m"] + 1e-6),
            "cue": lambda row: row["cue"].__setitem__(
                "mass_kg", row["cue"]["mass_kg"] + 1e-6),
            "rack": lambda row: row["rack"].__setitem__(
                "contact_gap_ratio", row["rack"]["contact_gap_ratio"] + 1e-6),
            "events_first": lambda row: row["events"][0].__setitem__(
                "time_s", row["events"][0]["time_s"] + 1e-9),
            "events_last": lambda row: row["events"][-1].__setitem__(
                "time_s", row["events"][-1]["time_s"] + 1e-9),
            "ball_samples_first": lambda row: row["balls"]["cue"]["samples"][0]["p"].__setitem__(
                0, row["balls"]["cue"]["samples"][0]["p"][0] + 1e-6),
            "ball_samples_last": lambda row: row["balls"]["1"]["samples"][-1]["q"].__setitem__(
                0, row["balls"]["1"]["samples"][-1]["q"][0] + 1e-6),
            "profile_hash": lambda row: row.__setitem__("profile_sha256", "0" * 64),
            "geometry_hash": lambda row: row.__setitem__(
                "geometry_contract_sha256", "0" * 64),
            "future_authoritative_field": lambda row: row.__setitem__(
                "future_authoritative_field", {"value": 1}),
        }
        changed = []
        for label, mutate in mutations.items():
            candidate = copy.deepcopy(payload)
            mutate(candidate)
            require(P.recompute_trajectory_sha256(candidate) != identity,
                    "%s is not covered by trajectory identity" % label)
            try:
                P.verify_trajectory_sha256(candidate)
            except ValueError:
                pass
            else:
                raise AssertionError("tampered %s passed digest verification" % label)
            changed.append(label)
        return {
            "trajectory_sha256": identity,
            "authoritative_mutations_detected": changed,
            "volatile_fields_ignored": sorted(
                P.TRAJECTORY_HASH_VOLATILE_FIELDS - {"trajectory_sha256"}
            ),
        }

    suite.run(
        "trajectory_identity",
        "Trajectory SHA covers every authoritative export field",
        trajectory_identity_test,
    )

    def orientation_collision_test() -> dict[str, Any]:
        system = P.system_from_positions(
            {"cue": (0.300, 1.270), "1": (0.700, 1.270)},
            profile=profile, geometry=geometry,
        )
        P.set_motion(system.balls["cue"],
                     (2.0, 0.0, 0.0), (0.0, 2.0 / radius, 0.0), 3)
        P.simulate(system, profile=profile)
        collision_time = float(first_event(system, "ball_ball").time)
        exports = {
            rate: P.export_trajectory(
                system,
                shot_id="orientation_collision_probe",
                profile=profile,
                geometry=geometry,
                sample_rate_hz=rate,
            )
            for rate in (240, 3840)
        }

        def sample(payload: dict[str, Any], ball_id: str, time_s: float) -> dict[str, Any]:
            row = min(
                payload["balls"][ball_id]["samples"],
                key=lambda value: abs(float(value["t"]) - time_s),
            )
            require(abs(float(row["t"]) - time_s) <= 5.1e-10,
                    "orientation probe timestamp is missing")
            return row

        def quaternion_error_deg(first: list[float], second: list[float]) -> float:
            a = np.asarray(first, dtype=np.float64)
            b = np.asarray(second, dtype=np.float64)
            cosine = abs(float(np.dot(a, b))) / float(np.linalg.norm(a) * np.linalg.norm(b))
            return math.degrees(2.0 * math.acos(float(np.clip(cosine, -1.0, 1.0))))

        event_sample = sample(exports[240], "1", collision_time)
        initial_q = exports[240]["balls"]["1"]["initial_quaternion_wxyz"]
        precontact_rotation = quaternion_error_deg(initial_q, event_sample["q"])
        require(precontact_rotation <= 1e-7,
                "object ball rotated before its instantaneous collision")
        require(float(np.linalg.norm(event_sample["v"])) > 0.1,
                "event sample is not the post-collision state")

        frame = 1.0 / 240.0
        probes = [
            math.floor(collision_time * 240.0) * frame,
            collision_time,
            math.ceil(collision_time * 240.0) * frame,
            (math.ceil(collision_time * 240.0) + 1.0) * frame,
        ]
        errors = {}
        for ball_id in ("cue", "1"):
            for index, time_s in enumerate(probes):
                key = "%s_probe_%d" % (ball_id, index)
                errors[key] = quaternion_error_deg(
                    sample(exports[240], ball_id, time_s)["q"],
                    sample(exports[3840], ball_id, time_s)["q"],
                )
        maximum_error = max(errors.values())
        require(maximum_error <= 0.01,
                "240 Hz orientation diverged from 3840 Hz around collision")
        return {
            "collision_time_s": collision_time,
            "probe_times_s": probes,
            "object_precontact_rotation_deg": precontact_rotation,
            "maximum_240_vs_3840_error_deg": maximum_error,
            "errors_deg": errors,
        }

    suite.run(
        "orientation_collision_integrity",
        "Collision-split quaternion integration matches a 16x reference",
        orientation_collision_test,
    )

    def repeatability_test() -> dict[str, Any]:
        first_hash = break_cache.get("fingerprint")
        hashes = [first_hash] if first_hash else []
        while len(hashes) < args.repeat:
            system = P.control_break_system(profile, geometry)
            P.simulate(system, profile=profile)
            hashes.append(P.simulation_fingerprint(system)[0])
        unique = sorted(set(hashes))
        require(len(unique) == 1, "control break produced more than one canonical hash")
        return {
            "runs": args.repeat,
            "unique_hash_count": len(unique),
            "canonical_sha256": unique[0],
        }

    suite.run("repeatability", "Fresh control-break systems repeat bit-for-bit", repeatability_test)

    summary = suite.summary()
    fixture = fixture_contract(profile)
    report = {
        "schema": "pool-physics-audit/v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if summary["failed"] == 0 else "FAIL",
        "provenance": P.provenance(profile),
        "parameters": {
            "ball": P.ball_parameter_kwargs(profile),
            "cue": profile["cue"],
            "resolver": {
                key: profile["solver"][key]
                for key in (
                    "ball_ball_model", "ball_ball_friction_model",
                    "linear_cushion_model", "circular_cushion_model",
                    "cushion_omega_ratio", "pocket_model",
                    "stick_ball_model", "transition_model",
                )
            },
        },
        "fixture_contract": fixture,
        "fixture_contract_sha256": P.canonical_sha256(fixture),
        "summary": summary,
        "tests": suite.tests,
        "repeatability": next(
            (row["observed"] for row in suite.tests if row["id"] == "repeatability"),
            {},
        ),
    }
    P.write_json(args.report, report)
    print("\nphysics audit: %d/%d passed -> %s" %
          (summary["passed"], summary["total"], args.report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
