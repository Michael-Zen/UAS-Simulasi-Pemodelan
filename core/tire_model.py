"""Tyre degradation, thermal behaviour, and grip model."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Dict, Optional

import numpy as np

from config import BASE_LAP_TIME, TIRE_COMPOUNDS


class Tire:
    """Represent a single tyre set with degradation, thermal, and graining."""

    def __init__(
        self,
        compound: str,
        track_wetness: float = 0.0,
        compound_data: Optional[Dict[str, float]] = None,
    ) -> None:
        if compound not in TIRE_COMPOUNDS and compound_data is None:
            available = ", ".join(sorted(TIRE_COMPOUNDS))
            raise ValueError(f"Unknown compound '{compound}'. Available compounds: {available}")

        params = deepcopy(compound_data or TIRE_COMPOUNDS[compound])
        self.compound = compound
        self.initial_grip = params["initial_grip"]
        self.degradation_rate = params["degradation_rate"]
        self.cliff_point = int(params["cliff_point"])
        self.cliff_penalty = params["cliff_penalty"]
        self.deg_exponent = params["deg_exponent"]
        self.optimal_temp = params["optimal_temp"]
        self.warmup_laps = int(params["warmup_laps"])
        self.temp_grip_factor = params["temp_grip_factor"]
        self.wet_condition_grip = params.get("wet_condition_grip", self.initial_grip)
        self.dry_condition_grip = params.get("dry_condition_grip", self.initial_grip)
        self.graining_peak_lap = params.get("graining_peak_lap", 3.0)
        self.graining_width = params.get("graining_width", 1.2)
        self.graining_gain = params.get("graining_gain", 0.0)
        self.graining_dip = params.get("graining_dip", 0.0)
        self.color = params.get("color", "#FFFFFF")
        self.label = params.get("label", compound)
        self.track_wetness = float(np.clip(track_wetness, 0.0, 1.0))
        self.tire_age = 0

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def estimate_temperature(self, age: Optional[int] = None) -> float:
        """Estimate tyre temperature from age using a smooth warm-up curve."""
        resolved_age = self.tire_age if age is None else age
        if self.warmup_laps <= 0:
            return self.optimal_temp

        progress = self._sigmoid((resolved_age - (self.warmup_laps - 1) / 2.0) * 3.0)
        base_fraction = 0.72
        return self.optimal_temp * (base_fraction + (1.0 - base_fraction) * progress)

    def _temperature_factor(
        self,
        age: int,
        tire_temp: Optional[float] = None,
    ) -> float:
        current_temp = tire_temp if tire_temp is not None else self.estimate_temperature(age)
        temp_offset = abs(current_temp - self.optimal_temp)

        # Penalty grows sigmoidally as the tyre temperature moves away from the
        # optimal window.
        temp_penalty = self.temp_grip_factor * self._sigmoid((temp_offset - 5.0) / 1.8)
        factor = 1.0 - temp_penalty

        # Newly fitted tyres need 2-3 laps to fully switch on.
        if age < self.warmup_laps:
            warmup_progress = self._sigmoid(((age + 1) / max(self.warmup_laps, 1) - 0.5) * 6.0)
            warmup_factor = 1.0 - self.temp_grip_factor * (1.0 - warmup_progress)
            factor *= warmup_factor

        return max(factor, 0.85)

    def _condition_factor(self, track_wetness: Optional[float] = None) -> float:
        wetness = self.track_wetness if track_wetness is None else float(np.clip(track_wetness, 0.0, 1.0))
        return (self.dry_condition_grip * (1.0 - wetness)) + (self.wet_condition_grip * wetness)

    def _graining_adjustment(self, age: int) -> float:
        early_dip_center = 1.5
        early_dip = self.graining_dip * math.exp(
            -0.5 * ((age - early_dip_center) / max(self.graining_width * 0.8, 0.5)) ** 2
        )
        later_bump = self.graining_gain * math.exp(
            -0.5 * ((age - self.graining_peak_lap) / max(self.graining_width, 0.5)) ** 2
        )
        return later_bump - early_dip

    def get_grip(
        self,
        age: Optional[int] = None,
        track_wetness: Optional[float] = None,
        tire_temp: Optional[float] = None,
    ) -> float:
        """Return grip level for a tyre age while keeping the original API intact."""
        resolved_age = self.tire_age if age is None else int(age)
        base_degradation = self.degradation_rate * (resolved_age ** self.deg_exponent)
        grip = self.initial_grip - base_degradation

        if resolved_age > self.cliff_point:
            cliff_degradation = self.cliff_penalty * ((resolved_age - self.cliff_point) ** 2)
            grip -= cliff_degradation

        grip += self._graining_adjustment(resolved_age)
        grip *= self._condition_factor(track_wetness)
        grip *= self._temperature_factor(resolved_age, tire_temp)

        return max(grip, 0.50)

    def get_lap_time(
        self,
        base_time: float = BASE_LAP_TIME,
        age: Optional[int] = None,
        track_wetness: Optional[float] = None,
        tire_temp: Optional[float] = None,
    ) -> float:
        """Return lap time for a tyre state while remaining backward compatible."""
        grip = self.get_grip(age=age, track_wetness=track_wetness, tire_temp=tire_temp)
        return base_time / grip

    def get_degradation_curve(
        self,
        max_laps: int = 50,
        track_wetness: Optional[float] = None,
    ) -> Dict[str, np.ndarray]:
        """Return lap-wise grip, temperature, and lap-time data for plotting."""
        laps = np.arange(0, max_laps + 1)
        temperatures = np.array([self.estimate_temperature(age=lap) for lap in laps])
        grips = np.array([self.get_grip(age=lap, track_wetness=track_wetness) for lap in laps])
        lap_times = np.array(
            [self.get_lap_time(age=lap, track_wetness=track_wetness) for lap in laps]
        )
        return {
            "laps": laps,
            "grip": grips,
            "lap_times": lap_times,
            "temperature": temperatures,
        }

    def age_one_lap(self) -> None:
        self.tire_age += 1

    def reset(self) -> None:
        self.tire_age = 0

    def __repr__(self) -> str:
        return f"Tire(compound='{self.compound}', age={self.tire_age}, grip={self.get_grip():.3f})"

