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

## Fitur baru: weather evolution + multi-car

- `POST /api/simulate/telemetry` mendukung evolusi cuaca lap-by-lap via payload:
  - `weather_evolution` (`true/false`)
  - `weather_mean_target` (`0..1`)
  - `weather_volatility` (`0..0.2`, opsional)
  - `weather_trend` (`-0.08..0.08`, opsional)
  - `weather_reversion` (`0..1`, opsional)
- Response telemetry sekarang juga menyertakan `weather_timeline` dan channel `track_wetness`.
- Endpoint baru `POST /api/simulate/multi-car` untuk simulasi traffic beberapa mobil sekaligus.
  - Input utama: `circuit`, `drivers` (`[{name, strategy_name}]`), `track_wetness`, `random_seed`.
  - Output utama: `standings`, `laps`, `vsc_laps`, `weather_timeline`, dan ringkasan `meta`.
- Frontend tab `Strategy Simulator` memiliki:
  - Toggle `Weather Evolution`
  - Tombol `Run Multi-Car Test` untuk melihat standing akhir multi-car.


