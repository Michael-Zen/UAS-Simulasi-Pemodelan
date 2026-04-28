# USER GUIDE - F1 PIT STOP SIMULATION

Panduan lengkap untuk menggunakan sistem simulasi strategi pit stop Formula 1.

---

## 1. QUICK START (5 Menit)

### 1.1 Setup Awal

```bash
# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Test basic simulation
python main.py --circuit Silverstone --mode single

# Output akan menunjukkan:
# Circuit  : Silverstone
# Strategy : 1-Stop: M->H
# Total    : 1:18:11.8
# Avg lap  : 90.22s
# Fastest  : 87.40s
```

### 1.2 Jalankan Web Interface

```bash
# Terminal 1: Start Flask backend
cd backend
python app.py

# Terminal 2: Buka browser
# Navigate ke http://localhost:5000
# Klik pada Strategy Simulator tab untuk interactive experimentation
```

---

## 2. FITUR UTAMA DAN CARA MENGGUNAKAN

### 2.1 Single Race Simulation

**Tujuan**: Simulasikan satu driver dengan satu strategi untuk satu balapan.

**Cara Menggunakan**:

```bash
python main.py --circuit Silverstone --mode single --strategy "2-Stop: S->M->H"
```

**Output yang Didapat**:
- Total race time
- Average lap time
- Fastest lap
- Lap-by-lap breakdown
- Pit stop history

**Use Case**:
- Understand bagaimana satu strategi perform di satu circuit
- Compare dua strategi dengan manual trial

### 2.2 Multi-Car Race

**Tujuan**: Simulasikan kompetisi antara multiple drivers dengan strategies berbeda.

**Cara Menggunakan**:

```bash
python main.py --circuit Monaco --mode multi
```

```python
# Atau via code:
from core.multi_car_race import MultiCarRace
from core.strategy import load_all_strategies

strategies = load_all_strategies("Monaco")
pairings = [
    ("VER", strategies[0]),   # 1-Stop: M->H
    ("LEC", strategies[1]),   # 1-Stop: S->H
    ("HAM", strategies[3]),   # 2-Stop: S->M->H
    ("NOR", strategies[2]),   # 2-Stop: S->H->M
]

race = MultiCarRace(pairings, "Monaco", random_seed=42)
standings = race.get_final_standings()
print(standings)
```

**Output**:
- Final standings (positions dan times)
- Lap-by-lap position changes
- Gap progression antar drivers
- Overtake events

**Use Case**:
- Analyze head-to-head competition
- Understand traffic dynamics
- Evaluate undercut/overcut strategies

### 2.3 Strategy Optimization (Genetic Algorithm)

**Tujuan**: Find optimal pit stop timing dan tire compound selection.

**Cara Menggunakan**:

```bash
# Via CLI
python main.py --circuit Silverstone --mode optimize --iterations 100

# Atau via code:
from optimization.genetic_optimizer import GeneticStrategyOptimizer

optimizer = GeneticStrategyOptimizer(
    circuit_name="Silverstone",
    generations=100
)

best_strategies = optimizer.run(verbose=True, output_dir="results")

for idx, ranked in enumerate(best_strategies[:5], 1):
    print(f"{idx}. {ranked.strategy.name}: {ranked.total_race_time:.1f}s")
    print(f"   Chromosome: {ranked.chromosome}")
```

**Output**:
- Top 5-10 best strategies (dengan race times)
- Chromosome representation (pit laps dan compounds)
- Convergence history
- Comparison vs baseline strategies

**Interpretasi Hasil**:
- Best strategy menunjukkan optimal pit timing untuk circuit tersebut
- Chromosome nilai pit lap bisa dibandingkan dengan predefined templates
- Jika best time improvement kecil (< 2%), template sudah near-optimal

**Use Case**:
- Research: Understand optimal pit stop timing scientifically
- Team strategy dev: Find new strategy ideas
- Academic analysis: Analyze trade-offs dalam pit stop decisions

### 2.4 Monte Carlo Analysis

**Tujuan**: Evaluate robustness dan risk profiling dari multiple strategies.

**Cara Menggunakan**:

```bash
# Via CLI - generate report with MC analysis
python main.py --circuit Silverstone --mode report --iterations 500

# Via code:
from optimization.monte_carlo import MonteCarloSimulator
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")

mc = MonteCarloSimulator(
    strategies=strategies,
    circuit_name="Silverstone",
    n_iterations=500
)

mc.run(verbose=True)

# Get results
comparison = mc.get_comparison_dataframe()
print(comparison[['strategy', 'mean', 'std', 'min', 'max', 'percentile_95']])
```

**Output**:
- Mean race time untuk each strategy
- Standard deviation (measure of consistency)
- Min/Max times
- 5th dan 95th percentile (risk metrics)
- Win probability untuk each strategy

