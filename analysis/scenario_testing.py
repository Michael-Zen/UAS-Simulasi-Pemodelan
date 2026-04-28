"""Scenario testing framework for F1 pit stop strategy paper scenarios."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import get_circuit_config
from core.race_simulator import RaceSimulator
from core.strategy import Strategy


class ScenarioTester:
    """Run what-if scenarios for pit stop strategy analysis."""
    
    def __init__(self, circuit_name: str = "Silverstone", random_seed: Optional[int] = None):
        self.circuit_name = circuit_name
        self.circuit_config = get_circuit_config(circuit_name)
        self.total_laps = int(self.circuit_config["total_laps"])
        self.random_seed = random_seed or 42
        self.results: Dict[str, Dict] = {}
    
    def run_baseline_scenario(self) -> Dict:
        """
        Baseline Scenario: 1-stop Medium → Hard at lap 30/52 (or proportional).
        Paper: "Strategi satu pit stop dengan urutan kompon Medium → Hard."
        """
        pit_lap = int(round(self.total_laps * 0.58))  # ~30 laps out of ~52
        
        stints = [
            ("Medium", 1, pit_lap),
            ("Hard", pit_lap + 1, self.total_laps)
        ]
        
        strategy = Strategy(
            name="Baseline (M→H)",
            stints=stints,
            description="1-stop baseline: Medium then Hard"
        )
        
        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=self.circuit_name,
            enable_variability=False,
            enable_safety_car=False,
            track_wetness=0.0
        )
        
        df = simulator.simulate()
        summary = simulator.get_summary()
        
        result = {
            "scenario_name": "Baseline (1-Stop: M→H)",
            "strategy_name": strategy.name,
            "strategy": strategy.as_dict(),
            "pit_lap": pit_lap,
            "num_stops": 1,
            "total_race_time": summary["total_race_time"],
            "total_race_time_formatted": summary["total_race_time_formatted"],
            "avg_lap_time": summary["avg_lap_time"],
            "fastest_lap": summary["fastest_lap"],
            "slowest_lap": summary["slowest_lap"],
            "total_pit_time_lost": summary["total_pit_time_lost"],
            "laps_data": df.to_dict(orient="records"),
            "stint_analysis": self._analyze_stints(df)
        }
        
        self.results["baseline"] = result
        return result
    
    def run_1_stop_vs_2_stop_scenario(self) -> Dict:
        """
        Compare 1-stop vs 2-stop strategies.
        Paper: "Membandingkan total waktu antara strategi satu pit stop versus dua pit stop."
        """
        # 1-Stop: Medium → Hard
        pit_lap_1stop = int(round(self.total_laps * 0.58))
        stints_1stop = [
            ("Medium", 1, pit_lap_1stop),
            ("Hard", pit_lap_1stop + 1, self.total_laps)
        ]
        strategy_1stop = Strategy(
            name="1-Stop (M→H)",
            stints=stints_1stop,
            description="1-stop: Medium then Hard"
        )
        
        # 2-Stop: Soft → Medium → Hard
        pit_lap_1 = int(round(self.total_laps * 0.30))
        pit_lap_2 = int(round(self.total_laps * 0.65))
        stints_2stop = [
            ("Soft", 1, pit_lap_1),
            ("Medium", pit_lap_1 + 1, pit_lap_2),
            ("Hard", pit_lap_2 + 1, self.total_laps)
        ]
        strategy_2stop = Strategy(
            name="2-Stop (S→M→H)",
            stints=stints_2stop,
            description="2-stop: Soft, Medium, then Hard"
        )
        
        results_list = []
        for strategy in [strategy_1stop, strategy_2stop]:
            simulator = RaceSimulator(
                strategy=strategy,
                circuit_name=self.circuit_name,
                enable_variability=False,
                enable_safety_car=False,
                track_wetness=0.0
            )
            
            df = simulator.simulate()
            summary = simulator.get_summary()
            
            result = {
                "strategy_name": strategy.name,
                "strategy": strategy.as_dict(),
                "num_stops": strategy.num_stops,
                "total_race_time": summary["total_race_time"],
                "total_race_time_formatted": summary["total_race_time_formatted"],
                "avg_lap_time": summary["avg_lap_time"],
                "fastest_lap": summary["fastest_lap"],
                "slowest_lap": summary["slowest_lap"],
                "total_pit_time_lost": summary["total_pit_time_lost"],
                "stint_analysis": self._analyze_stints(df)
            }
            results_list.append(result)
        
        # Determine winner
        best_result = min(results_list, key=lambda x: x["total_race_time"])
        time_delta = abs(
            results_list[0]["total_race_time"] - results_list[1]["total_race_time"]
        )
        
        comparison_result = {
            "scenario_name": "1-Stop vs 2-Stop",
            "strategies": results_list,
            "best_strategy": best_result["strategy_name"],
            "time_delta": round(time_delta, 3),
            "analysis": (
                f"2-stop strategy uses fresher tires but incurs additional pit penalties. "
                f"The {best_result['strategy_name']} is better by {time_delta:.1f}s for {self.circuit_name}."
            )
        }
        
        self.results["1stop_vs_2stop"] = comparison_result
        return comparison_result
    
    def run_weather_transition_scenario(
        self,
        transition_type: str = "dry_to_wet",
        transition_lap: int = None
    ) -> Dict:
        """
        Test weather changes during the race.
        Paper scenarios:
        - Dry→Wet: "hujan mulai turun sehingga grip lintasan menurun drastis"
        - Wet→Dry: "lintasan mulai mengering, pembalap yang mengganti ke ban slick"
        """
        if transition_lap is None:
            transition_lap = int(round(self.total_laps * 0.5))  # Mid-race default
        
        if transition_type == "dry_to_wet":
            # Start on slicks (Medium), pit to Intermediate/Wet
            pit_lap = transition_lap
            stints = [
                ("Medium", 1, pit_lap),
                ("Intermediate", pit_lap + 1, self.total_laps)
            ]
            description = "Dry→Wet: Medium (dry) then Intermediate (wet)"
            track_wetness_before = 0.0
            track_wetness_after = 0.7
        else:  # wet_to_dry
            # Start on Intermediate/Wet, pit to Medium/Soft
            pit_lap = transition_lap
            stints = [
                ("Intermediate", 1, pit_lap),
                ("Medium", pit_lap + 1, self.total_laps)
            ]
            description = "Wet→Dry: Intermediate (wet) then Medium (dry)"
            track_wetness_before = 0.7
            track_wetness_after = 0.0
        
        strategy = Strategy(
            name=f"{transition_type.replace('_', ' ').title()}",
            stints=stints,
            description=description
        )
        
        # Run two simulations: before transition (const dry) and after transition (const wet)
        results_list = []
        for track_wetness, phase in [
            (track_wetness_before, "before_transition"),
            (track_wetness_after, "after_transition")
        ]:
            simulator = RaceSimulator(
                strategy=strategy,
                circuit_name=self.circuit_name,
                enable_variability=False,
                enable_safety_car=False,
                track_wetness=track_wetness
            )
            
            df = simulator.simulate()
            summary = simulator.get_summary()
            
            results_list.append({
                "phase": phase,
                "track_wetness": track_wetness,
                "total_race_time": summary["total_race_time"],
                "avg_lap_time": summary["avg_lap_time"],
                "fastest_lap": summary["fastest_lap"]
            })
        
        scenario_result = {
            "scenario_name": f"Weather Transition: {transition_type.replace('_', ' ').title()}",
            "transition_type": transition_type,
            "transition_lap": pit_lap,
            "strategy": strategy.as_dict(),
            "simulation_phases": results_list,
            "critical_timing": f"Pit at lap {pit_lap} to minimize grip loss during transition.",
            "analysis": (
                f"Timing pit stop at lap {pit_lap} during {transition_type.replace('_', ' ').title()} "
                f"transition is critical. Early/late by a few laps significantly impacts total race time."
            )
        }
        
        scenario_key = f"weather_{transition_type}"
        self.results[scenario_key] = scenario_result
        return scenario_result
    
    def run_best_combination_scenario(self, max_combinations: int = 30) -> Dict:
        """
        Test combinations of pit strategies to find the best.
        Paper: "Mencoba mengkombinasikan semua strategi di sirkuit... mencarikan kombinasi terbaik."
        """
        from itertools import combinations
        
        compounds = ["Soft", "Medium", "Hard"]
        best_time = float("inf")
        best_strategy = None
        tested_strategies = []
        
        # Generate various combinations (limit to avoid explosion)
        for num_stints in [1, 2, 3]:
            for compound_combo in combinations(compounds, num_stints):
                if len(tested_strategies) >= max_combinations:
                    break
                
                # For each combination, generate pit laps
                if num_stints == 1:
                    # Single stint (not realistic per FIA rules, skip)
                    continue
                elif num_stints == 2:
                    pit_lap = int(round(self.total_laps * 0.58))
                    stints = [
                        (compound_combo[0], 1, pit_lap),
                        (compound_combo[1], pit_lap + 1, self.total_laps)
                    ]
                else:  # num_stints == 3
                    pit_lap_1 = int(round(self.total_laps * 0.33))
                    pit_lap_2 = int(round(self.total_laps * 0.67))
                    stints = [
                        (compound_combo[0], 1, pit_lap_1),
                        (compound_combo[1], pit_lap_1 + 1, pit_lap_2),
                        (compound_combo[2], pit_lap_2 + 1, self.total_laps)
                    ]
                
                try:
                    strategy = Strategy(
                        name=f"{num_stints}-Stop: {'-'.join(compound_combo)}",
                        stints=stints
                    )
                    
                    simulator = RaceSimulator(
                        strategy=strategy,
                        circuit_name=self.circuit_name,
                        enable_variability=False,
                        enable_safety_car=False,
                        track_wetness=0.0
                    )
                    
                    df = simulator.simulate()
                    summary = simulator.get_summary()
                    race_time = summary["total_race_time"]
                    
                    tested_strategies.append({
                        "strategy_name": strategy.name,
                        "total_race_time": race_time,
                        "total_race_time_formatted": summary["total_race_time_formatted"],
                        "avg_lap_time": summary["avg_lap_time"],
                        "total_pit_time_lost": summary["total_pit_time_lost"]
                    })
                    
                    if race_time < best_time:
                        best_time = race_time
                        best_strategy = strategy
                except Exception:
                    # Skip invalid strategies
                    pass
        
        # Sort by race time
        tested_strategies.sort(key=lambda x: x["total_race_time"])
        
        scenario_result = {
            "scenario_name": "Best Combination Finder",
            "total_combinations_tested": len(tested_strategies),
            "best_strategy": {
                "name": best_strategy.name if best_strategy else "N/A",
                "total_race_time": best_time if best_strategy else None,
                "strategy": best_strategy.as_dict() if best_strategy else None
            },
            "top_5_strategies": tested_strategies[:5],
            "all_tested": tested_strategies
        }
        
        self.results["best_combination"] = scenario_result
        return scenario_result
    
    def _analyze_stints(self, df: pd.DataFrame) -> List[Dict]:
        """Analyze lap times per stint."""
        stint_analysis = []
        
        # Group by stint (assuming 'stint' column exists)
        if "stint" in df.columns:
            for stint_num in df["stint"].unique():
                stint_df = df[df["stint"] == stint_num]
                
                stint_info = {
                    "stint": int(stint_num),
                    "compound": stint_df.iloc[0]["compound"] if "compound" in stint_df.columns else "Unknown",
                    "laps": len(stint_df),
                    "avg_lap_time": round(stint_df["lap_time"].mean(), 3),
                    "fastest_lap": round(stint_df["lap_time"].min(), 3),
                    "slowest_lap": round(stint_df["lap_time"].max(), 3),
                    "degradation": round(
                        stint_df["lap_time"].iloc[-1] - stint_df["lap_time"].iloc[0],
                        3
                    )
                }
                stint_analysis.append(stint_info)
        
        return stint_analysis
    
    def get_all_results_summary(self) -> Dict:
        """Get summary of all executed scenarios."""
        return {
            "circuit": self.circuit_name,
            "total_laps": self.total_laps,
            "scenarios_executed": list(self.results.keys()),
            "results": self.results
        }

