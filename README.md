# F1 Pit Stop Simulation

Proyek ini merapikan simulator strategi pit stop Formula 1 menjadi struktur yang lebih kohesif, dengan modul inti, optimasi, analisis, backend Flask, dan frontend statis.

## Struktur proyek

```text
.
├── analysis/
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

## Catatan track map telemetry

- Endpoint `POST /api/simulate/telemetry` sekarang mendukung track map non-oval yang lebih realistis.
- Sirkuit dengan layout khusus saat ini: `Monaco`, `Spa`, `Silverstone`, `Monza`, `Bahrain`, dan `Suzuka`.
- Sirkuit lain tetap memakai fallback oval agar minimap selalu tersedia.
- Geometri `Monaco` memakai turunan `monaco-6.svg` dari repositori `julesr0y/f1-circuits-svg` (lisensi CC BY 4.0).
- Geometri `Spa`, `Silverstone`, `Monza`, `Bahrain`, dan `Suzuka` juga memakai sumber yang sama melalui data `_external/generated_track_points.json`.


