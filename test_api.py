#!/usr/bin/env python
"""Test Flask API endpoints for scenarios"""

import json
from backend.app import app

if __name__ == "__main__":
    client = app.test_client()
    
    print("\n" + "="*60)
    print("TESTING FLASK API SCENARIO ENDPOINTS")
    print("="*60)
    
    # Test 1: Baseline endpoint
    print("\n1. Testing /api/scenarios/baseline")
    print("-" * 60)
    response = client.post(
        "/api/scenarios/baseline",
        json={"circuit": "Silverstone"},
        content_type="application/json"
    )
    print(f"Status: {response.status_code}")
    data = json.loads(response.data)
    if response.status_code == 200:
        result = data.get("result", {})
        print(f"Scenario: {result.get('scenario_name')}")
        print(f"Total Race Time: {result.get('total_race_time_formatted')}")
        print(f"Strategy: {result.get('strategy_name')}")
        print(f"Status: ✓ SUCCESS")
    else:
        print(f"Error: {data.get('error')}")
    
    # Test 2: 1-Stop vs 2-Stop endpoint
    print("\n2. Testing /api/scenarios/1stop-vs-2stop")
    print("-" * 60)
    response = client.post(
        "/api/scenarios/1stop-vs-2stop",
        json={"circuit": "Silverstone"},
        content_type="application/json"
    )
    print(f"Status: {response.status_code}")
    data = json.loads(response.data)
    if response.status_code == 200:
        result = data.get("result", {})
        print(f"Scenario: {result.get('scenario_name')}")
        print(f"Best Strategy: {result.get('best_strategy')}")
        print(f"Time Delta: {result.get('time_delta')}s")
        print(f"Strategies Tested: {len(result.get('strategies', []))}")
        print(f"Status: ✓ SUCCESS")
    else:
        print(f"Error: {data.get('error')}")
    
    # Test 3: Weather transition endpoint
    print("\n3. Testing /api/scenarios/weather-transition")
    print("-" * 60)
    response = client.post(
        "/api/scenarios/weather-transition",
        json={"circuit": "Silverstone", "transition_type": "dry_to_wet"},
        content_type="application/json"
    )
    print(f"Status: {response.status_code}")
    data = json.loads(response.data)
    if response.status_code == 200:
        result = data.get("result", {})
        print(f"Scenario: {result.get('scenario_name')}")
        print(f"Transition Type: {result.get('transition_type')}")
        print(f"Pit Lap: {result.get('transition_lap')}")
        print(f"Status: ✓ SUCCESS")
    else:
        print(f"Error: {data.get('error')}")
    
    # Test 4: Best combination endpoint
    print("\n4. Testing /api/scenarios/best-combination")
    print("-" * 60)
    response = client.post(
        "/api/scenarios/best-combination",
        json={"circuit": "Silverstone", "max_combinations": 20},
        content_type="application/json"
    )
    print(f"Status: {response.status_code}")
    data = json.loads(response.data)
    if response.status_code == 200:
        result = data.get("result", {})
        print(f"Scenario: {result.get('scenario_name')}")
        print(f"Combinations Tested: {result.get('total_combinations_tested')}")
        print(f"Best Strategy: {result.get('best_strategy', {}).get('name')}")
        best_time = result.get('best_strategy', {}).get('total_race_time')
        if best_time:
            print(f"Best Time: {best_time:.1f}s")
        print(f"Status: ✓ SUCCESS")
    else:
        print(f"Error: {data.get('error')}")
    
    # Test 5: All scenarios endpoint
    print("\n5. Testing /api/scenarios/all")
    print("-" * 60)
    response = client.post(
        "/api/scenarios/all",
        json={"circuit": "Silverstone"},
        content_type="application/json"
    )
    print(f"Status: {response.status_code}")
    data = json.loads(response.data)
    if response.status_code == 200:
        scenarios = data.get("scenarios", {})
        print(f"Circuit: {data.get('circuit')}")
        print(f"Scenarios Executed: {list(scenarios.keys())}")
        print(f"Status: ✓ SUCCESS")
    else:
        print(f"Error: {data.get('error')}")
    
    print("\n" + "="*60)
    print("ALL ENDPOINT TESTS COMPLETED!")
    print("="*60)

