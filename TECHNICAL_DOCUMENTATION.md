# DOKUMENTASI TEKNIS - F1 PIT STOP SIMULATION

## 1. INSTALASI DAN SETUP

### 1.1 Prerequisite

- Python 3.10+
- pip package manager
- Git

### 1.2 Instalasi

```bash
# Clone atau extract proyek
cd UAS-Simulasi-Pemodelan

# Install dependencies
pip install -r requirements.txt

# Atau install backend dependencies jika menggunakan Flask API
pip install -r backend/requirements.txt
```

### 1.3 Verifikasi Instalasi

```bash
# Test import modul inti
python -c "from core.race_simulator import RaceSimulator; print('✓ Core modules loaded')"

# Test import optimization
python -c "from optimization.genetic_optimizer import GeneticStrategyOptimizer; print('✓ Optimization modules loaded')"

# Test Flask app
python backend/app.py
# Harusnya server berjalan di http://localhost:5000
```

---

## 2. STRUKTUR KODE

### 2.1 Core Modules (core/)

#### core/tire_model.py
```python
class Tire:
    """Model ban dengan degradasi, thermal, dan graining."""
    
    def __init__(compound: str, track_wetness: float = 0.0):
        # Initialize tire parameters dari TIRE_COMPOUNDS config
        self.compound = compound
        self.tire_age = 0
        self.track_wetness = track_wetness
        
    def get_grip(age: int, temperature: Optional[float] = None) -> float:
        """Return grip coefficient untuk age dan temperature tertentu"""
        # Kombinasi dari:
        # - Base degradation (progressive)
        # - Cliff point penalty
        # - Temperature factor
        # - Graining effect
        
    def estimate_temperature(age: int) -> float:
        """Estimate ban temperature menggunakan sigmoid warmup curve"""
```

**Parameter Utama Tire**:
- `initial_grip`: Grip maksimum ban baru (0.91-1.00)
- `degradation_rate`: Laju wear per lap
- `cliff_point`: Lap ke berapa cliff terjadi (18-40 laps)
- `cliff_penalty`: Magnitude drop di cliff point
- `optimal_temp`: Temperature optimal (72-102°C)
- `warmup_laps`: Laps untuk mencapai grip max (2-3)

#### core/strategy.py
```python
class Strategy:
    """Representasi pit stop strategy."""
    
    name: str  # e.g., "2-Stop: S->M->H"
    stints: List[Tuple[str, int, int]]  # [(compound, lap_start, lap_end), ...]
    total_laps: int
    
    @staticmethod
    def from_custom_stints(custom_stints, total_laps):
        """Create strategy dari custom stint definition"""
        
    @staticmethod
    def load_all_strategies(circuit_name) -> List[Strategy]:
        """Load semua predefined strategies untuk circuit"""
```

**Format Stint**:
```python
stint = ("Soft", 1, 14)  # Soft compound, lap 1-14
# Pit stop pada lap 14, menggantinya dengan compound untuk stint berikutnya
```

#### core/race_simulator.py
```python
class RaceSimulator:
    """Simulasi one driver full race distance."""
    
    def __init__(
        strategy: Strategy,
        circuit_name: str = "Silverstone",
        enable_variability: bool = True,
        enable_safety_car: bool = True,
        track_wetness: float = 0.0,
        random_seed: Optional[int] = None
    ):
        pass
    
    def simulate() -> None:
        """Jalankan simulasi lap-by-lap"""
        for lap in range(1, total_laps + 1):
            # Update tire age
            # Check if pit stop pada lap ini
            # Calculate lap time
            # Add to race_data
            
    def get_summary() -> Dict:
        """Return ringkasan hasil simulasi"""
        return {
            'total_race_time': float,
            'avg_lap_time': float,
            'fastest_lap': float,
            'pit_stop_count': int,
            'tire_history': List
        }
```

**Key Methods**:
- `simulate()`: Run the full race
- `get_summary()`: Get aggregated results
- `get_detailed_data()`: Get lap-by-lap data as DataFrame

#### core/multi_car_race.py
```python
class MultiCarRace:
    """Simulasi multiple drivers dengan traffic modeling."""
    
    def __init__(
        pairings: List[Tuple[str, Strategy]],  # (driver_name, strategy)
        circuit_name: str,
        random_seed: Optional[int] = None
    ):
        pass
    
    def simulate() -> pd.DataFrame:
        """Run multi-car simulation dengan overtake logic"""
        # Simultaneous lap progression
        # Gap-based overtake probability
        # Track position adjustment
        # Return lap-by-lap data untuk all drivers
        
    def get_final_standings() -> pd.DataFrame:
        """Return final positions dan times"""
```

