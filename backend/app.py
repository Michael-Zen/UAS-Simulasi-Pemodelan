"""Flask API for the integrated F1 pit-stop simulation project."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone

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
from analysis.scenario_testing import ScenarioTester  # noqa: E402


FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

WEATHER_WETNESS = {
    "sunny": 0.0,
    "cloudy": 0.1,
    "rain": 0.7,
    "heavy_rain": 1.0,
}


def get_strategy_by_name(name: str, circuit_name: str):
    for strategy in load_all_strategies(circuit_name):
        if strategy.name == name:
            return strategy
    return None


def _resolve_strategy(data: dict, circuit_name: str):
    """Return a Strategy from either strategy_name or custom_stints."""
    from core.strategy import Strategy as StrategyClass
    custom_stints = data.get("custom_stints")
    if custom_stints:
        total_laps = int(get_circuit_config(circuit_name)["total_laps"])
        return StrategyClass.from_custom_stints(custom_stints, total_laps)
    strategy_name = data.get("strategy_name")
    if not strategy_name:
        return None
    return get_strategy_by_name(strategy_name, circuit_name)


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
    circuit = get_circuit_config(circuit_name)
    max_laps = int(request.args.get("max_laps", 50))
    compounds_data = {}
    base_lap_time = float(circuit["base_lap_time"])
    degradation_multiplier = float(circuit["degradation_multiplier"])

    for compound_name, params in TIRE_COMPOUNDS.items():
        adjusted_params = dict(params)
        adjusted_params["degradation_rate"] = float(adjusted_params["degradation_rate"]) * degradation_multiplier

        tire = Tire(compound_name, compound_data=adjusted_params)
        curve = tire.get_degradation_curve(max_laps=max_laps)
        lap_times = [round(tire.get_lap_time(base_time=base_lap_time, age=lap), 3) for lap in curve["laps"].tolist()]
        compounds_data[compound_name] = {
            "laps": curve["laps"].tolist(),
            "grip": [round(value, 4) for value in curve["grip"].tolist()],
            "lap_times": lap_times,
            "temperature": [round(value, 2) for value in curve["temperature"].tolist()],
            "color": params["color"],
            "label": params["label"],
            "cliff_point": params["cliff_point"],
            "warmup_laps": params["warmup_laps"],
            "initial_grip": params["initial_grip"],
            "degradation_rate": round(adjusted_params["degradation_rate"], 6),
        }

    return jsonify(
        {
            "circuit": circuit_name,
            "base_lap_time": base_lap_time,
            "degradation_multiplier": degradation_multiplier,
            "compounds": compounds_data,
        }
    )


@app.route("/api/simulate/deterministic", methods=["POST"])
def simulate_deterministic():
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    weather = data.get("weather", "sunny")
    track_wetness = WEATHER_WETNESS.get(weather, 0.0)

    strategy = _resolve_strategy(data, circuit_name)
    if strategy is None:
        return jsonify({"error": "Missing 'strategy_name' or 'custom_stints' in request body"}), 400

    try:
        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=circuit_name,
            enable_variability=False,
            enable_safety_car=False,
            track_wetness=track_wetness,
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


@app.route("/api/simulate/telemetry", methods=["POST"])
def simulate_telemetry():
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    timestep_s = float(data.get("timestep_s", 0.5))
    max_points = data.get("max_points")
    response_shape = str(data.get("response_shape", "v2")).lower()
    weather = data.get("weather", "sunny")
    track_wetness = WEATHER_WETNESS.get(weather, 0.0)

    strategy = _resolve_strategy(data, circuit_name)
    if strategy is None:
        return jsonify({"error": "Missing 'strategy_name' or 'custom_stints' in request body"}), 400

    try:
        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=circuit_name,
            enable_variability=False,
            enable_safety_car=False,
            track_wetness=track_wetness,
        )
        df = simulator.simulate()
        summary = simulator.get_summary()
        telemetry_payload = simulator.generate_telemetry(timestep_s=timestep_s, max_points=max_points)

        result = {
            "circuit": circuit_name,
            "weather": weather,
            "track_wetness": track_wetness,
            "strategy": strategy.as_dict(),
            "summary": summary,
            "laps": df.to_dict(orient="records"),
            "track_map": telemetry_payload["track_map"],
            "channels": telemetry_payload["channels"],
            "sampling": telemetry_payload["sampling"],
            "telemetry": telemetry_payload["telemetry"],
        }

        if response_shape == "legacy":
            return jsonify(result)

        strategy_name = data.get("strategy_name", strategy.name)
        request_echo = {
            "strategy_name": strategy_name,
            "circuit": circuit_name,
            "weather": weather,
            "timestep_s": timestep_s,
            "max_points": max_points,
            "response_shape": "v2",
            "resolved": {
                "applied_timestep_s": telemetry_payload["sampling"]["applied_timestep_s"],
                "returned_points": telemetry_payload["sampling"]["returned_points"],
                "downsample_factor": telemetry_payload["sampling"]["downsample_factor"],
            },
        }

        return jsonify(
            {
                "meta": {
                    "schema_name": "f1_telemetry_simulation",
                    "schema_version": "2.0.0",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "ok",
                },
                "request": request_echo,
                "result": result,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/compare", methods=["POST"])
def compare_strategies():
    data = request.get_json(silent=True) or {}
    strategy_names = data.get("strategy_names", [])
    custom_stints_list = data.get("custom_stints_list", [])  # list of {name, stints}
    circuit_name = data.get("circuit", "Silverstone")
    weather = data.get("weather", "sunny")
    track_wetness = WEATHER_WETNESS.get(weather, 0.0)
    total_laps = int(get_circuit_config(circuit_name)["total_laps"])

    strategies = []
    for name in strategy_names:
        strategy = get_strategy_by_name(name, circuit_name)
        if strategy is None:
            return jsonify({"error": f"Strategy '{name}' not found"}), 404
        strategies.append(strategy)

    from core.strategy import Strategy as StrategyClass
    for custom in custom_stints_list:
        cs = StrategyClass.from_custom_stints(
            custom["stints"], total_laps, name=custom.get("name", "Custom")
        )
        strategies.append(cs)

    if len(strategies) < 2:
        return jsonify({"error": "Please select at least two strategies"}), 400

    rows = []
    for strategy in strategies:
        simulator = RaceSimulator(
            strategy=strategy,
            circuit_name=circuit_name,
            enable_variability=False,
            enable_safety_car=False,
            track_wetness=track_wetness,
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
    custom_stints_list = data.get("custom_stints_list", [])
    circuit_name = data.get("circuit", "Silverstone")
    weather = data.get("weather", "sunny")
    track_wetness = WEATHER_WETNESS.get(weather, 0.0)
    iterations = int(np.clip(data.get("iterations", 500), 100, 2000))
    total_laps = int(get_circuit_config(circuit_name)["total_laps"])

    strategies = []
    for name in strategy_names:
        strategy = get_strategy_by_name(name, circuit_name)
        if strategy is None:
            return jsonify({"error": f"Strategy '{name}' not found"}), 404
        strategies.append(strategy)

    from core.strategy import Strategy as StrategyClass
    for custom in custom_stints_list:
        cs = StrategyClass.from_custom_stints(
            custom["stints"], total_laps, name=custom.get("name", "Custom")
        )
        strategies.append(cs)

    if not strategies:
        return jsonify({"error": "Please select at least one strategy"}), 400

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


@app.route("/api/scenarios/baseline", methods=["POST"])
def scenario_baseline():
    """
    Run Baseline Scenario: 1-stop Medium → Hard
    Paper: Strategi standar satu kali pit stop dengan urutan kompon Medium → Hard
    """
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    
    try:
        tester = ScenarioTester(circuit_name=circuit_name, random_seed=42)
        result = tester.run_baseline_scenario()
        return jsonify({
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "scenario_type": "baseline"
            },
            "result": result
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/scenarios/1stop-vs-2stop", methods=["POST"])
def scenario_1stop_vs_2stop():
    """
    Run 1-Stop vs 2-Stop Scenario
    Paper: Membandingkan total waktu antara strategi satu pit stop versus dua pit stop.
    Tujuannya menentukan apakah kecepatan ban di awal sepadan dengan tambahan satu kali penalti pit lane.
    """
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    
    try:
        tester = ScenarioTester(circuit_name=circuit_name, random_seed=42)
        result = tester.run_1_stop_vs_2_stop_scenario()
        return jsonify({
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "scenario_type": "1stop_vs_2stop"
            },
            "result": result
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/scenarios/weather-transition", methods=["POST"])
def scenario_weather_transition():
    """
    Run Weather Transition Scenario: Dry→Wet or Wet→Dry
    Paper: Perubahan kondisi lintasan selama balapan berlangsung.
    Tingkat pit stop saat perubahan cuaca merupakan faktor yang sangat menentukan total race time.
    """
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    transition_type = data.get("transition_type", "dry_to_wet")  # or "wet_to_dry"
    transition_lap = data.get("transition_lap")
    
    circuit_config = get_circuit_config(circuit_name)
    total_laps = int(circuit_config["total_laps"])
    
    if transition_lap is None:
        transition_lap = int(round(total_laps * 0.5))
    else:
        transition_lap = min(max(int(transition_lap), 5), total_laps - 10)
    
    try:
        tester = ScenarioTester(circuit_name=circuit_name, random_seed=42)
        result = tester.run_weather_transition_scenario(
            transition_type=transition_type,
            transition_lap=transition_lap
        )
        return jsonify({
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "scenario_type": "weather_transition"
            },
            "result": result
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/scenarios/best-combination", methods=["POST"])
def scenario_best_combination():
    """
    Run Best Combination Finder Scenario
    Paper: Mencoba mengkombinasikan semua strategi di sirkuit yang telah dibuat
    lalu mencarikan kombinasi terbaik yang menghasilkan total race time paling kecil.
    """
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    max_combinations = int(data.get("max_combinations", 30))
    
    try:
        tester = ScenarioTester(circuit_name=circuit_name, random_seed=42)
        result = tester.run_best_combination_scenario(max_combinations=max_combinations)
        return jsonify({
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "scenario_type": "best_combination"
            },
            "result": result
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/api/scenarios/all", methods=["POST"])
def run_all_scenarios():
    """
    Run ALL paper scenarios at once for comprehensive analysis.
    Combines: Baseline, 1-Stop vs 2-Stop, Weather Transitions, Best Combination
    """
    data = request.get_json(silent=True) or {}
    circuit_name = data.get("circuit", "Silverstone")
    
    try:
        tester = ScenarioTester(circuit_name=circuit_name, random_seed=42)
        
        # Run all scenarios
        baseline = tester.run_baseline_scenario()
        comparison = tester.run_1_stop_vs_2_stop_scenario()
        weather_dry_to_wet = tester.run_weather_transition_scenario("dry_to_wet")
        weather_wet_to_dry = tester.run_weather_transition_scenario("wet_to_dry")
        best_combo = tester.run_best_combination_scenario()
        
        summary = tester.get_all_results_summary()
        
        return jsonify({
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "scenario_type": "comprehensive"
            },
            "circuit": circuit_name,
            "scenarios": {
                "baseline": baseline,
                "1stop_vs_2stop": comparison,
                "weather_dry_to_wet": weather_dry_to_wet,
                "weather_wet_to_dry": weather_wet_to_dry,
                "best_combination": best_combo
            },
            "summary": summary
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    print("Integrated F1 simulation backend")
    print("Listening on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
