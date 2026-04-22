"""One-at-a-time sensitivity analysis utilities."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    FUEL_EFFECT_PER_LAP,
    PIT_STOP_TIME_MEAN,
    TIRE_COMPOUNDS,
)
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies


class SensitivityAnalyzer:
    """Run OAT sensitivity analysis on key simulation parameters."""

    def __init__(self, circuit_name: str = "Silverstone", steps: int = 20) -> None:
        self.circuit_name = circuit_name
        self.steps = steps
        self.baseline_parameters = {
            "degradation_rate": 1.0,
            "cliff_point": 1.0,
            "pit_stop_time_mean": PIT_STOP_TIME_MEAN,
            "fuel_effect_per_lap": FUEL_EFFECT_PER_LAP,
        }
        self.results: Dict[str, pd.DataFrame] = {}
        self.summary: pd.DataFrame | None = None

    def _build_overrides(self, parameter_name: str, value: float) -> dict:
        overrides = {}
        compound_overrides = deepcopy(TIRE_COMPOUNDS)
        if parameter_name == "degradation_rate":
            for compound in compound_overrides:
                compound_overrides[compound]["degradation_rate"] *= value
            overrides["compound_overrides"] = compound_overrides
        elif parameter_name == "cliff_point":
            for compound in compound_overrides:
                compound_overrides[compound]["cliff_point"] = max(
                    5, int(round(compound_overrides[compound]["cliff_point"] * value))
                )
            overrides["compound_overrides"] = compound_overrides
        elif parameter_name == "pit_stop_time_mean":
            overrides["pit_stop_time_mean"] = value
        elif parameter_name == "fuel_effect_per_lap":
            overrides["fuel_effect_per_lap"] = value
        return overrides

    def _evaluate_strategies(self, overrides: dict) -> pd.DataFrame:
        rows = []
        for strategy in load_all_strategies(self.circuit_name):
            simulator = RaceSimulator(
                strategy=strategy,
                circuit_name=self.circuit_name,
                enable_variability=False,
                enable_safety_car=False,
                simulation_overrides=overrides,
            )
            simulator.simulate()
            rows.append(
                {
                    "strategy": strategy.name,
                    "total_race_time": simulator.total_race_time,
                }
            )
        return pd.DataFrame(rows).sort_values("total_race_time").reset_index(drop=True)

    def run(self, output_dir: str = "output") -> pd.DataFrame:
        os.makedirs(output_dir, exist_ok=True)
        baseline_ranking = self._evaluate_strategies({})
        baseline_best = float(baseline_ranking.iloc[0]["total_race_time"])
        baseline_order = baseline_ranking["strategy"].tolist()

        summary_rows = []
        for parameter_name, baseline_value in self.baseline_parameters.items():
            if parameter_name in {"degradation_rate", "cliff_point"}:
                samples = np.linspace(0.5, 1.5, self.steps)
            else:
                samples = np.linspace(baseline_value * 0.5, baseline_value * 1.5, self.steps)

            rows = []
            for sample in samples:
                ranking = self._evaluate_strategies(self._build_overrides(parameter_name, float(sample)))
                rows.append(
                    {
                        "parameter_value": float(sample),
                        "best_total_race_time": float(ranking.iloc[0]["total_race_time"]),
                        "best_strategy": ranking.iloc[0]["strategy"],
                        "ranking_changed": ranking["strategy"].tolist() != baseline_order,
                    }
                )

            parameter_df = pd.DataFrame(rows)
            self.results[parameter_name] = parameter_df

            output_low = float(parameter_df.iloc[0]["best_total_race_time"])
            output_high = float(parameter_df.iloc[-1]["best_total_race_time"])
            input_low = float(parameter_df.iloc[0]["parameter_value"])
            input_high = float(parameter_df.iloc[-1]["parameter_value"])
            sensitivity_index = (
                ((output_high - output_low) / baseline_best)
                / ((input_high - input_low) / baseline_value)
            )

            summary_rows.append(
                {
                    "parameter": parameter_name,
                    "baseline_value": baseline_value,
                    "baseline_output": baseline_best,
                    "sensitivity_index": float(sensitivity_index),
                    "ranking_changed": bool(parameter_df["ranking_changed"].any()),
                }
            )

        self.summary = pd.DataFrame(summary_rows).sort_values(
            "sensitivity_index", key=lambda series: series.abs(), ascending=False
        )
        self._plot_tornado(output_dir)
        return self.summary

    def _plot_tornado(self, output_dir: str) -> str:
        if self.summary is None:
            raise RuntimeError("Run sensitivity analysis before plotting.")
        output_path = os.path.join(output_dir, "sensitivity_tornado.png")
        plot_df = self.summary.copy()
        plt.figure(figsize=(10, 5))
        colors = ["#00B050" if value >= 0 else "#E10600" for value in plot_df["sensitivity_index"]]
        plt.barh(plot_df["parameter"], plot_df["sensitivity_index"], color=colors)
        plt.axvline(0.0, color="black", linewidth=1.0)
        plt.title(f"Tornado Chart - {self.circuit_name}")
        plt.xlabel("Sensitivity index")
        plt.ylabel("Parameter")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        return output_path