#### core/track_maps.py
```python
def get_track_map(circuit_name: str) -> Dict:
    """Return track geometry (SVG path) untuk circuit"""
    # Load dari _external/f1-circuits-svg/circuits/detailed/
    # Return SVG path untuk minimap rendering
    
    return {
        'path': str,  # SVG path
        'name': str,
        'length': int,  # meters
        'corners': List[Dict]  # [{'name', 'speed', 'position'}, ...]
    }
```

### 2.2 Optimization Modules (optimization/)

#### optimization/genetic_optimizer.py
```python
class GeneticStrategyOptimizer:
    """Genetic Algorithm untuk optimize pit stop strategies."""
    
    def __init__(
        circuit_name: str,
        generations: int = 100,
        population_size: int = 50
    ):
        pass
    
    def run(verbose: bool = True, output_dir: str = None) -> List[RankedStrategy]:
        """
        Run GA untuk find optimal strategy.
        
        Returns top ranked strategies dengan chromosome,
        fitness score, dan race time estimates.
        """
```

**Chromosome Format**:
```python
# Format: [pit_lap_1, compound_1, pit_lap_2, compound_2, ...]
# Example: [15, "Soft", 33, "Medium", "Hard"]
# Pit stop lap 15 dengan Soft, pit lap 33 dengan Medium, finish Hard
```

**GA Parameters**:
- Population size: 50
- Generations: 100 (atau lebih)
- Crossover probability: 0.8
- Mutation probability: 0.1
- Selection: Tournament selection (size 3)

#### optimization/monte_carlo.py
```python
class MonteCarloSimulator:
    """Monte Carlo untuk evaluate strategies under uncertainty."""
    
    def __init__(
        strategies: List[Strategy],
        circuit_name: str,
        n_iterations: int = 1000
    ):
        pass
    
    def run(verbose: bool = True) -> None:
        """Run MC simulations dengan random seeds"""
        
    def get_comparison_dataframe() -> pd.DataFrame:
        """Return comparison statistics untuk all strategies"""
        # Columns: strategy, mean, std, min, max, percentile_5, percentile_95
```

#### optimization/rl_agent.py
```python
class QLearningPitAgent:
    """Reinforcement Learning agent untuk learn optimal pit timing."""
    
    def __init__(
        circuit_name: str,
        episodes: int = 500
    ):
        self.q_table = {}  # state -> (action -> value)
        
    def train(output_dir: str = None) -> Dict:
        """Train Q-learning agent"""
        
        return {
            'pit_plan': Dict[int, str],  # lap -> "pit" atau "stay_out"
            'comparison': {
                'best_monte_carlo_strategy': str,
                'best_monte_carlo_time': float
            }
        }
```

**State Space**:
```python
state = (
    lap_number,              # 1-52
    residual_tire_age,       # 0-50
    track_wetness,           # 0.0-1.0
    relative_position        # (ahead/behind others)
)
```

**Action Space**:
```python
action in ["pit_now", "stay_out"]
```

### 2.3 Analysis Modules (analysis/)

#### analysis/sensitivity_analysis.py
```python
class SensitivityAnalyzer:
    """Analyze sensitivity race time terhadap parameter variations."""
    
    def __init__(circuit_name: str):
        pass
    
    def run(output_dir: str = None) -> pd.DataFrame:
        """
        Vary parameters dan measure impact pada race time.
        
        Returns DataFrame dengan:
        - Parameter
        - Baseline value
        - Min/max variation
        - Sensitivity coefficient
        - Elasticity
        """
```

**Parameter yang Di-test**:
- base_lap_time: ±5%
- pit_lane_delta: ±2 seconds
- degradation_rate: 0.8x, 1.0x, 1.2x
- track_wetness: 0.0, 0.3, 0.7, 1.0

#### analysis/validation_fastf1.py
```python
class FastF1Validator:
    """Validate simulation terhadap real FastF1 race data."""
    
    def __init__(circuit_name: str):
        pass
    
    def validate_top_finishers(output_dir: str = None) -> List[ValidationResult]:
        """
        Compare sim lap times vs actual data.
        
        Returns RMSE, MAE, R² untuk each driver.
        """
        
    def calibrate(output_dir: str = None) -> Dict:
        """
        Calibrate simulation parameters untuk match real data.
        
        Returns adjusted parameters yang minimize validation error.
        """
```