**Interpretasi**:
- Strategy dengan low std lebih konsisten
- Strategy dengan low 5th percentile lebih robust terhadap variability
- Strategy dengan high mean tapi low std = safer choice
- Strategy dengan low mean tapi high std = riskier but potentially rewarding

**Use Case**:
- Team decision making: Choose strategy balancing risk/reward
- Academic analysis: Understand uncertainty dalam pit stop decisions
- Data science: Analyze probability distributions

### 2.5 Sensitivity Analysis

**Tujuan**: Identify yang parameter paling kritis mempengaruhi hasil.

**Cara Menggunakan**:

```bash
python main.py --circuit Silverstone --mode report --iterations 500

# Report akan include sensitivity analysis section

# Atau via code:
from analysis.sensitivity_analysis import SensitivityAnalyzer

analyzer = SensitivityAnalyzer(circuit_name="Silverstone")
sensitivity = analyzer.run(output_dir="results")

ranked = sensitivity.sort_values('sensitivity_coefficient', ascending=False)
print(ranked[['parameter', 'sensitivity_coefficient', 'elasticity']])
```

**Output**:
- Sensitivity coefficient untuk each parameter
- Elasticity (% change dalam output per % change dalam input)
- Ranking importance

**Interpretasi**:
- High sensitivity coefficient = parameter penting untuk optimize
- Elasticity > 0.5 = significant impact
- Elasticity < 0.1 = dapat diabaikan

**Use Case**:
- Understand yang factors paling penting untuk pit strategy
- Focus optimization efforts pada high-sensitivity parameters
- Academic research: Publish findings tentang critical variables

### 2.6 Model Validation (FastF1)

**Tujuan**: Validate simulator terhadap real race data.

**Cara Menggunakan**:

```bash
python main.py --circuit Silverstone --mode validate

# Output akan show RMSE, MAE, R² untuk top finishers

# Via code:
from analysis.validation_fastf1 import FastF1Validator

validator = FastF1Validator(circuit_name="Monaco")

results = validator.validate_top_finishers(output_dir="results")
for result in results:
    print(f"{result.driver}:")
    print(f"  RMSE: {result.rmse:.2f}s (lower is better)")
    print(f"  MAE:  {result.mae:.2f}s")
    print(f"  R²:   {result.r_squared:.3f}")
    print()

# Calibrate parameters untuk match real data
calibration = validator.calibrate()
print(f"Calibrated base_lap_time: {calibration['base_lap_time']:.1f}s")
```

**Output**:
- RMSE (Root Mean Square Error) - absolute error measure
- MAE (Mean Absolute Error)
- R² (coefficient of determination)
- Calibrated parameters untuk improve match

**Interpreting Metrics**:
- RMSE < 2.0s: Model very accurate
- RMSE 2-5s: Model reasonably accurate
- RMSE > 5s: Model needs calibration
- R² > 0.85: Model explains 85%+ of variance
- R² > 0.90: Model very good fit

**Use Case**:
- Ensure simulator realism
- Academic credibility: Validate model terhadap ground truth
- Continuous improvement: Track if simulation improve

---

## 3. WEB INTERFACE TUTORIAL

### 3.1 Starting the Web App

```bash
# Terminal
cd backend
python app.py

# Browser
# Open http://localhost:5000
```

### 3.2 Home Page

Menampilkan statistics dan quick links:
- Total circuits supported
- Available strategies
- Latest simulation results

### 3.3 Strategy Simulator Tab

**Features**:
1. **Circuit Selection**: Dropdown untuk pilih circuit
2. **Strategy Selection**: Pre-defined strategies atau custom stints
3. **Parameters**:
   - Track wetness (0.0 = dry to 1.0 = full wet)
   - Weather evolution toggle
   - Enable safety car toggle
4. **Run Simulation**: Click untuk simulate
5. **Results**:
   - Race time breakdown
   - Lap-by-lap chart
   - Tire health visualization
   - Weather timeline

**How to Use**:
1. Select Silverstone
2. Choose "1-Stop: M->H"
3. Set track_wetness = 0.0
4. Click "Simulate"
5. View results in interactive dashboard

### 3.4 Multi-Car Simulator Tab

**Features**:
1. Add drivers dengan strategies
2. Set initial conditions (track_wetness, random_seed)
3. Run simulation
4. View final standings
5. Replay lap-by-lap progression

**How to Use**:
1. Add 4 drivers (VER, LEC, HAM, NOR)
2. Assign different strategies
3. Click "Run Multi-Car Test"
4. View final standings dan gap progression

### 3.5 Optimizer Tab

**Features**:
1. Configure GA parameters:
   - Population size
   - Number of generations
   - Mutation rate
