"""Single-car lap-by-lap race simulator."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import (
    FUEL_EFFECT_PER_LAP,
    LAP_TIME_VARIABILITY_STD,
    MAX_PIT_STOP_TIME,
    MIN_PIT_STOP_TIME,
    PIT_STOP_TIME_MEAN,
    PIT_STOP_TIME_STD,
    SAFETY_CAR_DURATION_MAX,
    SAFETY_CAR_DURATION_MIN,
    SAFETY_CAR_LAP_TIME,
    SAFETY_CAR_PROBABILITY,
    TIRE_COMPOUNDS,
    get_circuit_config,
)
from core.strategy import Strategy
from core.track_maps import get_track_map
from core.tire_model import Tire


class RaceSimulator:
    """Simulate one driver over a full race distance."""

    def __init__(
        self,
        strategy: Strategy,
        circuit_name: str = "Silverstone",
        enable_variability: bool = True,
        enable_safety_car: bool = True,
        random_seed: Optional[int] = None,
        track_wetness: float = 0.0,
        simulation_overrides: Optional[Dict[str, object]] = None,
    ) -> None:
        self.strategy = strategy
        self.circuit_config = get_circuit_config(circuit_name)
        self.circuit_name = self.circuit_config["name"]
        self.total_laps = strategy.total_laps
        if self.total_laps != int(self.circuit_config["total_laps"]):
            raise ValueError(
                f"Strategy '{strategy.name}' was built for {strategy.total_laps} laps, "
                f"but circuit '{self.circuit_name}' uses {self.circuit_config['total_laps']} laps."
            )

        self.base_lap_time = float(
            simulation_overrides.get("base_lap_time", self.circuit_config["base_lap_time"])
            if simulation_overrides
            else self.circuit_config["base_lap_time"]
        )
        self.enable_variability = enable_variability
        self.enable_safety_car = enable_safety_car
        self.track_wetness = float(np.clip(track_wetness, 0.0, 1.0))
        self.simulation_overrides = simulation_overrides or {}
        self.rng = np.random.default_rng(random_seed)

        self.race_data: Optional[pd.DataFrame] = None
        self.total_race_time: Optional[float] = None
        self.safety_car_laps: list[int] = []

    def _setting(self, key: str, default):
        return self.simulation_overrides.get(key, default)

    @staticmethod
    def _health_to_color(health_pct: float) -> str:
        ratio = float(np.clip(health_pct, 0.0, 100.0)) / 100.0
        red = int(round(255 * (1.0 - ratio)))
        green = int(round(255 * ratio))
        return f"#{red:02X}{green:02X}33"

    def _build_track_map(self) -> Dict[str, object]:
        resolved_track_map = get_track_map(self.circuit_name)
        if resolved_track_map and resolved_track_map.get("path"):
            return resolved_track_map

        # Fallback oval map keeps telemetry usable for circuits without custom geometry.
        length_by_circuit = {
            "Silverstone": 5891,
            "Monaco": 3337,
            "Monza": 5793,
            "Bahrain": 5412,
            "Spa": 7004,
            "Suzuka": 5807,
        }
        radius_x_by_circuit = {
            "Silverstone": 0.46,
            "Monaco": 0.43,
            "Monza": 0.49,
            "Bahrain": 0.47,
            "Spa": 0.50,
        }
        radius_x = radius_x_by_circuit.get(self.circuit_name, 0.46)
        radius_y = 0.36
        points = []
        for angle in np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False):
            x = 0.5 + radius_x * np.cos(angle)
            y = 0.5 + radius_y * np.sin(angle)
            points.append({"x": round(float(x), 5), "y": round(float(y), 5)})

        return {
            "circuit": self.circuit_name,
            "length_m": int(length_by_circuit.get(self.circuit_name, 5500)),
            "pit_entry_progress": 0.72,
            "pit_exit_progress": 0.93,
            "source": "fallback_oval",
            "path": points,
        }

    def generate_telemetry(
        self,
        timestep_s: float = 0.5,
        max_points: Optional[int] = None,
    ) -> Dict[str, object]:
        if self.race_data is None:
            raise RuntimeError("Simulation has not been run yet.")

        dt = float(np.clip(timestep_s, 0.1, 2.0))
        track_map = self._build_track_map()
        track_length = float(track_map["length_m"])
        pit_entry_progress = float(track_map.get("pit_entry_progress", 0.72))
        pit_exit_progress = float(track_map.get("pit_exit_progress", 0.93))
        if pit_exit_progress < pit_entry_progress:
            pit_window_contains = lambda progress: progress >= pit_entry_progress or progress <= pit_exit_progress
        else:
            pit_window_contains = lambda progress: pit_entry_progress <= progress <= pit_exit_progress
        raw_telemetry: List[Dict[str, object]] = []

        current_time = 0.0
        for lap_row in self.race_data.itertuples(index=False):
            lap = int(lap_row.lap)
            lap_time = float(lap_row.final_lap_time)
            tire_age = int(lap_row.tire_age)
            compound = str(lap_row.compound)
            estimated_temp = float(lap_row.estimated_temp)
            grip = float(lap_row.grip)
            is_pit_lap = bool(lap_row.is_pit_lap)
            cliff_point = max(int(TIRE_COMPOUNDS[compound]["cliff_point"]), 1)
            optimal_temp = float(TIRE_COMPOUNDS[compound]["optimal_temp"])

            steps = max(int(np.ceil(lap_time / dt)), 2)
            for step in range(steps):
                progress_in_lap = step / max(steps - 1, 1)

                # Phase-based profile keeps signals smooth while remaining deterministic.
                phase = 2.0 * np.pi * progress_in_lap
                raw_throttle = 0.76 + 0.24 * np.sin((phase * 2.8) + 0.35)
                brake = np.clip(0.85 * np.maximum(0.0, np.sin((phase * 2.8) - 1.15)), 0.0, 1.0)
                throttle = np.clip(raw_throttle * (1.0 - (0.65 * brake)), 0.0, 1.0)

                dynamic_temp = estimated_temp + 18.0 * (throttle - 0.55) + 12.0 * brake
                tire_temp = float(np.clip(dynamic_temp, 60.0, 150.0))

                wear_pct = float(np.clip((tire_age / (cliff_point + 8)) * 100.0, 0.0, 100.0))
                overheat_penalty = max(0.0, tire_temp - optimal_temp) * 0.45
                grip_penalty = max(0.0, (1.0 - grip) * 100.0)
                health_pct = float(np.clip(100.0 - wear_pct - overheat_penalty - grip_penalty, 0.0, 100.0))

                speed_kmh = float(np.clip(140.0 + 220.0 * throttle - 125.0 * brake, 60.0, 340.0))
                race_progress = ((lap - 1) + progress_in_lap) / max(self.total_laps, 1)
                s_on_track_m = float(race_progress * track_length)

                in_pit_window = bool(is_pit_lap and pit_window_contains(progress_in_lap))
                raw_telemetry.append(
                    {
                        "t": round(current_time + (progress_in_lap * lap_time), 3),
                        "lap": lap,
                        "lap_progress": round(progress_in_lap, 5),
                        "race_progress": round(race_progress, 5),
                        "s_on_track_m": round(s_on_track_m, 3),
                        "compound": compound,
                        "tire_age": tire_age,
                        "throttle": round(float(throttle), 4),
                        "brake": round(float(brake), 4),
                        "speed_kmh": round(speed_kmh, 3),
                        "tire_temp_c": round(tire_temp, 3),
                        "tire_wear_pct": round(wear_pct, 3),
                        "tire_health_pct": round(health_pct, 3),
                        "tire_health_color": self._health_to_color(health_pct),
                        "in_pit": in_pit_window,
                    }
                )

            current_time += lap_time

        returned_telemetry = raw_telemetry
        raw_points = len(raw_telemetry)
        downsample_factor = 1
        if max_points is not None:
            target_points = max(int(max_points), 1)
            if raw_points > target_points:
                downsample_factor = int(np.ceil(raw_points / target_points))
                returned_telemetry = raw_telemetry[::downsample_factor]

        return {
            "track_map": track_map,
            "channels": {
                "t": {"unit": "s", "label": "Race Time"},
                "lap": {"unit": "lap", "label": "Lap Number"},
                "lap_progress": {"unit": "ratio", "label": "Lap Progress"},
                "race_progress": {"unit": "ratio", "label": "Race Progress"},
                "s_on_track_m": {"unit": "m", "label": "Distance Along Track"},
                "speed_kmh": {"unit": "km/h", "label": "Speed"},
                "throttle": {"unit": "ratio", "label": "Throttle"},
                "brake": {"unit": "ratio", "label": "Brake"},
                "tire_temp_c": {"unit": "C", "label": "Tyre Temperature"},
                "tire_wear_pct": {"unit": "%", "label": "Tyre Wear"},
                "tire_health_pct": {"unit": "%", "label": "Tyre Health"},
                "tire_health_color": {"unit": "hex", "label": "Tyre Health Color"},
                "in_pit": {"unit": "bool", "label": "Pit Lane Flag"},
            },
            "telemetry": returned_telemetry,
            "sampling": {
                "requested_timestep_s": timestep_s,
                "applied_timestep_s": dt,
                "raw_points": raw_points,
                "returned_points": len(returned_telemetry),
                "downsample_factor": downsample_factor,
            },
        }

    def _resolve_compound_data(self, compound: str) -> Dict[str, float]:
        compound_overrides = self.simulation_overrides.get("compound_overrides", {})
        if compound in compound_overrides:
            merged = deepcopy(TIRE_COMPOUNDS[compound])
            merged.update(compound_overrides[compound])
            return merged
        return deepcopy(TIRE_COMPOUNDS[compound])

    def _calculate_fuel_effect(self, lap: int) -> float:
        return float(self._setting("fuel_effect_per_lap", FUEL_EFFECT_PER_LAP)) * (lap - 1)

    def _calculate_pit_stop_time(self) -> float:
        pit_lane_delta = float(self._setting("pit_lane_delta", self.circuit_config["pit_lane_delta"]))
        mean = float(self._setting("pit_stop_time_mean", PIT_STOP_TIME_MEAN))
        std = float(self._setting("pit_stop_time_std", PIT_STOP_TIME_STD))
        minimum = float(self._setting("min_pit_stop_time", MIN_PIT_STOP_TIME))
        maximum = float(self._setting("max_pit_stop_time", MAX_PIT_STOP_TIME))

        if self.enable_variability:
            stationary_time = float(self.rng.normal(mean, std))
            stationary_time = float(np.clip(stationary_time, minimum, maximum))
        else:
            stationary_time = mean

        return pit_lane_delta + stationary_time

    def _check_safety_car(self) -> bool:
        if not self.enable_safety_car:
            return False
        probability = float(self._setting("safety_car_probability", SAFETY_CAR_PROBABILITY))
        return bool(self.rng.random() < probability)

    def simulate(self) -> pd.DataFrame:
        data = {
            "lap": [],
            "compound": [],
            "tire_age": [],
            "grip": [],
            "estimated_temp": [],
            "base_lap_time": [],
            "degraded_lap_time": [],
            "fuel_effect": [],
            "noise": [],
            "pit_stop_loss": [],
            "is_pit_lap": [],
            "safety_car": [],
            "final_lap_time": [],
            "cumulative_time": [],
        }

        cumulative_time = 0.0
        pit_stop_laps = set(self.strategy.get_pit_stop_laps())
        self.safety_car_laps = []
        safety_car_remaining = 0
        degradation_multiplier = float(self.circuit_config["degradation_multiplier"])

        for lap in range(1, self.total_laps + 1):
            compound = self.strategy.get_compound_at_lap(lap)
            tire_age = self.strategy.get_tire_age_at_lap(lap)

            compound_data = self._resolve_compound_data(compound)
            compound_data["degradation_rate"] *= degradation_multiplier
            tire = Tire(compound, track_wetness=self.track_wetness, compound_data=compound_data)

            grip = tire.get_grip(age=tire_age, track_wetness=self.track_wetness)
            estimated_temp = tire.estimate_temperature(age=tire_age)
            degraded_lap_time = tire.get_lap_time(
                base_time=self.base_lap_time,
                age=tire_age,
                track_wetness=self.track_wetness,
            )

            fuel_effect = self._calculate_fuel_effect(lap)
            variability_std = float(self._setting("lap_time_variability_std", LAP_TIME_VARIABILITY_STD))
            noise = float(self.rng.normal(0.0, variability_std)) if self.enable_variability else 0.0

            is_pit_lap = lap in pit_stop_laps
            pit_stop_loss = self._calculate_pit_stop_time() if is_pit_lap else 0.0

            is_safety_car = False
            if safety_car_remaining > 0:
                is_safety_car = True
                safety_car_remaining -= 1
            elif self._check_safety_car():
                is_safety_car = True
                duration_min = int(self._setting("safety_car_duration_min", SAFETY_CAR_DURATION_MIN))
                duration_max = int(self._setting("safety_car_duration_max", SAFETY_CAR_DURATION_MAX))
                duration = int(self.rng.integers(duration_min, duration_max + 1))
                safety_car_remaining = duration - 1

            if is_safety_car:
                self.safety_car_laps.append(lap)
                final_lap_time = float(self._setting("safety_car_lap_time", SAFETY_CAR_LAP_TIME)) + pit_stop_loss
            else:
                final_lap_time = degraded_lap_time - fuel_effect + noise + pit_stop_loss

            cumulative_time += final_lap_time

            data["lap"].append(lap)
            data["compound"].append(compound)
            data["tire_age"].append(tire_age)
            data["grip"].append(grip)
            data["estimated_temp"].append(estimated_temp)
            data["base_lap_time"].append(self.base_lap_time)
            data["degraded_lap_time"].append(degraded_lap_time)
            data["fuel_effect"].append(fuel_effect)
            data["noise"].append(noise)
            data["pit_stop_loss"].append(pit_stop_loss)
            data["is_pit_lap"].append(is_pit_lap)
            data["safety_car"].append(is_safety_car)
            data["final_lap_time"].append(final_lap_time)
            data["cumulative_time"].append(cumulative_time)

        self.race_data = pd.DataFrame(data)
        self.total_race_time = float(cumulative_time)
        return self.race_data

    def get_summary(self) -> Dict[str, object]:
        if self.race_data is None or self.total_race_time is None:
            raise RuntimeError("Simulation has not been run yet.")

        normal_laps = self.race_data[(~self.race_data["safety_car"]) & (~self.race_data["is_pit_lap"])]
        return {
            "strategy_name": self.strategy.name,
            "circuit_name": self.circuit_name,
            "total_race_time": self.total_race_time,
            "total_race_time_formatted": self._format_time(self.total_race_time),
            "num_pit_stops": self.strategy.num_stops,
            "avg_lap_time": float(normal_laps["final_lap_time"].mean()) if not normal_laps.empty else 0.0,
            "fastest_lap": float(normal_laps["final_lap_time"].min()) if not normal_laps.empty else 0.0,
            "slowest_lap": float(normal_laps["final_lap_time"].max()) if not normal_laps.empty else 0.0,
            "total_pit_time_lost": float(self.race_data["pit_stop_loss"].sum()),
            "safety_car_laps": len(self.safety_car_laps),
            "stints": self.strategy.get_stint_info(),
        }

    @staticmethod
    def _format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:06.3f}"
        return f"{minutes}:{secs:06.3f}"

    def __repr__(self) -> str:
        status = "completed" if self.race_data is not None else "not-started"
        return f"RaceSimulator(strategy='{self.strategy.name}', circuit='{self.circuit_name}', status={status})"