**Metrics**:
- RMSE: Root Mean Square Error (should be < 2.0s)
- MAE: Mean Absolute Error
- R²: Coefficient of determination (should be > 0.85)

### 2.4 Backend (backend/)

#### backend/app.py
```python
# Flask REST API endpoints

@app.route('/api/circuits', methods=['GET'])
def get_circuits() -> Dict:
    """Get semua circuit configurations"""

@app.route('/api/compounds', methods=['GET'])
def get_compounds() -> Dict:
    """Get tire compounds untuk selected circuit"""

@app.route('/api/strategies', methods=['GET'])
def get_strategies() -> Dict:
    """Get predefined strategies"""

@app.route('/api/simulate/telemetry', methods=['POST'])
def simulate_telemetry() -> Dict:
    """
    Simulate single race dan return lap-by-lap telemetry.
    
    Request body:
    {
        "circuit": "Silverstone",
        "strategy_name": "1-Stop: M->H",
        "custom_stints": null,  # atau define custom strategy
        "track_wetness": 0.0,
        "enable_variability": true,
        "enable_safety_car": true,
        "weather_evolution": true,
        "weather_mean_target": 0.3,
        "weather_volatility": 0.1
    }
    
    Response:
    {
        "circuit": str,
        "strategy": str,
        "total_race_time": float,
        "avg_lap_time": float,
        "laps": [{lap, time, compound, tire_age, pit_stop, ...}, ...],
        "weather_timeline": [0.0, 0.02, 0.05, ...],
        "track_map": {...}
    }
    """

@app.route('/api/simulate/multi-car', methods=['POST'])
def simulate_multi_car() -> Dict:
    """
    Simulate multiple drivers dengan traffic.
    
    Request body:
    {
        "circuit": "Silverstone",
        "drivers": [
            {"name": "VER", "strategy_name": "1-Stop: M->H"},
            {"name": "LEC", "strategy_name": "2-Stop: S->M->H"},
            ...
        ],
        "track_wetness": 0.0
    }
    
    Response:
    {
        "standings": [{position, driver, total_time}, ...],
        "laps": [{lap, drivers: [{driver, position, gap, ...}]}, ...],
        "weather_timeline": [...],
        "meta": {start_time, duration, circuit, ...}
    }
    """

@app.route('/api/optimize/genetic', methods=['POST'])
def optimize_genetic() -> Dict:
    """
    Run genetic algorithm optimization.
    
    Request:
    {
        "circuit": "Silverstone",
        "generations": 50,
        "population_size": 30
    }
    """

@app.route('/api/analyze/sensitivity', methods=['POST'])
def analyze_sensitivity() -> Dict:
    """
    Run sensitivity analysis.
    
    Returns parameter sensitivity ranking.
    """
```

---

## 3. API USAGE EXAMPLES

### 3.1 Command Line (CLI)

```bash
# Single race simulation
python main.py --circuit Silverstone --mode single --strategy "1-Stop: M->H"

# Multi-car race
python main.py --circuit Monaco --mode multi

# Genetic optimization (100 generations)
python main.py --circuit Silverstone --mode optimize --iterations 100

# FastF1 validation
python main.py --circuit Silverstone --mode validate

# Generate report (Monte Carlo + Sensitivity)
python main.py --circuit Silverstone --mode report --iterations 500
```

### 3.2 Python API

#### Example 1: Single Race Simulation

```python
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies

# Load strategy
strategies = load_all_strategies("Silverstone")
strategy = strategies[0]  # "1-Stop: M->H"

# Create simulator
simulator = RaceSimulator(
    strategy=strategy,
    circuit_name="Silverstone",
    enable_variability=True,
    enable_safety_car=True,
    track_wetness=0.1,  # Slightly wet
    random_seed=42
)

# Run simulation
simulator.simulate()

# Get results
summary = simulator.get_summary()
print(f"Total time: {summary['total_race_time_formatted']}")
print(f"Avg lap: {summary['avg_lap_time']:.2f}s")

# Get detailed data
detailed = simulator.get_detailed_race_data()
print(detailed.head())
```

#### Example 2: Multi-Car Race

