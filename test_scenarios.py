#!/usr/bin/env python
"""Test scenario endpoints"""

from analysis.scenario_testing import ScenarioTester

if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING PAPER-ALIGNED SCENARIOS")
    print("="*60)
    
    tester = ScenarioTester(circuit_name="Silverstone", random_seed=42)
    
    # Test 1: Baseline
    print("\n1. BASELINE SCENARIO (Medium → Hard)")
    print("-" * 60)
    baseline = tester.run_baseline_scenario()
    print(f"   Total Race Time: {baseline['total_race_time_formatted']}")
    print(f"   Strategy: {baseline['strategy_name']}")
    print(f"   Pit at lap: {baseline['pit_lap']}")
    print(f"   Total pit time lost: {baseline['total_pit_time_lost']:.1f}s")
    
    # Test 2: 1-Stop vs 2-Stop
    print("\n2. 1-STOP VS 2-STOP SCENARIO")
    print("-" * 60)
    comparison = tester.run_1_stop_vs_2_stop_scenario()
    for strat in comparison['strategies']:
        print(f"   {strat['strategy_name']}: {strat['total_race_time_formatted']}")
    print(f"   Best: {comparison['best_strategy']}")
    print(f"   Delta: {comparison['time_delta']:.1f}s")
    
    # Test 3: Weather Dry-to-Wet
    print("\n3. WEATHER TRANSITION: DRY → WET")
    print("-" * 60)
    weather_dtw = tester.run_weather_transition_scenario("dry_to_wet")
    print(f"   Strategy: {weather_dtw['strategy']['stints']}")
    print(f"   Transition at lap: {weather_dtw['transition_lap']}")
    print(f"   {weather_dtw['critical_timing']}")
    
    # Test 4: Best Combination
    print("\n4. BEST COMBINATION FINDER")
    print("-" * 60)
    best_combo = tester.run_best_combination_scenario(max_combinations=20)
    print(f"   Tested combinations: {best_combo['total_combinations_tested']}")
    print(f"   Best strategy: {best_combo['best_strategy']['name']}")
    print(f"   Best time: {best_combo['best_strategy']['total_race_time']:.1f}s")
    print("\n   Top 5:")
    for i, strat in enumerate(best_combo['top_5_strategies'][:5], 1):
        print(f"      {i}. {strat['strategy_name']}: {strat['total_race_time_formatted']}")
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*60)

