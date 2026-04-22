"""Monte Carlo evaluation for pit-stop strategies."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import MONTE_CARLO_ITERATIONS, RANDOM_SEED
from core.race_simulator import RaceSimulator
from core.strategy import Strategy, load_all_strategies


class MonteCarloSimulator:
    """Run multiple stochastic races for one or more strategies."""

    def __init__(
        self,
        strategies: Optional[List[Strategy]] = None,
        circuit_name: str = "Silverstone",
        n_iterations: int = MONTE_CARLO_ITERATIONS,
        base_seed: int = RANDOM_SEED,
        track_wetness: float = 0.0,
    ) -> None:
        self.circuit_name = circuit_name
        self.strategies = strategies or load_all_strategies(circuit_name)
        self.n_iterations = n_iterations
        self.base_seed = base_seed
        self.track_wetness = track_wetness

        self.results: Dict[str, np.ndarray] = {}
        self.statistics: Dict[str, Dict[str, float]] = {}
        self.sample_race_data: Dict[str, pd.DataFrame] = {}
        self.is_completed = False

    def run(self, verbose: bool = True) -> Dict[str, np.ndarray]:
        for strategy_index, strategy in enumerate(self.strategies):
            if verbose:
                print(f"Running Monte Carlo for {strategy.name} ({self.n_iterations} iterations)")

            race_times = np.zeros(self.n_iterations)
            sample_df = None
            for iteration in range(self.n_iterations):
                seed = self.base_seed + strategy_index * self.n_iterations + iteration
                simulator = RaceSimulator(
                    strategy=strategy,
                    circuit_name=self.circuit_name,
                    enable_variability=True,
                    enable_safety_car=True,
                    random_seed=seed,
                    track_wetness=self.track_wetness,
                )
                df = simulator.simulate()
                race_times[iteration] = simulator.total_race_time
                if sample_df is None:
                    sample_df = df

            self.results[strategy.name] = race_times
            if sample_df is not None:
                self.sample_race_data[strategy.name] = sample_df

        self._calculate_statistics()
        self.is_completed = True
        return self.results

    def _calculate_statistics(self) -> None:
        for name, times in self.results.items():
            self.statistics[name] = {
                "mean": float(np.mean(times)),
                "median": float(np.median(times)),
                "std": float(np.std(times)),
                "min": float(np.min(times)),
                "max": float(np.max(times)),
                "q1": float(np.percentile(times, 25)),
                "q3": float(np.percentile(times, 75)),
                "ci_lower": float(np.percentile(times, 2.5)),
                "ci_upper": float(np.percentile(times, 97.5)),
            }

    def calculate_win_probabilities(self) -> Dict[str, float]:
        if not self.is_completed:
            raise RuntimeError("Monte Carlo has not been run yet.")

        strategy_names = list(self.results)
        matrix = np.column_stack([self.results[name] for name in strategy_names])
        winners = np.argmin(matrix, axis=1)
        counts = np.bincount(winners, minlength=len(strategy_names))
        probabilities = counts / self.n_iterations
        return {name: float(prob) for name, prob in zip(strategy_names, probabilities)}

    def get_best_strategy(self) -> str:
        if not self.statistics:
            raise RuntimeError("Monte Carlo has not been run yet.")
        return min(self.statistics, key=lambda key: self.statistics[key]["mean"])

    def get_comparison_dataframe(self) -> pd.DataFrame:
        if not self.is_completed:
            raise RuntimeError("Monte Carlo has not been run yet.")

        win_probabilities = self.calculate_win_probabilities()
        rows = []
        for strategy in self.strategies:
            stats = self.statistics[strategy.name]
            rows.append(
                {
                    "strategy": strategy.name,
                    "pit_stops": strategy.num_stops,
                    "mean": stats["mean"],
                    "median": stats["median"],
                    "std": stats["std"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "ci_lower": stats["ci_lower"],
                    "ci_upper": stats["ci_upper"],
                    "win_probability": win_probabilities[strategy.name],
                }
            )

        df = pd.DataFrame(rows).sort_values("mean").reset_index(drop=True)
        df.index += 1
        df.index.name = "rank"
        return df