```python
from core.multi_car_race import MultiCarRace
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")

# Pair drivers dengan strategies
pairings = [
    ("Verstappen", strategies[0]),  # 1-Stop: M->H
    ("Leclerc", strategies[1]),     # 1-Stop: S->H
    ("Hamilton", strategies[2]),    # 2-Stop: S->M->H
    ("Norris", strategies[3]),      # 2-Stop: S->H->M
]

# Run multi-car
multi_race = MultiCarRace(
    pairings=pairings,
    circuit_name="Silverstone",
    random_seed=42
)

standings = multi_race.get_final_standings()
print(standings)

# Get detailed lap data
lap_data = multi_race.simulate()
print(lap_data[['lap', 'driver', 'time', 'position', 'gap']].head())
```

#### Example 3: Genetic Optimization

```python
from optimization.genetic_optimizer import GeneticStrategyOptimizer

optimizer = GeneticStrategyOptimizer(
    circuit_name="Silverstone",
    generations=100
)

best_strategies = optimizer.run(verbose=True, output_dir="results")

for rank in best_strategies[:3]:
    print(f"Rank {rank.rank}: {rank.strategy.name}")
    print(f"  Race Time: {rank.total_race_time:.1f}s")
    print(f"  Chromosome: {rank.chromosome}")
```

#### Example 4: Monte Carlo Analysis

```python
from optimization.monte_carlo import MonteCarloSimulator
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")

mc = MonteCarloSimulator(
    strategies=strategies,
    circuit_name="Silverstone",
    n_iterations=1000
)

mc.run(verbose=True)

# Get comparison
comparison = mc.get_comparison_dataframe()
print(comparison[['strategy', 'mean', 'std', 'min', 'max']])

# Get best strategy
best = mc.get_best_strategy()
print(f"Best strategy (by mean): {best}")
```

#### Example 5: FastF1 Validation

```python
from analysis.validation_fastf1 import FastF1Validator

validator = FastF1Validator(circuit_name="Monaco")

# Validate top finishers
results = validator.validate_top_finishers(output_dir="validation")
for result in results:
    print(f"{result.driver}: RMSE={result.rmse:.2f}s, MAE={result.mae:.2f}s, R²={result.r_squared:.3f}")

# Calibrate parameters
calibration = validator.calibrate()
print(f"Calibrated params: {calibration}")
```

#### Example 6: Sensitivity Analysis

```python
from analysis.sensitivity_analysis import SensitivityAnalyzer

analyzer = SensitivityAnalyzer(circuit_name="Silverstone")

sensitivity = analyzer.run(output_dir="sensitivity")
print(sensitivity)

# Sensitivity ranking
ranked = sensitivity.sort_values('sensitivity_coefficient', ascending=False)
print(f"Top parameters by sensitivity:")
for _, row in ranked.head(5).iterrows():
    print(f"  {row['parameter']}: {row['sensitivity_coefficient']:.3f}")
```

### 3.3 REST API Examples

#### Start Flask Server

```bash
cd backend
python app.py
# Server running on http://localhost:5000
```

#### Example API Calls

```bash
# Get available circuits
curl http://localhost:5000/api/circuits

# Get strategies
curl http://localhost:5000/api/strategies?circuit=Silverstone

# Simulate race
curl -X POST http://localhost:5000/api/simulate/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "circuit": "Silverstone",
    "strategy_name": "1-Stop: M->H",
    "track_wetness": 0.1,
    "weather_evolution": true
  }'

# Simulate multi-car
curl -X POST http://localhost:5000/api/simulate/multi-car \
  -H "Content-Type: application/json" \
  -d '{
    "circuit": "Silverstone",
    "drivers": [
      {"name": "VER", "strategy_name": "1-Stop: M->H"},
      {"name": "LEC", "strategy_name": "2-Stop: S->M->H"}
    ],
    "track_wetness": 0.0
  }'

# Run genetic optimizer
curl -X POST http://localhost:5000/api/optimize/genetic \
  -H "Content-Type: application/json" \
  -d '{
    "circuit": "Silverstone",
    "generations": 50,
    "population_size": 30
  }'
```

---

## 4. CONFIGURATION

### 4.1 config.py Struktur

```python
# Circuit definitions
CIRCUITS = {
    "Silverstone": {
        "pit_lane_delta": 20.0,      # seconds
        "base_lap_time": 90.0,       # seconds
        "degradation_multiplier": 1.0,
        "total_laps": 52,
        "overtake_difficulty": 0.55,  # 0=easy, 1=hard
        "rain_probability": 0.08
    },
    # ... other circuits
}

# Tire compound definitions
TIRE_COMPOUNDS = {
    "Soft": {
        "initial_grip": 1.00,
        "degradation_rate": 0.008,
        "cliff_point": 18,
        "cliff_penalty": 0.0030,
        "deg_exponent": 1.30,
        "optimal_temp": 102.0,
        "warmup_laps": 2,
        # ... more parameters
    },
    # ... other compounds
}

# Strategy templates
STRATEGY_TEMPLATES = {
    "1-Stop: M->H": {
        "compounds": ["Medium", "Hard"],
        "pit_ratios": [25/52],  # pit pada 25/52 of race
        "description": "Balanced one-stop..."
    },
    # ... other strategies
}
```

