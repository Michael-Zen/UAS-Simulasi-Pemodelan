"""Flask API for the integrated F1 pit-stop simulation project."""

from __future__ import annotations

import os
import sys
import traceback

import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config import TIRE_COMPOUNDS, get_circuit_config, get_circuit_names  # noqa: E402
from core.race_simulator import RaceSimulator  # noqa: E402
from core.strategy import load_all_strategies  # noqa: E402
from core.tire_model import Tire  # noqa: E402
from optimization.monte_carlo import MonteCarloSimulator  # noqa: E402


FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


def get_strategy_by_name(name: str, circuit_name: str):
    for strategy in load_all_strategies(circuit_name):
        if strategy.name == name:
            return strategy
    return None


@app.route("/api/circuits", methods=["GET"])
def get_circuits():
    return jsonify(
        {
            "circuits": {
                circuit_name: get_circuit_config(circuit_name)
                for circuit_name in get_circuit_names()
            }
        }
    )


@app.route("/api/compounds", methods=["GET"])
def get_compounds():
    circuit_name = request.args.get("circuit", "Silverstone")
    circuit = get_circuit_config(circuit_name)
    return jsonify(
        {
            "circuit": circuit_name,
            "total_laps": circuit["total_laps"],
            "base_lap_time": circuit["base_lap_time"],
            "compounds": TIRE_COMPOUNDS,
        }
    )


@app.route("/api/strategies", methods=["GET"])
def get_strategies():
    circuit_name = request.args.get("circuit", "Silverstone")
    strategies = [strategy.as_dict() for strategy in load_all_strategies(circuit_name)]
    return jsonify({"circuit": circuit_name, "strategies": strategies})


@app.route("/api/degradation", methods=["GET"])
def get_degradation():
    circuit_name = request.args.get("circuit", "Silverstone")
    max_laps = int(request.args.get("max_laps", 50))
    compounds_data = {}

    for compound_name, params in TIRE_COMPOUNDS.items():
        tire = Tire(compound_name)
        curve = tire.get_degradation_curve(max_laps=max_laps)
        compounds_data[compound_name] = {
            "laps": curve["laps"].tolist(),
            "grip": [round(value, 4) for value in curve["grip"].tolist()],
            "lap_times": [round(value, 3) for value in curve["lap_times"].tolist()],
            "temperature": [round(value, 2) for value in curve["temperature"].tolist()],
            "color": params["color"],
            "label": params["label"],
            "cliff_point": params["cliff_point"],
            "warmup_laps": params["warmup_laps"],
            "initial_grip": params["initial_grip"],
            "degradation_rate": params["degradation_rate"],
        }

    return jsonify({"circuit": circuit_name, "compounds": compounds_data})


@app.route("/api/simulate/deterministic", methods=["POST"])
def simulate_deterministic():
    data = request.get_json(silent=True) or {}
    strategy_name = data.get("strategy_name")
    circuit_name = data.get("circuit", "Silverstone")
    if not strategy_name:
        return jsonify({"error": "Missing 'strategy_name' in request body"}), 400

    strategy = get_strategy_by_name(strategy_name, circuit_name)
    if strategy is None:
        return jsonify({"error": f"Strategy '{strategy_name}' not found for circuit '{circuit_name}'"}), 404

    try:
        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=circuit_name,
            enable_variability=False,
            enable_safety_car=False,
        )
        df = simulator.simulate()
        summary = simulator.get_summary()
        return jsonify(
            {
                "circuit": circuit_name,
                "strategy": strategy.as_dict(),
                "summary": summary,
                "laps": df.to_dict(orient="records"),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/compare", methods=["POST"])
def compare_strategies():
    data = request.get_json(silent=True) or {}
    strategy_names = data.get("strategy_names", [])
    circuit_name = data.get("circuit", "Silverstone")
    if len(strategy_names) < 2:
        return jsonify({"error": "Please select at least two strategies"}), 400

    rows = []
    for strategy_name in strategy_names:
        strategy = get_strategy_by_name(strategy_name, circuit_name)
        if strategy is None:
            return jsonify({"error": f"Strategy '{strategy_name}' not found"}), 404

        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=circuit_name,
            enable_variability=False,
            enable_safety_car=False,
        )
        simulator.simulate()
        summary = simulator.get_summary()
        rows.append(
            {
                "name": strategy.name,
                "num_stops": strategy.num_stops,
                "total_race_time": summary["total_race_time"],
                "total_race_time_formatted": summary["total_race_time_formatted"],
                "avg_lap_time": summary["avg_lap_time"],
                "fastest_lap": summary["fastest_lap"],
                "slowest_lap": summary["slowest_lap"],
                "total_pit_time_lost": summary["total_pit_time_lost"],
            }
        )

    rows.sort(key=lambda item: item["total_race_time"])
    best_time = rows[0]["total_race_time"]
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["delta"] = row["total_race_time"] - best_time

    return jsonify({"circuit": circuit_name, "results": rows, "best_strategy": rows[0]["name"]})


@app.route("/api/simulate/monte-carlo", methods=["POST"])
def simulate_monte_carlo():
    data = request.get_json(silent=True) or {}
    strategy_names = data.get("strategy_names", [])
    circuit_name = data.get("circuit", "Silverstone")
    iterations = int(np.clip(data.get("iterations", 500), 100, 2000))
    if not strategy_names:
        return jsonify({"error": "Please select at least one strategy"}), 400

    strategies = []
    for name in strategy_names:
        strategy = get_strategy_by_name(name, circuit_name)
        if strategy is None:
            return jsonify({"error": f"Strategy '{name}' not found"}), 404
        strategies.append(strategy)

    try:
        mc = MonteCarloSimulator(
            strategies=strategies,
            circuit_name=circuit_name,
            n_iterations=iterations,
            base_seed=42,
        )
        mc.run(verbose=False)
        win_probabilities = mc.calculate_win_probabilities()

        results = []
        for strategy in strategies:
            stats = mc.statistics[strategy.name]
            distribution = mc.results[strategy.name]
            results.append(
                {
                    "name": strategy.name,
                    "mean": round(stats["mean"], 3),
                    "median": round(stats["median"], 3),
                    "std": round(stats["std"], 3),
                    "min": round(stats["min"], 3),
                    "max": round(stats["max"], 3),
                    "q1": round(stats["q1"], 3),
                    "q3": round(stats["q3"], 3),
                    "ci_lower": round(stats["ci_lower"], 3),
                    "ci_upper": round(stats["ci_upper"], 3),
                    "win_probability": round(win_probabilities[strategy.name] * 100, 1),
                    "distribution": [round(value, 3) for value in distribution.tolist()],
                    "mean_formatted": RaceSimulator._format_time(stats["mean"]),
                }
            )

        results.sort(key=lambda item: item["mean"])
        return jsonify(
            {
                "circuit": circuit_name,
                "iterations": iterations,
                "results": results,
                "best_strategy": results[0]["name"],
                "ranking": [result["name"] for result in results],
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    print("Integrated F1 simulation backend")
    print("Listening on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
