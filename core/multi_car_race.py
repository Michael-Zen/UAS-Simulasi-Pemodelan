"""Multi-car race simulation with traffic and VSC logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

from config import (
    TRAFFIC_DELTA_RANGE,
    TRAFFIC_GAP_THRESHOLD,
    VSC_DURATION_MAX,
    VSC_DURATION_MIN,
    VSC_LAP_TIME,
    VSC_PROBABILITY,
    get_circuit_config,
)
from core.race_simulator import RaceSimulator
from core.strategy import Strategy
from core.tire_model import Tire


@dataclass
class _DriverState:
    name: str
    strategy: Strategy
    cumulative_time: float = 0.0
    latest_lap_time: float = 0.0
    last_gap_to_car_ahead: float = 999.0


class MultiCarRace:
    """Simulate several cars together, updating positions lap by lap."""

    def __init__(
        self,
        drivers_and_strategies: Sequence[Tuple[str, Strategy]],
        circuit_name: str = "Silverstone",
        random_seed: int | None = None,
        track_wetness: float = 0.0,
    ) -> None:
        if not drivers_and_strategies:
            raise ValueError("MultiCarRace requires at least one car.")

        self.circuit_config = get_circuit_config(circuit_name)
        self.circuit_name = circuit_name
        self.total_laps = int(self.circuit_config["total_laps"])
        self.track_wetness = track_wetness
        self.rng = np.random.default_rng(random_seed)

        self.driver_states = [
            _DriverState(name=driver, strategy=strategy)
            for driver, strategy in drivers_and_strategies
        ]
        for state in self.driver_states:
            if state.strategy.total_laps != self.total_laps:
                raise ValueError(
                    f"Strategy '{state.strategy.name}' for {state.name} does not match "
                    f"the {self.total_laps}-lap distance of {self.circuit_name}."
                )

        self.results: pd.DataFrame | None = None
        self.vsc_laps: List[int] = []

    def _base_lap_time(self, state: _DriverState, lap: int) -> tuple[float, str, int]:
        compound = state.strategy.get_compound_at_lap(lap)
        tire_age = state.strategy.get_tire_age_at_lap(lap)
        tire = Tire(compound, track_wetness=self.track_wetness)
        lap_time = tire.get_lap_time(
            base_time=self.circuit_config["base_lap_time"],
            age=tire_age,
            track_wetness=self.track_wetness,
        )
        fuel_effect = RaceSimulator(
            strategy=state.strategy,
            circuit_name=self.circuit_name,
            enable_variability=False,
            enable_safety_car=False,
            track_wetness=self.track_wetness,
        )._calculate_fuel_effect(lap)
        lap_time -= fuel_effect
        if lap in state.strategy.get_pit_stop_laps():
            lap_time += RaceSimulator(
                strategy=state.strategy,
                circuit_name=self.circuit_name,
                enable_variability=False,
                enable_safety_car=False,
                track_wetness=self.track_wetness,
            )._calculate_pit_stop_time()
        return lap_time, compound, tire_age

    def simulate(self) -> pd.DataFrame:
        rows: List[dict] = []
        vsc_remaining = 0
        previous_order = list(self.driver_states)

        for lap in range(1, self.total_laps + 1):
            is_vsc = False
            if vsc_remaining > 0:
                is_vsc = True
                vsc_remaining -= 1
            elif self.rng.random() < VSC_PROBABILITY:
                is_vsc = True
                vsc_remaining = int(self.rng.integers(VSC_DURATION_MIN, VSC_DURATION_MAX + 1)) - 1

            if is_vsc:
                self.vsc_laps.append(lap)

            lap_snapshots = []
            for index, state in enumerate(previous_order):
                lap_time, compound, tire_age = self._base_lap_time(state, lap)
                traffic_penalty = 0.0
                if not is_vsc and index > 0 and state.last_gap_to_car_ahead < TRAFFIC_GAP_THRESHOLD:
                    traffic_penalty = float(
                        self.rng.uniform(TRAFFIC_DELTA_RANGE[0], TRAFFIC_DELTA_RANGE[1])
                    )

                if is_vsc:
                    pit_loss = lap_time - max(
                        lap_time - self.circuit_config["pit_lane_delta"] - 2.8,
                        0.0,
                    )
                    lap_time = VSC_LAP_TIME + max(pit_loss, 0.0)
                else:
                    lap_time += traffic_penalty

                state.latest_lap_time = lap_time
                state.cumulative_time += lap_time

                lap_snapshots.append(
                    {
                        "lap": lap,
                        "driver": state.name,
                        "compound": compound,
                        "tire_age": tire_age,
                        "lap_time": lap_time,
                        "cumulative_time": state.cumulative_time,
                    }
                )

            lap_snapshots.sort(key=lambda item: item["cumulative_time"])
            leader_time = lap_snapshots[0]["cumulative_time"]
            name_to_gap_ahead = {}
            for position, snapshot in enumerate(lap_snapshots, start=1):
                snapshot["position"] = position
                snapshot["gap_to_leader"] = snapshot["cumulative_time"] - leader_time
                snapshot["tire_compound"] = snapshot.pop("compound")
                rows.append(snapshot)
                if position == 1:
                    name_to_gap_ahead[snapshot["driver"]] = 999.0
                else:
                    ahead_time = lap_snapshots[position - 2]["cumulative_time"]
                    name_to_gap_ahead[snapshot["driver"]] = snapshot["cumulative_time"] - ahead_time

            previous_order = sorted(self.driver_states, key=lambda driver: driver.cumulative_time)
            for state in previous_order:
                state.last_gap_to_car_ahead = name_to_gap_ahead[state.name]

        self.results = pd.DataFrame(rows)[
            [
                "lap",
                "driver",
                "position",
                "gap_to_leader",
                "tire_compound",
                "tire_age",
                "lap_time",
                "cumulative_time",
            ]
        ]
        return self.results

    def get_final_standings(self) -> pd.DataFrame:
        if self.results is None:
            raise RuntimeError("Run simulate() before requesting final standings.")
        final_lap = self.results["lap"].max()
        standings = self.results[self.results["lap"] == final_lap].copy()
        standings = standings.sort_values(["position", "cumulative_time"]).reset_index(drop=True)
        return standings[["position", "driver", "gap_to_leader", "lap_time", "tire_compound", "tire_age"]]