### 4.2 Custom Configuration

Untuk modify configuration tanpa edit config.py:

```python
from core.race_simulator import RaceSimulator
from core.strategy import Strategy

# Custom simulation overrides
overrides = {
    "base_lap_time": 88.0,  # lebih cepat dari default
    "pit_lane_delta": 19.0   # pit lane lebih cepat
}

simulator = RaceSimulator(
    strategy=strategy,
    circuit_name="Silverstone",
    simulation_overrides=overrides
)
```

---

## 5. OUTPUT DAN RESULT FORMAT

### 5.1 Race Simulation Output

```json
{
  "circuit": "Silverstone",
  "strategy": "1-Stop: M->H",
  "total_race_time": 4691.8,
  "total_race_time_formatted": "1:18:11.8",
  "avg_lap_time": 90.22,
  "fastest_lap": 87.4,
  "pit_stop_count": 1,
  "pit_stop_times": [2.84],
  "laps": [
    {
      "lap": 1,
      "compound": "Medium",
      "tire_age": 0,
      "lap_time": 92.3,
      "pit_stop": false,
      "position": 1,
      "weather": 0.0
    },
    {
      "lap": 25,
      "compound": "Medium",
      "tire_age": 24,
      "lap_time": 90.8,
      "pit_stop": true,
      "pit_stop_duration": 2.84,
      "position": 1,
      "weather": 0.05
    },
    {
      "lap": 26,
      "compound": "Hard",
      "tire_age": 0,
      "lap_time": 91.2,
      "pit_stop": false,
      "position": 1,
      "weather": 0.05
    }
  ]
}
```

### 5.2 Multi-Car Output

```json
{
  "standings": [
    {"position": 1, "driver": "VER", "total_time": 4680.2},
    {"position": 2, "driver": "LEC", "total_time": 4685.1},
    {"position": 3, "driver": "HAM", "total_time": 4692.4}
  ],
  "laps": [
    {
      "lap": 1,
      "drivers": [
        {"driver": "VER", "position": 1, "gap": 0.0, "lap_time": 92.4},
        {"driver": "LEC", "position": 2, "gap": 0.3, "lap_time": 92.7},
        {"driver": "HAM", "position": 3, "gap": 1.2, "lap_time": 93.6}
      ]
    }
  ],
  "meta": {
    "circuit": "Silverstone",
    "total_laps": 52,
    "duration_seconds": 4692.4
  }
}
```

---

## 6. TROUBLESHOOTING

### 6.1 Common Issues

**Issue: ImportError pada core modules**
```
Solution: Pastikan Anda menjalankan dari root directory UAS-Simulasi-Pemodelan/
          PYTHONPATH harus include root directory
```

**Issue: FastF1 API timeout**
```
Solution: FastF1 mungkin down atau rate limit. Coba lagi dalam beberapa menit.
          Atau set offline mode di config untuk gunakan cached data.
```

**Issue: Memory error pada large optimization**
```
Solution: Reduce population_size atau generations untuk GA
          Reduce n_iterations untuk Monte Carlo
```

### 6.2 Performance Optimization

**Untuk mempercepat simulasi**:
```python
# Disable variability (deterministic)
enable_variability=False,

# Disable safety car
enable_safety_car=False,

# Reduce weather evolution complexity
# (langsung set track_wetness value)
```

---

## 7. VERSIONING DAN DEPENDENCIES

```
Python: 3.10+
numpy: 1.26+
pandas: 2.2+
matplotlib: 3.9+
scipy: 1.12+
Flask: 3.0+
fastf1: 3.4+
```

Untuk upgrade dependencies dengan aman:
```bash
pip install --upgrade -r requirements.txt
```

---

## 8. DEBUGGING

### Enable verbose logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Sekarang akan print debug messages
simulator.simulate()  # akan show detailed progress
```

### Profile performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run expensive operation
optimizer.run()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative').print_stats(10)  # Top 10 slowest
```

---

**End of Technical Documentation**


