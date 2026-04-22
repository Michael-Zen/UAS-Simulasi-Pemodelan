"""Single-car lap-by-lap race simulator."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config import (
    BASE_LAP_TIME,
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

