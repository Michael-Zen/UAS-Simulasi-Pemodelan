# F1 Pit Stop Simulation

Proyek ini merupakan simulator strategi pit stop Formula 1 berbasis Hybrid Model (kombinasi continuous tire degradation dan discrete pit stop events) yang sesuai dengan paper S1 tentang strategi pit stop F1. Proyek ini meliputi modul inti, optimasi, analisis, backend Flask, dan frontend statis.

## Struktur proyek

```text
.
├── analysis/
│   ├── scenario_testing.py  (What-if scenario framework)
│   ├── sensitivity_analysis.py
│   └── validation_fastf1.py
├── backend/
│   └── app.py
├── core/
│   ├── multi_car_race.py
│   ├── race_simulator.py
│   ├── strategy.py
│   └── tire_model.py
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── optimization/
│   ├── genetic_optimizer.py
│   ├── monte_carlo.py
│   └── rl_agent.py
├── config.py
├── main.py
└── requirements.txt
```

## Fitur Utama: Paper-Aligned Scenario Testing

### Model Simulasi (Hybrid Model)
- **Komponen Kontinu**: Degradasi ban per lap menggunakan fungsi eksponensial/linear
- **Komponen Diskrit**: Pit stop sebagai event yang mengubah state sistem secara instan
- **Implementasi**: Kombinasi keduanya memberikan representasi realistis dinamika balapan F1

### What-If Scenarios (sesuai paper)

Endpoint untuk menjalankan scenario-scenario dari paper:

#### 1. **Baseline Scenario** (`POST /api/scenarios/baseline`)
Strategi standar 1-stop: Medium → Hard pada lap ~30/52 (50% dari race distance).
**Dari paper**: "Strategi satu pit stop dengan urutan kompon Medium → Hard."

```bash
curl -X POST http://localhost:5000/api/scenarios/baseline \
  -H "Content-Type: application/json" \
  -d '{"circuit": "Silverstone"}'
```

**Response Fields**:
- `total_race_time`: Total race time dalam detik
- `avg_lap_time`: Rata-rata lap time
- `stint_analysis`: Analisa per stint (avg lap, degradation)
- `pit_lap`: Lap pit stop dilakukan

#### 2. **1-Stop vs 2-Stop Comparison** (`POST /api/scenarios/1stop-vs-2stop`)
Membandingkan strategi 1-stop (Medium→Hard) vs 2-stop (Soft→Medium→Hard).
**Dari paper**: "Membandingkan total waktu antara strategi satu pit stop versus dua pit stop. Tujuannya menentukan apakah kecepatan ban di awal sepadan dengan tambahan satu kali penalti pit lane."

```bash
curl -X POST http://localhost:5000/api/scenarios/1stop-vs-2stop \
  -H "Content-Type: application/json" \
  -d '{"circuit": "Silverstone"}'
```

**Response Fields**:
- `strategies`: Array of both strategies dengan metrics
- `best_strategy`: Nama strategi yang lebih cepat
- `time_delta`: Selisih waktu antar strategi
- `analysis`: Penjelasan mengapa strategy tertentu lebih baik

#### 3. **Weather Transition** (`POST /api/scenarios/weather-transition`)
Test kritis pit timing saat perubahan cuaca.
**Dari paper**: "Kondisi lintasan berubah selama balapan berlangsung. Tingat pit stop saat perubahan cuaca merupakan faktor yang sangat menentukan total race time."

```bash
curl -X POST http://localhost:5000/api/scenarios/weather-transition \
  -H "Content-Type: application/json" \
  -d '{
    "circuit": "Silverstone",
    "transition_type": "dry_to_wet",
    "transition_lap": 26
  }'
```

**Parameters**:
- `transition_type`: `"dry_to_wet"` atau `"wet_to_dry"`
- `transition_lap`: Lap pada saat weather berubah (default: mid-race)

**Response Fields**:
- `scenario_name`: Jenis scenario
- `strategy`: Strategy yang digunakan
- `simulation_phases`: Results sebelum dan sesudah transition
- `critical_timing`: Insight tentang optimal pit lap
- `analysis`: Penjelasan impact dari weather change

#### 4. **Best Combination Finder** (`POST /api/scenarios/best-combination`)
Search optimal pit stop combinations untuk minimum race time.
**Dari paper**: "Mencoba mengkombinasikan semua strategi di sirkuit... mencarikan kombinasi terbaik."

```bash
curl -X POST http://localhost:5000/api/scenarios/best-combination \
  -H "Content-Type: application/json" \
  -d '{"circuit": "Silverstone", "max_combinations": 30}'
```

**Response Fields**:
- `best_strategy`: Strategy dengan minimum race time
- `top_5_strategies`: 5 strategi terbaik
- `all_tested`: Semua strategi yang ditest

#### 5. **Comprehensive Analysis** (`POST /api/scenarios/all`)
Run ALL scenarios sekaligus untuk complete paper analysis.

```bash
curl -X POST http://localhost:5000/api/scenarios/all \
  -H "Content-Type: application/json" \
  -d '{"circuit": "Silverstone"}'
```

**Response**: Kombinasi dari semua 4 scenario di atas dalam satu response.

## API Endpoints Lainnya

### Existing Endpoints (tetap berfungsi):
- `GET /api/circuits` - List semua circuit
- `GET /api/compounds` - Info tire compounds
- `GET /api/strategies` - List strategy templates
- `GET /api/degradation` - Degradation curves per compound
- `POST /api/simulate/deterministic` - Run deterministic simulation
- `POST /api/simulate/telemetry` - Get telemetry data per frame
- `POST /api/compare` - Compare multiple strategies
- `POST /api/simulate/monte-carlo` - Stochastic analysis

## Catatan teknis

### Circuit Configuration (config.py)
Setiap circuit memiliki:
- `pit_lane_delta`: Waktu hilang di pit lane (detik)
- `base_lap_time`: Reference lap time (detik)
- `degradation_multiplier`: Faktor pengali degradasi
- `total_laps`: Jumlah lap di circuit itu
- `overtake_difficulty`: Difficulty factor untuk overtaking
- `rain_probability`: Probability cuaca hujan

### Tire Compounds Model
5 jenis ban dengan parameter individual:
- **Soft (S)**: Grip tinggi, degradasi tinggi
- **Medium (M)**: Balanced
- **Hard (H)**: Grip rendah, durability tinggi
- **Intermediate (I)**: Untuk track basah sebagian
- **Wet (W)**: Track full wet

Setiap compound memiliki:
- `initial_grip`: Grip awal
- `degradation_rate`: Laju degradasi per lap
- `cliff_point`: Lap pada mana cliff terjadi
- `optimal_temp`: Optimal working temperature

### Track Map Telemetry
- Endpoint telemetry support circuit-spesific track geometry
- Circuit dengan track map: Monaco, Spa, Silverstone, Monza, Bahrain, Suzuka
- Novel fallback untuk circuit lain (oval approximation)

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask backend
python -m backend.app

# Frontend tersedia di http://localhost:5000
```

## File References
- Paper scenarios implemented in: `analysis/scenario_testing.py`
- Backend API: `backend/app.py`
- Core simulation: `core/race_simulator.py`
- Tire model: `core/tire_model.py`
- Strategy: `core/strategy.py`



