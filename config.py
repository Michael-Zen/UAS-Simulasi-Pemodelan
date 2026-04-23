"""Central configuration for the F1 pit stop simulation project."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Tuple


DEFAULT_CIRCUIT_NAME = "Silverstone"

CIRCUITS: Dict[str, Dict[str, float]] = {
    "Silverstone": {
        "pit_lane_delta": 20.0,
        "base_lap_time": 90.0,
        "degradation_multiplier": 1.0,
        "total_laps": 52,
        "overtake_difficulty": 0.55,
        "rain_probability": 0.08,
    },
    "Monaco": {
        "pit_lane_delta": 28.0,
        "base_lap_time": 75.0,
        "degradation_multiplier": 0.7,
        "total_laps": 78,
        "overtake_difficulty": 0.95,
        "rain_probability": 0.05,
    },
    "Monza": {
        "pit_lane_delta": 18.0,
        "base_lap_time": 83.0,
        "degradation_multiplier": 0.8,
        "total_laps": 53,
        "overtake_difficulty": 0.45,
        "rain_probability": 0.06,
    },
    "Bahrain": {
        "pit_lane_delta": 22.0,
        "base_lap_time": 95.0,
        "degradation_multiplier": 1.4,
        "total_laps": 57,
        "overtake_difficulty": 0.60,
        "rain_probability": 0.01,
    },
    "Spa": {
        "pit_lane_delta": 19.0,
        "base_lap_time": 108.0,
        "degradation_multiplier": 1.1,
        "total_laps": 44,
        "overtake_difficulty": 0.50,
        "rain_probability": 0.15,
    },
    "Suzuka": {
        "pit_lane_delta": 21.0,
        "base_lap_time": 92.0,
        "degradation_multiplier": 1.05,
        "total_laps": 53,
        "overtake_difficulty": 0.58,
        "rain_probability": 0.12,
    },
}

# Legacy constants kept for backward compatibility with the original flat-module
# version of the project. They point to the default circuit preset.
CIRCUIT_NAME = DEFAULT_CIRCUIT_NAME
TOTAL_LAPS = int(CIRCUITS[CIRCUIT_NAME]["total_laps"])
BASE_LAP_TIME = float(CIRCUITS[CIRCUIT_NAME]["base_lap_time"])
PIT_LANE_DELTA = float(CIRCUITS[CIRCUIT_NAME]["pit_lane_delta"])


PIT_STOP_TIME_MEAN = 2.8
PIT_STOP_TIME_STD = 0.4
MIN_PIT_STOP_TIME = 2.0
MAX_PIT_STOP_TIME = 8.0

FUEL_EFFECT_PER_LAP = 0.03
LAP_TIME_VARIABILITY_STD = 0.15

SAFETY_CAR_PROBABILITY = 0.02
SAFETY_CAR_DURATION_MIN = 3
SAFETY_CAR_DURATION_MAX = 5
SAFETY_CAR_LAP_TIME = 120.0

VSC_PROBABILITY = 0.03
VSC_DURATION_MIN = 2
VSC_DURATION_MAX = 4
VSC_LAP_TIME = 130.0
TRAFFIC_GAP_THRESHOLD = 1.5
TRAFFIC_DELTA_RANGE = (0.2, 0.3)

MONTE_CARLO_ITERATIONS = 1000
RANDOM_SEED = 42


TIRE_COMPOUNDS: Dict[str, Dict[str, float]] = {
    "Soft": {
        "initial_grip": 1.00,
        "degradation_rate": 0.008,
        "cliff_point": 18,
        "cliff_penalty": 0.0030,
        "deg_exponent": 1.30,
        "optimal_temp": 102.0,
        "warmup_laps": 2,
        "temp_grip_factor": 0.055,
        "wet_condition_grip": 0.84,
        "dry_condition_grip": 1.00,
        "graining_peak_lap": 3.4,
        "graining_width": 1.15,
        "graining_gain": 0.012,
        "graining_dip": 0.008,
        "color": "#FF3333",
        "label": "Soft (S)",
    },
    "Medium": {
        "initial_grip": 0.97,
        "degradation_rate": 0.005,
        "cliff_point": 28,
        "cliff_penalty": 0.0020,
        "deg_exponent": 1.28,
        "optimal_temp": 99.0,
        "warmup_laps": 2,
        "temp_grip_factor": 0.045,
        "wet_condition_grip": 0.88,
        "dry_condition_grip": 0.97,
        "graining_peak_lap": 3.2,
        "graining_width": 1.20,
        "graining_gain": 0.010,
        "graining_dip": 0.006,
        "color": "#FFD700",
        "label": "Medium (M)",
    },
    "Hard": {
        "initial_grip": 0.94,
        "degradation_rate": 0.003,
        "cliff_point": 40,
        "cliff_penalty": 0.0015,
        "deg_exponent": 1.22,
        "optimal_temp": 96.0,
        "warmup_laps": 3,
        "temp_grip_factor": 0.040,
        "wet_condition_grip": 0.90,
        "dry_condition_grip": 0.94,
        "graining_peak_lap": 3.0,
        "graining_width": 1.25,
        "graining_gain": 0.008,
        "graining_dip": 0.005,
        "color": "#FFFFFF",
        "label": "Hard (H)",
    },
    "Intermediate": {
        "initial_grip": 0.95,
        "degradation_rate": 0.006,
        "cliff_point": 24,
        "cliff_penalty": 0.0024,
        "deg_exponent": 1.26,
        "optimal_temp": 82.0,
        "warmup_laps": 2,
        "temp_grip_factor": 0.050,
        "wet_condition_grip": 0.99,
        "dry_condition_grip": 0.84,
        "graining_peak_lap": 3.1,
        "graining_width": 1.15,
        "graining_gain": 0.009,
        "graining_dip": 0.006,
        "color": "#00CC66",
        "label": "Intermediate (I)",
    },
    "Wet": {
        "initial_grip": 0.91,
        "degradation_rate": 0.0075,
        "cliff_point": 20,
        "cliff_penalty": 0.0035,
        "deg_exponent": 1.24,
        "optimal_temp": 72.0,
        "warmup_laps": 2,
        "temp_grip_factor": 0.060,
        "wet_condition_grip": 1.04,
        "dry_condition_grip": 0.72,
        "graining_peak_lap": 2.9,
        "graining_width": 1.10,
        "graining_gain": 0.008,
        "graining_dip": 0.005,
        "color": "#0066FF",
        "label": "Wet (W)",
    },
}


STRATEGY_TEMPLATES: Dict[str, Dict[str, object]] = {
    "1-Stop: S->H": {
        "compounds": ["Soft", "Hard"],
        "pit_ratios": [18 / 52],
        "description": "Aggressive opening stint on Soft, then finish on Hard.",
    },
    "1-Stop: M->H": {
        "compounds": ["Medium", "Hard"],
        "pit_ratios": [25 / 52],
        "description": "Balanced one-stop with a long Hard final stint.",
    },
    "1-Stop: H->M": {
        "compounds": ["Hard", "Medium"],
        "pit_ratios": [30 / 52],
        "description": "Long opening Hard stint before switching to Medium.",
    },
    "2-Stop: S->M->H": {
        "compounds": ["Soft", "Medium", "Hard"],
        "pit_ratios": [14 / 52, 32 / 52],
        "description": "Classic two-stop: attack early, stabilize late.",
    },
    "2-Stop: S->H->M": {
        "compounds": ["Soft", "Hard", "Medium"],
        "pit_ratios": [14 / 52, 36 / 52],
        "description": "Front-load the pace, keep a fresh Medium for the end.",
    },
    "2-Stop: M->S->H": {
        "compounds": ["Medium", "Soft", "Hard"],
        "pit_ratios": [18 / 52, 34 / 52],
        "description": "Use Soft in the middle to attack the undercut window.",
    },
    "2-Stop: S->S->M": {
        "compounds": ["Soft", "Soft", "Medium"],
        "pit_ratios": [14 / 52, 28 / 52],
        "description": "Double Soft sprint before a stable Medium finish.",
    },
    "3-Stop: S->S->S->H": {
        "compounds": ["Soft", "Soft", "Soft", "Hard"],
        "pit_ratios": [12 / 52, 24 / 52, 36 / 52],
        "description": "Very aggressive triple-Soft approach.",
    },
    "3-Stop: S->M->S->M": {
        "compounds": ["Soft", "Medium", "Soft", "Medium"],
        "pit_ratios": [10 / 52, 24 / 52, 38 / 52],
        "description": "Alternating compounds for maximum pace flexibility.",
    },
}


def get_circuit_config(circuit_name: str | None = None) -> Dict[str, float]:
    """Return the resolved configuration for a circuit."""
    name = circuit_name or DEFAULT_CIRCUIT_NAME
    if name not in CIRCUITS:
        available = ", ".join(sorted(CIRCUITS))
        raise ValueError(f"Unknown circuit '{name}'. Available circuits: {available}")

    base_defaults = {
        "name": name,
        "pit_lane_delta": PIT_LANE_DELTA,
        "base_lap_time": BASE_LAP_TIME,
        "degradation_multiplier": 1.0,
        "total_laps": TOTAL_LAPS,
        "overtake_difficulty": 0.60,
        "rain_probability": 0.0,
    }
    resolved = deepcopy(base_defaults)
    resolved.update(deepcopy(CIRCUITS[name]))
    resolved["name"] = name
    return resolved


def get_circuit_names() -> List[str]:
    """Return all supported circuit names."""
    return list(CIRCUITS.keys())


def _scaled_pit_lap(ratio: float, total_laps: int, previous_lap: int) -> int:
    pit_lap = int(round(total_laps * ratio))
    pit_lap = max(previous_lap + 5, pit_lap)
    pit_lap = min(total_laps - 1, pit_lap)
    return pit_lap


def build_strategy(template_name: str, circuit_name: str | None = None) -> Dict[str, object]:
    """Build a concrete strategy definition for the selected circuit."""
    if template_name not in STRATEGY_TEMPLATES:
        available = ", ".join(sorted(STRATEGY_TEMPLATES))
        raise ValueError(f"Unknown strategy template '{template_name}'. Available: {available}")

    template = STRATEGY_TEMPLATES[template_name]
    circuit = get_circuit_config(circuit_name)
    total_laps = int(circuit["total_laps"])

    pit_laps: List[int] = []
    previous_pit_lap = 0
    for ratio in template["pit_ratios"]:
        pit_lap = _scaled_pit_lap(float(ratio), total_laps, previous_pit_lap)
        pit_laps.append(pit_lap)
        previous_pit_lap = pit_lap

    stints: List[Tuple[str, int, int]] = []
    stint_start = 1
    for index, compound in enumerate(template["compounds"]):
        if index < len(pit_laps):
            stint_end = pit_laps[index]
        else:
            stint_end = total_laps
        stints.append((compound, stint_start, stint_end))
        stint_start = stint_end + 1

    return {
        "stints": stints,
        "description": template["description"],
    }


def get_strategies(circuit_name: str | None = None) -> Dict[str, Dict[str, object]]:
    """Return all strategy definitions for the selected circuit."""
    return {
        name: build_strategy(name, circuit_name)
        for name in STRATEGY_TEMPLATES
    }


# Backward-compatible default strategy mapping.
STRATEGIES = get_strategies()

