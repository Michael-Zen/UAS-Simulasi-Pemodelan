"""CLI entry point for the integrated F1 pit stop simulation system."""

from __future__ import annotations

import argparse
import json
import os
from typing import List, Tuple

import pandas as pd

from analysis.sensitivity_analysis import SensitivityAnalyzer
from analysis.validation_fastf1 import FastF1Validator
from config import get_circuit_names
from core.multi_car_race import MultiCarRace
from core.race_simulator import RaceSimulator
from core.strategy import Strategy, load_all_strategies
from optimization.genetic_optimizer import GeneticStrategyOptimizer
from optimization.monte_carlo import MonteCarloSimulator
from optimization.rl_agent import QLearningPitAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="F1 pit stop simulation toolkit")
    parser.add_argument("--circuit", default="Silverstone", choices=get_circuit_names())
    parser.add_argument(
        "--mode",
        default="single",
        choices=["single", "multi", "optimize", "validate", "report"],
        help="Execution mode",
    )
    parser.add_argument(
        "--strategy",
        default="1-Stop: M->H",
        help="Strategy name for single mode, or 'rl' for RL optimizer mode.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=500,
        help="Monte Carlo iterations or optimization training/generation count.",
    )
    return parser


def get_strategy_by_name(strategy_name: str, circuit_name: str) -> Strategy:
    strategies = load_all_strategies(circuit_name)
    for strategy in strategies:
        if strategy.name == strategy_name:
            return strategy
    available = ", ".join(strategy.name for strategy in strategies)
    raise ValueError(f"Unknown strategy '{strategy_name}'. Available strategies: {available}")


def run_single_mode(args: argparse.Namespace) -> None:
    strategy = get_strategy_by_name(args.strategy, args.circuit)
    simulator = RaceSimulator(
        strategy=strategy,
        circuit_name=args.circuit,
        enable_variability=False,
        enable_safety_car=False,
    )
    simulator.simulate()
    summary = simulator.get_summary()

    print(f"Circuit  : {args.circuit}")
    print(f"Strategy : {strategy.name}")
    print(f"Total    : {summary['total_race_time_formatted']}")
    print(f"Avg lap  : {summary['avg_lap_time']:.3f}s")
    print(f"Fastest  : {summary['fastest_lap']:.3f}s")


def run_multi_mode(args: argparse.Namespace) -> None:
    strategies = load_all_strategies(args.circuit)
    pairings: List[Tuple[str, Strategy]] = [
        ("VER", strategies[1]),
        ("LEC", strategies[0]),
        ("HAM", strategies[3]),
        ("NOR", strategies[2]),
    ]
    multi_race = MultiCarRace(pairings, circuit_name=args.circuit, random_seed=42)
    df = multi_race.simulate()
    os.makedirs("output", exist_ok=True)
    csv_path = os.path.join("output", f"multi_car_{args.circuit.lower()}.csv")
    df.to_csv(csv_path, index=False)

    print(f"Multi-car race saved to {csv_path}")
    print(multi_race.get_final_standings().to_string(index=False))


def run_optimize_mode(args: argparse.Namespace) -> None:
    os.makedirs("output", exist_ok=True)
    if args.strategy.lower() == "rl":
        agent = QLearningPitAgent(circuit_name=args.circuit, episodes=args.iterations)
        result = agent.train(output_dir="output")
        print(f"RL training finished for {args.circuit}")
        print(f"Greedy pit plan: {result['pit_plan']}")
        print(
            "Monte Carlo benchmark: "
            f"{result['comparison']['best_monte_carlo_strategy']} "
            f"({result['comparison']['best_monte_carlo_time']:.3f}s)"
        )
        return

    optimizer = GeneticStrategyOptimizer(
        circuit_name=args.circuit,
        generations=args.iterations,
    )
    best_ranked = optimizer.run(verbose=True, output_dir="output")
    print("Top 3 genetic strategies:")
    for index, ranked in enumerate(best_ranked, start=1):
        print(f"{index}. {ranked.strategy.name} -> {ranked.total_race_time:.3f}s | {ranked.chromosome}")


def run_validate_mode(args: argparse.Namespace) -> None:
    validator = FastF1Validator(circuit_name=args.circuit)
    results = validator.validate_top_finishers(output_dir="output")
    calibration = validator.calibrate(output_dir="output")

    print("Validation results:")
    for result in results:
        print(f"- {result.driver}: RMSE={result.rmse:.3f}s | MAE={result.mae:.3f}s")
    print(f"Calibrated parameters: {json.dumps(calibration, indent=2)}")


def run_report_mode(args: argparse.Namespace) -> None:
    os.makedirs("output", exist_ok=True)
    strategies = load_all_strategies(args.circuit)
    mc = MonteCarloSimulator(
        strategies=strategies,
        circuit_name=args.circuit,
        n_iterations=args.iterations,
    )
    mc.run(verbose=False)

    sensitivity = SensitivityAnalyzer(circuit_name=args.circuit)
    sensitivity_summary = sensitivity.run(output_dir="output")
    comparison = mc.get_comparison_dataframe()

    report = {
        "circuit": args.circuit,
        "monte_carlo_best": mc.get_best_strategy(),
        "monte_carlo_results": comparison.to_dict(orient="records"),
        "sensitivity": sensitivity_summary.to_dict(orient="records"),
    }
    report_path = os.path.join("output", f"report_{args.circuit.lower()}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(f"Report saved to {report_path}")
    print(f"Best Monte Carlo strategy: {mc.get_best_strategy()}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "single":
        run_single_mode(args)
    elif args.mode == "multi":
        run_multi_mode(args)
    elif args.mode == "optimize":
        run_optimize_mode(args)
    elif args.mode == "validate":
        run_validate_mode(args)
    elif args.mode == "report":
        run_report_mode(args)


if __name__ == "__main__":
    main()

