"""Validation helpers using FastF1 race data."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import TIRE_COMPOUNDS
from core.race_simulator import RaceSimulator
from core.strategy import Strategy


@dataclass
class ValidationResult:
    driver: str
    rmse: float
    mae: float
    strategy: Strategy
    comparison: pd.DataFrame


class FastF1Validator:
    """Fetch British GP 2023 data and compare it with the simulator."""

    def __init__(self, circuit_name: str = "Silverstone") -> None:
        self.circuit_name = circuit_name
        self.validation_results: List[ValidationResult] = []

    def _load_session(self):
        try:
            import fastf1
        except ImportError as exc:
            raise ImportError("fastf1 is required for validation mode. Install requirements first.") from exc

        fastf1.Cache.enable_cache("output/fastf1_cache")
        session = fastf1.get_session(2023, "British Grand Prix", "R")
        session.load()
        return session

    @staticmethod
    def _extract_strategy(driver_laps: pd.DataFrame) -> Strategy:
        usable = driver_laps.dropna(subset=["LapTime", "Compound"]).copy()
        usable = usable[usable["LapNumber"] >= 1]
        compound_changes = usable["Compound"].ne(usable["Compound"].shift()).fillna(True)
        change_rows = usable[compound_changes]
        pit_plan = []
        current_compound = str(change_rows.iloc[0]["Compound"]).title()

        previous_compound = current_compound
        previous_lap = int(usable.iloc[0]["LapNumber"])
        for _, row in change_rows.iloc[1:].iterrows():
            lap_number = int(row["LapNumber"])
            compound = str(row["Compound"]).title()
            pit_plan.append((lap_number - 1, compound))
            previous_compound = compound
            previous_lap = lap_number

        total_laps = int(usable["LapNumber"].max())
        return Strategy.from_pit_plan(
            name=f"Actual {usable.iloc[0]['Driver']}",
            start_compound=current_compound,
            pit_plan=pit_plan,
            total_laps=total_laps,
            description="Extracted from FastF1 data.",
        )

    def validate_top_finishers(self, limit: int = 5, output_dir: str = "output") -> List[ValidationResult]:
        session = self._load_session()
        os.makedirs(output_dir, exist_ok=True)

        results = session.results.head(limit)
        laps = session.laps.pick_quicklaps().copy()
        validation_results: List[ValidationResult] = []

        for _, result_row in results.iterrows():
            abbreviation = result_row["Abbreviation"]
            driver_laps = laps.pick_driver(abbreviation).copy()
            if driver_laps.empty:
                continue

            strategy = self._extract_strategy(driver_laps)
            simulator = RaceSimulator(
                strategy=strategy,
                circuit_name=self.circuit_name,
                enable_variability=False,
                enable_safety_car=False,
            )
            simulated_df = simulator.simulate()

            actual_times = driver_laps["LapTime"].dt.total_seconds().reset_index(drop=True)
            simulated_times = simulated_df["final_lap_time"].iloc[: len(actual_times)].reset_index(drop=True)
            comparison = pd.DataFrame(
                {
                    "lap": np.arange(1, len(actual_times) + 1),
                    "actual_lap_time": actual_times,
                    "simulated_lap_time": simulated_times,
                }
            )
            rmse = float(np.sqrt(np.mean((comparison["simulated_lap_time"] - comparison["actual_lap_time"]) ** 2)))
            mae = float(np.mean(np.abs(comparison["simulated_lap_time"] - comparison["actual_lap_time"])))

            validation_results.append(
                ValidationResult(
                    driver=abbreviation,
                    rmse=rmse,
                    mae=mae,
                    strategy=strategy,
                    comparison=comparison,
                )
            )

        self.validation_results = validation_results
        self._plot_validation(output_dir)
        return validation_results

    def calibrate(self, output_dir: str = "output") -> Dict[str, float]:
        try:
            from scipy.optimize import minimize
        except ImportError as exc:
            raise ImportError("scipy is required for calibration mode. Install requirements first.") from exc

        if not self.validation_results:
            self.validate_top_finishers(output_dir=output_dir)

        def objective(values: np.ndarray) -> float:
            degradation_scale, cliff_scale = values
            compound_overrides = deepcopy(TIRE_COMPOUNDS)
            for compound in compound_overrides:
                compound_overrides[compound]["degradation_rate"] *= float(degradation_scale)
                compound_overrides[compound]["cliff_penalty"] *= float(cliff_scale)

            errors = []
            for result in self.validation_results:
                simulator = RaceSimulator(
                    strategy=result.strategy,
                    circuit_name=self.circuit_name,
                    enable_variability=False,
                    enable_safety_car=False,
                    simulation_overrides={"compound_overrides": compound_overrides},
                )
                simulated = simulator.simulate()["final_lap_time"].iloc[: len(result.comparison)]
                actual = result.comparison["actual_lap_time"]
                errors.append(np.sqrt(np.mean((simulated.values - actual.values) ** 2)))
            return float(np.mean(errors))

        optimum = minimize(objective, x0=np.array([1.0, 1.0]), bounds=[(0.5, 1.5), (0.5, 1.5)])
        calibrated = {
            "degradation_rate_scale": float(optimum.x[0]),
            "cliff_penalty_scale": float(optimum.x[1]),
            "objective_rmse": float(optimum.fun),
        }
        output_path = os.path.join(output_dir, "calibrated_params.json")
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(calibrated, handle, indent=2)
        return calibrated

    def _plot_validation(self, output_dir: str) -> str:
        if not self.validation_results:
            return ""

        output_path = os.path.join(output_dir, "validation_fastf1.png")
        figure, axes = plt.subplots(2, 3, figsize=(16, 9))
        axes = axes.flatten()

        for axis, result in zip(axes, self.validation_results):
            axis.plot(result.comparison["lap"], result.comparison["actual_lap_time"], label="Actual", linewidth=1.8)
            axis.plot(
                result.comparison["lap"],
                result.comparison["simulated_lap_time"],
                label="Simulated",
                linewidth=1.8,
            )
            for pit_lap in result.strategy.get_pit_stop_laps():
                axis.axvline(pit_lap, color="#E10600", linestyle="--", alpha=0.4)
            axis.set_title(f"{result.driver} | RMSE {result.rmse:.2f}s")
            axis.set_xlabel("Lap")
            axis.set_ylabel("Lap time (s)")
            axis.grid(alpha=0.3)

        for axis in axes[len(self.validation_results) :]:
            axis.axis("off")

        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc="upper center", ncol=2)
        figure.tight_layout(rect=(0, 0, 1, 0.95))
        figure.savefig(output_path, dpi=150)
        plt.close(figure)
        return output_path
