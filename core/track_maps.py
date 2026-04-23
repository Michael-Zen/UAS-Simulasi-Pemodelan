"""Normalized track-map geometry used by telemetry minimap rendering."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DERIVED_POINTS_PATH = os.path.join(ROOT_DIR, "_external", "generated_track_points.json")


def _clamp_point(point: Point) -> Dict[str, float]:
    x, y = point
    x = min(max(float(x), 0.02), 0.98)
    y = min(max(float(y), 0.02), 0.98)
    return {"x": round(x, 5), "y": round(y, 5)}


def _densify_closed_path(control_points: List[Point], samples_per_segment: int = 5) -> List[Dict[str, float]]:
    if len(control_points) < 3:
        return [_clamp_point(point) for point in control_points]

    path: List[Dict[str, float]] = []
    total_points = len(control_points)
    for index in range(total_points):
        start_x, start_y = control_points[index]
        end_x, end_y = control_points[(index + 1) % total_points]
        for step in range(samples_per_segment):
            ratio = step / float(samples_per_segment)
            x = start_x + ((end_x - start_x) * ratio)
            y = start_y + ((end_y - start_y) * ratio)
            path.append(_clamp_point((x, y)))

    return path


def _load_svg_derived_control_points() -> Dict[str, List[Point]]:
    if not os.path.exists(SVG_DERIVED_POINTS_PATH):
        return {}
    try:
        with open(SVG_DERIVED_POINTS_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    parsed: Dict[str, List[Point]] = {}
    for circuit_name, points in payload.items():
        if not isinstance(points, list):
            continue
        parsed_points: List[Point] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                continue
            parsed_points.append((float(point[0]), float(point[1])))
        if parsed_points:
            parsed[circuit_name] = parsed_points
    return parsed


MONACO_CONTROL_POINTS: List[Point] = [
    (0.18942, 0.49415),
    (0.17383, 0.49921),
    (0.15982, 0.51614),
    (0.14318, 0.54606),
    (0.13468, 0.58160),
    (0.13483, 0.62650),
    (0.14158, 0.64251),
    (0.16275, 0.65021),
    (0.17534, 0.65908),
    (0.18478, 0.69315),
    (0.19653, 0.74126),
    (0.19747, 0.75599),
    (0.17986, 0.76507),
    (0.17089, 0.77369),
    (0.17921, 0.79797),
    (0.19768, 0.83269),
    (0.23891, 0.87089),
    (0.26950, 0.88214),
    (0.28986, 0.88954),
    (0.29498, 0.90389),
    (0.28769, 0.91079),
    (0.23286, 0.91930),
    (0.19256, 0.92000),
    (0.18713, 0.91490),
    (0.18775, 0.90072),
    (0.17864, 0.88519),
    (0.15781, 0.86175),
    (0.12804, 0.80864),
    (0.10026, 0.74186),
    (0.08812, 0.69077),
    (0.08060, 0.63808),
    (0.08000, 0.56797),
    (0.09448, 0.52643),
    (0.10238, 0.50514),
    (0.10177, 0.48752),
    (0.11224, 0.47847),
    (0.16867, 0.47061),
    (0.21618, 0.46606),
    (0.26760, 0.45878),
    (0.30927, 0.44983),
    (0.36544, 0.43981),
    (0.41215, 0.43325),
    (0.45355, 0.42079),
    (0.49775, 0.40475),
    (0.53247, 0.39676),
    (0.56978, 0.39044),
    (0.60491, 0.38539),
    (0.64080, 0.37836),
    (0.68404, 0.34752),
    (0.68967, 0.30371),
    (0.66049, 0.27229),
    (0.63745, 0.25412),
    (0.62906, 0.23726),
    (0.63523, 0.21943),
    (0.66328, 0.19011),
    (0.72600, 0.12626),
    (0.76656, 0.08534),
    (0.78043, 0.08000),
    (0.79493, 0.08676),
    (0.80590, 0.09747),
    (0.80594, 0.11328),
    (0.81060, 0.12662),
    (0.81915, 0.13641),
    (0.82900, 0.14671),
    (0.83630, 0.15670),
    (0.84472, 0.16627),
    (0.85911, 0.16527),
    (0.86357, 0.15532),
    (0.85466, 0.14696),
    (0.84710, 0.14169),
    (0.83694, 0.13037),
    (0.82780, 0.12008),
    (0.82509, 0.10554),
    (0.84703, 0.09454),
    (0.88446, 0.08596),
    (0.90581, 0.08401),
    (0.92000, 0.09866),
    (0.91911, 0.12678),
    (0.91612, 0.15368),
    (0.89794, 0.22522),
    (0.84312, 0.30726),
    (0.76892, 0.36590),
    (0.70910, 0.40034),
    (0.64455, 0.42524),
    (0.58894, 0.44051),
    (0.52999, 0.44811),
    (0.48400, 0.45307),
    (0.47679, 0.45973),
    (0.47583, 0.46827),
    (0.46601, 0.47221),
    (0.44295, 0.47497),
    (0.43418, 0.46888),
    (0.42406, 0.46770),
    (0.36167, 0.47466),
    (0.23952, 0.48845),
    (0.18942, 0.49415),
]

SVG_DERIVED_CONTROL_POINTS = _load_svg_derived_control_points()

BAHRAIN_CONTROL_POINTS: List[Point] = SVG_DERIVED_CONTROL_POINTS.get("Bahrain", [])
MONZA_CONTROL_POINTS: List[Point] = SVG_DERIVED_CONTROL_POINTS.get("Monza", [])
SILVERSTONE_CONTROL_POINTS: List[Point] = SVG_DERIVED_CONTROL_POINTS.get("Silverstone", [])
SPA_CONTROL_POINTS: List[Point] = SVG_DERIVED_CONTROL_POINTS.get("Spa", [])

SUZUKA_CONTROL_POINTS: List[Point] = [
    (0.79, 0.24),
    (0.88, 0.28),
    (0.92, 0.38),
    (0.88, 0.48),
    (0.79, 0.55),
    (0.68, 0.54),
    (0.58, 0.48),
    (0.49, 0.43),
    (0.42, 0.48),
    (0.36, 0.58),
    (0.29, 0.68),
    (0.20, 0.72),
    (0.12, 0.66),
    (0.10, 0.54),
    (0.16, 0.43),
    (0.25, 0.36),
    (0.36, 0.33),
    (0.47, 0.34),
    (0.56, 0.37),
    (0.63, 0.30),
    (0.66, 0.20),
    (0.59, 0.13),
    (0.47, 0.10),
    (0.35, 0.12),
    (0.26, 0.18),
    (0.28, 0.25),
    (0.40, 0.27),
    (0.53, 0.28),
    (0.66, 0.25),
]
SUZUKA_CONTROL_POINTS = SVG_DERIVED_CONTROL_POINTS.get("Suzuka", SUZUKA_CONTROL_POINTS)

REALISTIC_TRACK_MAPS: Dict[str, Dict[str, object]] = {
    "Silverstone": {
        "circuit": "Silverstone",
        "length_m": 5891,
        "pit_entry_progress": 0.87,
        "pit_exit_progress": 0.04,
        "source": "f1-circuits-svg:silverstone-8:cc-by-4.0",
        "path": _densify_closed_path(SILVERSTONE_CONTROL_POINTS, samples_per_segment=4),
    },
    "Monaco": {
        "circuit": "Monaco",
        "length_m": 3337,
        "pit_entry_progress": 0.97,
        "pit_exit_progress": 0.03,
        "source": "f1-circuits-svg:monaco-6:cc-by-4.0",
        "path": _densify_closed_path(MONACO_CONTROL_POINTS, samples_per_segment=4),
    },
    "Monza": {
        "circuit": "Monza",
        "length_m": 5793,
        "pit_entry_progress": 0.84,
        "pit_exit_progress": 0.07,
        "source": "f1-circuits-svg:monza-7:cc-by-4.0",
        "path": _densify_closed_path(MONZA_CONTROL_POINTS, samples_per_segment=4),
    },
    "Bahrain": {
        "circuit": "Bahrain",
        "length_m": 5412,
        "pit_entry_progress": 0.92,
        "pit_exit_progress": 0.05,
        "source": "f1-circuits-svg:bahrain-1:cc-by-4.0",
        "path": _densify_closed_path(BAHRAIN_CONTROL_POINTS, samples_per_segment=4),
    },
    "Spa": {
        "circuit": "Spa",
        "length_m": 7004,
        "pit_entry_progress": 0.95,
        "pit_exit_progress": 0.04,
        "source": "f1-circuits-svg:spa-francorchamps-4:cc-by-4.0",
        "path": _densify_closed_path(SPA_CONTROL_POINTS, samples_per_segment=4),
    },
    "Suzuka": {
        "circuit": "Suzuka",
        "length_m": 5807,
        "pit_entry_progress": 0.91,
        "pit_exit_progress": 0.05,
        "source": "f1-circuits-svg:suzuka-2:cc-by-4.0",
        "path": _densify_closed_path(SUZUKA_CONTROL_POINTS, samples_per_segment=4),
    },
}


def get_track_map(circuit_name: str) -> Optional[Dict[str, object]]:
    track_map = REALISTIC_TRACK_MAPS.get(circuit_name)
    if not track_map:
        return None
    return deepcopy(track_map)