2. Select circuit
3. Run optimization
4. Download results as CSV/JSON

**How to Use**:
1. Set generations = 50
2. Set population_size = 30
3. Select circuit = Monaco
4. Click "Optimize"
5. Monitor convergence in real-time
6. Download best strategies

### 3.6 Analysis Tab

**Features**:
1. Sensitivity analysis
2. Monte Carlo comparison
3. FastF1 validation results
4. Reports dengan charts

**How to Use**:
1. Click "Run Sensitivity Analysis"
2. View parameter ranking
3. Click "Run Monte Carlo" untuk strategy comparison
4. See uncertainty bands

---

## 4. COMMON USE CASES

### Use Case 1: Compare Two Strategies

```python
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")

for strategy in strategies[:2]:  # Compare first 2
    sim = RaceSimulator(strategy=strategy, circuit_name="Silverstone")
    sim.simulate()
    summary = sim.get_summary()
    print(f"{strategy.name}: {summary['total_race_time_formatted']}")

# Output:
# 1-Stop: S->H: 1:18:23.6
# 1-Stop: M->H: 1:18:11.8  <- faster
```

### Use Case 2: What-If Analysis (Weather Impact)

```python
from core.race_simulator import RaceSimulator
from core.strategy import Strategy

strategy = Strategy.from_template("1-Stop: M->H", "Silverstone")

conditions = [
    ("Dry", 0.0),
    ("Drizzle", 0.2),
    ("Rain", 0.7),
    ("Heavy", 1.0),
]

for condition_name, wetness in conditions:
    sim = RaceSimulator(
        strategy=strategy,
        circuit_name="Silverstone",
        track_wetness=wetness
    )
    sim.simulate()
    summary = sim.get_summary()
    print(f"{condition_name} ({wetness}): {summary['total_race_time']:.1f}s")

# Output:
# Dry (0.0): 4691.8s
# Drizzle (0.2): 4802.3s
# Rain (0.7): 5124.6s
# Heavy (1.0): 5456.2s
```

### Use Case 3: Find Optimal Pit Stop Lap

```python
from optimization.genetic_optimizer import GeneticStrategyOptimizer

optimizer = GeneticStrategyOptimizer("Silverstone", generations=100)
best = optimizer.run()[0]

print("Optimal pit stop strategy:")
print(f"  Strategy: {best.strategy.name}")
print(f"  Race Time: {best.total_race_time:.1f}s")
print(f"  Pit laps: {best.chromosome}")

# Example output:
# Optimal pit stop strategy:
#   Strategy: Custom-2Stop
#   Race Time: 4680.2s
#   Pit laps: [15, 33]  <- pit pada lap 15 dan 33 adalah optimal!
```

### Use Case 4: Risk Assessment

```python
from optimization.monte_carlo import MonteCarloSimulator
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")

mc = MonteCarloSimulator(strategies[:3], "Silverstone", n_iterations=500)
mc.run()

df = mc.get_comparison_dataframe()

print("Strategy Risk Assessment:")
for _, row in df.iterrows():
    print(f"\n{row['strategy']}:")
    print(f"  Expected (mean): {row['mean']:.1f}s")
    print(f"  Worst case (min): {row['min']:.1f}s")
    print(f"  Risk (95th %ile): {row['percentile_95']:.1f}s")
    print(f"  Upside (5th %ile): {row['percentile_5']:.1f}s")
```

### Use Case 5: Circuit Comparison

```python
from core.strategy import Strategy
from core.race_simulator import RaceSimulator

strategy = Strategy.from_template("1-Stop: M->H", "Silverstone")

circuits = ["Silverstone", "Monaco", "Monza", "Bahrain"]

for circuit in circuits:
    strategy = Strategy.from_template("1-Stop: M->H", circuit)
    sim = RaceSimulator(strategy=strategy, circuit_name=circuit)
    sim.simulate()
    summary = sim.get_summary()
    print(f"{circuit}: {summary['avg_lap_time']:.2f}s per lap")

# Output:
# Silverstone: 90.22s per lap
# Monaco: 75.45s per lap
# Monza: 83.12s per lap
# Bahrain: 95.30s per lap
```

---

## 5. TIPS & TRICKS

### Tip 1: Reproducible Results

Gunakan random_seed untuk reproducible results:

```python
# First run - seed 42
sim1 = RaceSimulator(strategy, seed=42)
sim1.simulate()
time1 = sim1.get_summary()['total_race_time']

# Same run - sama seed
sim2 = RaceSimulator(strategy, seed=42)
sim2.simulate()
time2 = sim2.get_summary()['total_race_time']

print(f"Same seeds produce same result: {time1 == time2}")  # True
```

### Tip 2: Batch Processing

Run multiple simulations efficiently:

```python
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies
import pandas as pd

strategies = load_all_strategies("Silverstone")
results = []

for idx, strategy in enumerate(strategies):
    sim = RaceSimulator(strategy=strategy, circuit_name="Silverstone")
    sim.simulate()
    summary = sim.get_summary()
    results.append({
        'strategy': strategy.name,
        'total_time': summary['total_race_time'],
        'avg_lap': summary['avg_lap_time'],
        'fastest': summary['fastest_lap']
    })

df = pd.DataFrame(results)
df = df.sort_values('total_time')
print(df.to_string(index=False))
```

### Tip 3: Custom Tire Parameters

Modify tire characteristics untuk testing:

```python
from core.tire_model import Tire

# Create custom tire dengan modified degradation
custom_soft = Tire(
    compound="Soft",
    track_wetness=0.0,
    compound_data={
        "initial_grip": 1.00,
        "degradation_rate": 0.010,  # Lebih aggressive wear
        "cliff_point": 15,           # Cliff terjadi lebih awal
        # ... other parameters
    }
)
```

### Tip 4: Save Results to CSV

```python
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies

strategies = load_all_strategies("Silverstone")
sim = RaceSimulator(strategy=strategies[0], circuit_name="Silverstone")
sim.simulate()

# Get detailed lap data
lap_data = sim.get_detailed_race_data()

# Save to CSV
lap_data.to_csv("race_results.csv", index=False)

# Or load dan analyze
import pandas as pd
df = pd.read_csv("race_results.csv")
print(df[['lap', 'lap_time', 'compound', 'tire_age']].head(10))
```

### Tip 5: Parallel Optimization

Use parallel processing untuk faster optimization:

```python
from optimization.genetic_optimizer import GeneticStrategyOptimizer

# Built-in parallel support
optimizer = GeneticStrategyOptimizer(
    circuit_name="Silverstone",
    generations=100,
    n_jobs=4  # Use 4 cores
)

best_strategies = optimizer.run()
```

---

## 6. FREQUENTLY ASKED QUESTIONS

### Q1: Bagaimana cara membuat custom strategy?

**A**: Gunakan `Strategy.from_custom_stints()`:

```python
from core.strategy import Strategy

custom_stints = [
    ("Soft", 1, 16),
    ("Hard", 17, 52)
]

strategy = Strategy.from_custom_stints(custom_stints, total_laps=52)
print(strategy.name)  # "Custom"
```

### Q2: Bagaimana cara menurun track wetness effect?

**A**: Set track_wetness parameter dalam RaceSimulator:

```python
sim = RaceSimulator(
    strategy=strategy,
    circuit_name="Silverstone",
    track_wetness=0.5  # 0=dry, 1=full wet
)
```

### Q3: Bagaimana cara analyze pit stop penalty impact?

**A**: Compare dengan simulation_overrides:

```python
# Normal pit lane
sim1 = RaceSimulator(strategy, circuit_name="Silverstone")
sim1.simulate()
normal_time = sim1.get_summary()['total_race_time']

# Faster pit lane
sim2 = RaceSimulator(
    strategy=strategy,
    circuit_name="Silverstone",
    simulation_overrides={"pit_lane_delta": 18.0}  # vs default 20.0
)
sim2.simulate()
fast_pit_time = sim2.get_summary()['total_race_time']

penalty_diff = normal_time - fast_pit_time
print(f"Pit 2 seconds faster saves: {penalty_diff:.1f}s in race")
```

### Q4: Berapa lama GA optimization biasanya berjalan?

**A**: Tergantung population_size dan generations:
- 50 pop × 50 gen: ~5-10 menit
- 50 pop × 100 gen: ~15-20 menit
- 100 pop × 100 gen: ~30-40 menit

Gunakan smaller population untuk faster iteration!

### Q5: Bagaimana cara contribute ke project?

**A**: 
1. Fork the repository
2. Create feature branch
3. Add improvements (new strategies, tire models, etc.)
4. Submit pull request

---

## 7. NEXT STEPS

### For Students:
1. Run basic simulation untuk understand pit stop mechanics
2. Try multi-car untuk analyze traffic dynamics
3. Use optimizer untuk find optimal strategies
4. Analyze sensitivity untuk understand key variables
5. Compare simulator hasil vs real FastF1 data

### For Researchers:
1. Extend tire model dengan more physics
2. Add DRS overtaking mechanics
3. Implement fuel consumption
4. Add driver skill variation
5. Publish findings!

### For Teams:
1. Use simulator untuk pre-race planning
2. Analyze weather scenarios
3. Test contingency strategies
4. Validate terhadap team's own data
5. Integrate real-time dalam race monitoring

---

**Happy simulating! 🏎️💨**

Questions? Issues? Create GitHub issue atau contact development team.


