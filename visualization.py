"""
================================================================================
VISUALISASI HASIL SIMULASI F1
================================================================================
Module ini menghasilkan semua grafik dan visualisasi untuk analisis simulasi.

GRAFIK YANG DIHASILKAN:
━━━━━━━━━━━━━━━━━━━━━━
1. Kurva Degradasi Ban   — grip vs lap number per compound
2. Lap Time per Compound — lap time vs lap number per compound
3. Lap Time Progression  — lap time sepanjang race per strategi (deterministic)
4. Bar Chart Total Time  — perbandingan total race time antar strategi
5. Monte Carlo Distribusi— histogram/violin plot distribusi race time
6. Heatmap Pit Window    — optimal lap untuk pit stop
7. Win Probability       — pie chart probabilitas kemenangan

STYLE:
━━━━━━
Menggunakan style gelap (dark theme) agar terlihat profesional dan modern.
Warna ban mengikuti konvensi F1: Merah=Soft, Kuning=Medium, Putih=Hard.
================================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

from tire_model import Tire
from strategy import Strategy, load_all_strategies
from race_simulator import RaceSimulator
from monte_carlo import MonteCarloSimulator
from config import (
    TIRE_COMPOUNDS, TOTAL_LAPS, BASE_LAP_TIME,
    CIRCUIT_NAME
)


# ==========================================
# STYLE GLOBAL
# ==========================================
def setup_style():
    """Mengatur style global untuk semua plot."""
    plt.style.use('dark_background')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Segoe UI', 'Arial', 'DejaVu Sans'],
        'font.size': 11,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'axes.titleweight': 'bold',
        'figure.facecolor': '#1a1a2e',
        'axes.facecolor': '#16213e',
        'axes.edgecolor': '#e94560',
        'axes.grid': True,
        'grid.color': '#2a2a4a',
        'grid.alpha': 0.5,
        'grid.linestyle': '--',
        'text.color': '#e0e0e0',
        'xtick.color': '#e0e0e0',
        'ytick.color': '#e0e0e0',
        'legend.facecolor': '#1a1a2e',
        'legend.edgecolor': '#e94560',
        'figure.dpi': 120,
    })


# Warna untuk strategi (gradient dari biru ke merah)
STRATEGY_COLORS = [
    '#00d2ff', '#3a7bd5', '#6dd5ed', '#2193b0',
    '#e94560', '#fc5c7d', '#ff7eb3', '#f093fb',
    '#4facfe',
]


def plot_tire_degradation(save_path: str = None):
    """
    GRAFIK 1: Kurva Degradasi Ban
    
    Menampilkan bagaimana grip ban menurun seiring bertambahnya umur
    untuk setiap compound (Soft, Medium, Hard).
    
    Insight yang bisa didapat:
    - Soft: grip awal tinggi tapi cepat habis
    - Medium: keseimbangan antara performa dan daya tahan
    - Hard: grip rendah tapi tahan lama
    - Cliff point terlihat jelas sebagai penurunan tajam
    """
    setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f'Model Degradasi Ban F1 - {CIRCUIT_NAME}', 
                 fontsize=16, fontweight='bold', color='white', y=1.02)
    
    max_laps = 50
    
    for compound_name, params in TIRE_COMPOUNDS.items():
        tire = Tire(compound_name)
        data = tire.get_degradation_curve(max_laps)
        
        color = params["color"]
        if color == "#FFFFFF":
            color = "#cccccc"  # Slightly darker white for visibility on dark bg
        
        # Plot grip
        axes[0].plot(data["laps"], data["grip"], 
                     color=color, linewidth=2.5, label=params["label"],
                     marker='o', markevery=5, markersize=4)
        
        # Mark cliff point
        cp = params["cliff_point"]
        cp_grip = tire.get_grip(age=cp)
        axes[0].axvline(x=cp, color=color, linestyle=':', alpha=0.4, linewidth=1)
        axes[0].plot(cp, cp_grip, 's', color=color, markersize=10, 
                     markeredgecolor='white', markeredgewidth=1.5, zorder=5)
        axes[0].annotate(f'Cliff L{cp}', xy=(cp, cp_grip), 
                         xytext=(cp+2, cp_grip+0.02),
                         fontsize=8, color=color, fontweight='bold',
                         arrowprops=dict(arrowstyle='->', color=color, lw=1))
        
        # Plot lap time
        axes[1].plot(data["laps"], data["lap_times"],
                     color=color, linewidth=2.5, label=params["label"],
                     marker='o', markevery=5, markersize=4)
    
    # Style axis grip
    axes[0].set_xlabel('Umur Ban (Lap)')
    axes[0].set_ylabel('Grip Level')
    axes[0].set_title('Grip vs Umur Ban')
    axes[0].legend(loc='lower left', framealpha=0.8)
    axes[0].set_ylim(0.45, 1.05)
    axes[0].set_xlim(0, max_laps)
    
    # Style axis lap time
    axes[1].set_xlabel('Umur Ban (Lap)')
    axes[1].set_ylabel('Lap Time (detik)')
    axes[1].set_title('Lap Time vs Umur Ban')
    axes[1].legend(loc='upper left', framealpha=0.8)
    axes[1].set_xlim(0, max_laps)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_lap_time_progression(strategies: list = None, save_path: str = None):
    """
    GRAFIK 2: Lap Time Progression Sepanjang Race (Deterministic)
    
    Menampilkan lap time setiap lap untuk beberapa strategi,
    tanpa variabilitas (deterministic) agar pola terlihat jelas.
    
    Insight:
    - Terlihat kapan mobil masuk pit (spike waktu)
    - Terlihat efek ban baru (lap time turun setelah pit stop)
    - Terlihat degradasi ban (lap time naik bertahap)
    """
    setup_style()
    
    if strategies is None:
        strategies = load_all_strategies()
    
    fig, ax = plt.subplots(figsize=(16, 8))
    fig.suptitle(f'Lap Time Progression - {CIRCUIT_NAME} ({TOTAL_LAPS} Lap)',
                 fontsize=16, fontweight='bold', color='white')
    
    for i, strategy in enumerate(strategies):
        sim = RaceSimulator(
            strategy=strategy,
            enable_variability=False,
            enable_safety_car=False
        )
        df = sim.simulate()
        
        color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
        
        # Plot lap times (tanpa pit stop spike untuk clarity)
        normal_laps = df[~df["is_pit_lap"]]
        pit_laps = df[df["is_pit_lap"]]
        
        ax.plot(normal_laps["lap"], normal_laps["final_lap_time"],
                color=color, linewidth=1.8, label=strategy.name, alpha=0.85)
        
        # Mark pit stops
        if len(pit_laps) > 0:
            ax.scatter(pit_laps["lap"], pit_laps["final_lap_time"] - pit_laps["pit_stop_loss"],
                       color=color, marker='v', s=80, zorder=5,
                       edgecolors='white', linewidths=1)
    
    ax.set_xlabel('Lap')
    ax.set_ylabel('Lap Time (detik)')
    ax.legend(loc='upper right', fontsize=9, ncol=2, framealpha=0.8)
    ax.set_xlim(1, TOTAL_LAPS)
    
    # Tambahkan anotasi
    ax.annotate('▼ = Pit Stop', xy=(0.01, 0.02), xycoords='axes fraction',
                fontsize=9, color='#aaaaaa', style='italic')
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_total_race_time_comparison(strategies: list = None, save_path: str = None):
    """
    GRAFIK 3: Bar Chart Perbandingan Total Race Time (Deterministic)
    
    Membandingkan total race time setiap strategi dalam bar chart horizontal.
    Strategi diurutkan dari tercepat ke terlambat.
    """
    setup_style()
    
    if strategies is None:
        strategies = load_all_strategies()
    
    # Simulasikan semua strategi (deterministic)
    results = []
    for strategy in strategies:
        sim = RaceSimulator(
            strategy=strategy,
            enable_variability=False,
            enable_safety_car=False
        )
        sim.simulate()
        summary = sim.get_summary()
        results.append(summary)
    
    # Sort by total time
    results.sort(key=lambda x: x["total_race_time"])
    
    names = [r["strategy_name"] for r in results]
    times = [r["total_race_time"] for r in results]
    min_time = min(times)
    
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(f'Perbandingan Total Race Time - {CIRCUIT_NAME}',
                 fontsize=16, fontweight='bold', color='white')
    
    # Create horizontal bar chart
    bars = ax.barh(range(len(names)), times, height=0.6, 
                   color=[STRATEGY_COLORS[i % len(STRATEGY_COLORS)] for i in range(len(names))],
                   edgecolor='white', linewidth=0.5, alpha=0.85)
    
    # Add time labels
    for i, (bar, time_val) in enumerate(zip(bars, times)):
        diff = time_val - min_time
        formatted = RaceSimulator._format_time(time_val)
        diff_str = f" (+{diff:.3f}s)" if diff > 0 else " << FASTEST"
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f'{formatted}{diff_str}', va='center', ha='left',
                fontsize=9, color='white', fontweight='bold' if diff == 0 else 'normal')
    
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel('Total Race Time (detik)')
    ax.invert_yaxis()
    
    # Set x limit to show labels
    ax.set_xlim(min(times) - 10, max(times) + 60)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_monte_carlo_distributions(mc_sim: MonteCarloSimulator, save_path: str = None):
    """
    GRAFIK 4: Distribusi Monte Carlo (Violin + Box Plot)
    
    Menampilkan distribusi total race time dari simulasi Monte Carlo.
    Menggunakan violin plot yang menunjukkan bentuk distribusi lengkap,
    dikombinasikan dengan box plot untuk statistik ringkas.
    
    Insight:
    - Distribusi sempit = strategi konsisten (low risk)
    - Distribusi lebar = strategi berisiko (high variance)
    - Outlier menunjukkan kejadian safety car yang berpengaruh
    """
    setup_style()
    
    if not mc_sim.is_completed:
        raise RuntimeError("Monte Carlo belum dijalankan!")
    
    # Persiapkan data
    data_list = []
    for name, times in mc_sim.results.items():
        for t in times:
            data_list.append({"Strategi": name, "Total Race Time (s)": t})
    
    df = pd.DataFrame(data_list)
    
    # Sort strategi berdasarkan mean time
    order = sorted(mc_sim.results.keys(), 
                   key=lambda k: mc_sim.statistics[k]["mean"])
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), 
                             gridspec_kw={'height_ratios': [2, 1]})
    fig.suptitle(f'Distribusi Monte Carlo - {mc_sim.n_iterations} Iterasi per Strategi',
                 fontsize=16, fontweight='bold', color='white', y=1.01)
    
    # === Violin Plot ===
    palette = {name: STRATEGY_COLORS[i % len(STRATEGY_COLORS)] 
               for i, name in enumerate(order)}
    
    sns.violinplot(data=df, x="Strategi", y="Total Race Time (s)",
                   order=order, palette=palette, ax=axes[0],
                   inner="box", linewidth=1, alpha=0.7, cut=0)
    
    axes[0].set_title('Distribusi Total Race Time (Violin + Box Plot)')
    axes[0].set_xlabel('')
    axes[0].set_ylabel('Total Race Time (detik)')
    axes[0].tick_params(axis='x', rotation=30)
    
    # Tambahkan mean labels
    for i, name in enumerate(order):
        mean_val = mc_sim.statistics[name]["mean"]
        axes[0].annotate(f'μ={mean_val:.1f}s', 
                         xy=(i, mean_val), xytext=(i, mean_val - 15),
                         fontsize=8, color='white', ha='center', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#e94560', alpha=0.7))
    
    # === Box Plot detail ===
    sns.boxplot(data=df, x="Strategi", y="Total Race Time (s)",
                order=order, palette=palette, ax=axes[1],
                linewidth=1, fliersize=2, width=0.5)
    
    axes[1].set_title('Box Plot Detail (Median, Q1-Q3, Outliers)')
    axes[1].set_xlabel('Strategi')
    axes[1].set_ylabel('Total Race Time (detik)')
    axes[1].tick_params(axis='x', rotation=30)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_win_probability(mc_sim: MonteCarloSimulator, save_path: str = None):
    """
    GRAFIK 5: Win Probability Pie Chart
    
    Menampilkan probabilitas setiap strategi menjadi yang tercepat
    berdasarkan simulasi Monte Carlo.
    """
    setup_style()
    
    if not mc_sim.is_completed:
        raise RuntimeError("Monte Carlo belum dijalankan!")
    
    win_probs = mc_sim.calculate_win_probabilities()
    
    # Filter strategi dengan win prob > 0
    filtered = {k: v for k, v in win_probs.items() if v > 0}
    
    if not filtered:
        print("  ⚠️ Tidak ada strategi dengan win probability > 0")
        return None
    
    names = list(filtered.keys())
    probs = list(filtered.values())
    colors = [STRATEGY_COLORS[list(win_probs.keys()).index(n) % len(STRATEGY_COLORS)] 
              for n in names]
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7),
                             gridspec_kw={'width_ratios': [1, 1.2]})
    fig.suptitle(f'Probabilitas Kemenangan Strategi - Monte Carlo ({mc_sim.n_iterations} iterasi)',
                 fontsize=16, fontweight='bold', color='white')
    
    # Pie chart
    explode = [0.05 if p == max(probs) else 0 for p in probs]
    wedges, texts, autotexts = axes[0].pie(
        probs, labels=None, autopct='%1.1f%%',
        colors=colors, explode=explode,
        pctdistance=0.75, startangle=90,
        wedgeprops=dict(width=0.5, edgecolor='white', linewidth=1.5)
    )
    
    for autotext in autotexts:
        autotext.set_fontsize(10)
        autotext.set_fontweight('bold')
        autotext.set_color('white')
    
    axes[0].set_title('Win Probability', pad=15)
    
    # Legend sebagai tabel
    axes[0].legend(wedges, [f"{n} ({p*100:.1f}%)" for n, p in zip(names, probs)],
                   loc='center left', bbox_to_anchor=(0.85, 0.5),
                   fontsize=9, framealpha=0.8)
    
    # Bar chart di sebelah kanan
    sorted_idx = np.argsort(probs)[::-1]
    sorted_names = [names[i] for i in sorted_idx]
    sorted_probs = [probs[i] * 100 for i in sorted_idx]
    sorted_colors = [colors[i] for i in sorted_idx]
    
    bars = axes[1].barh(range(len(sorted_names)), sorted_probs,
                        color=sorted_colors, edgecolor='white', linewidth=0.5,
                        height=0.6, alpha=0.85)
    
    for bar, prob in zip(bars, sorted_probs):
        axes[1].text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                     f'{prob:.1f}%', va='center', fontsize=10, 
                     color='white', fontweight='bold')
    
    axes[1].set_yticks(range(len(sorted_names)))
    axes[1].set_yticklabels(sorted_names, fontsize=10)
    axes[1].set_xlabel('Win Probability (%)')
    axes[1].set_title('Ranking Strategi', pad=15)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, max(sorted_probs) + 10)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_pit_window_heatmap(strategies: list = None, save_path: str = None):
    """
    GRAFIK 6: Heatmap Optimal Pit Window
    
    Menampilkan lap time pada setiap lap untuk setiap strategi,
    memvisualisasikan di mana waktu yang digunakan paling optimal.
    
    Warna gelap = lap time cepat (bagus)
    Warna terang = lap time lambat (buruk)
    
    Insight:
    - Melihat pola kapan setiap strategi paling cepat/lambat
    - Mengidentifikasi window optimal untuk pit stop
    """
    setup_style()
    
    if strategies is None:
        strategies = load_all_strategies()
    
    # Simulasikan semua strategi (deterministic)
    lap_times_matrix = []
    strat_names = []
    
    for strategy in strategies:
        sim = RaceSimulator(
            strategy=strategy,
            enable_variability=False,
            enable_safety_car=False
        )
        df = sim.simulate()
        
        # Ambil lap time tanpa pit stop loss
        clean_times = df["degraded_lap_time"] - df["fuel_effect"]
        lap_times_matrix.append(clean_times.values)
        strat_names.append(strategy.name)
    
    # Buat matrix
    matrix = np.array(lap_times_matrix)
    
    fig, ax = plt.subplots(figsize=(18, 7))
    fig.suptitle(f'Heatmap Lap Time per Strategi - {CIRCUIT_NAME}',
                 fontsize=16, fontweight='bold', color='white')
    
    # Heatmap
    im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn_r',
                   interpolation='nearest')
    
    # Labels
    ax.set_yticks(range(len(strat_names)))
    ax.set_yticklabels(strat_names, fontsize=10)
    ax.set_xlabel('Lap Number')
    ax.set_ylabel('Strategi')
    
    # X axis: setiap 5 lap
    ax.set_xticks(range(0, TOTAL_LAPS, 5))
    ax.set_xticklabels(range(1, TOTAL_LAPS + 1, 5))
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('Lap Time (detik)', rotation=270, labelpad=15)
    
    # Mark pit stops
    for i, strategy in enumerate(strategies):
        pit_laps = strategy.get_pit_stop_laps()
        for pl in pit_laps:
            ax.plot(pl - 1, i, 'w*', markersize=12, markeredgecolor='black',
                    markeredgewidth=0.5)
    
    # Legend
    ax.annotate('★ = Pit Stop', xy=(0.01, -0.12), xycoords='axes fraction',
                fontsize=10, color='white', style='italic')
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def plot_strategy_stint_timeline(strategies: list = None, save_path: str = None):
    """
    GRAFIK 7: Timeline Stint per Strategi
    
    Visualisasi timeline yang menunjukkan compound apa yang digunakan
    pada setiap bagian race untuk setiap strategi.
    Warna mengikuti konvensi F1 (Merah=Soft, Kuning=Medium, Putih=Hard).
    """
    setup_style()
    
    if strategies is None:
        strategies = load_all_strategies()
    
    compound_colors = {
        "Soft": "#FF3333",
        "Medium": "#FFD700", 
        "Hard": "#cccccc"
    }
    
    fig, ax = plt.subplots(figsize=(16, 6))
    fig.suptitle(f'Timeline Stint Strategi - {CIRCUIT_NAME} ({TOTAL_LAPS} Lap)',
                 fontsize=16, fontweight='bold', color='white')
    
    bar_height = 0.6
    
    for i, strategy in enumerate(strategies):
        for compound, start, end in strategy.stints:
            width = end - start + 1
            color = compound_colors[compound]
            ax.barh(i, width, left=start-1, height=bar_height,
                    color=color, edgecolor='#1a1a2e', linewidth=1.5,
                    alpha=0.85)
            
            # Label di tengah bar
            mid = start - 1 + width / 2
            text_color = 'black' if compound in ['Medium', 'Hard'] else 'white'
            if width >= 5:  # Hanya tampilkan label jika cukup lebar
                ax.text(mid, i, f'{compound[0]}\n({width}L)',
                        ha='center', va='center', fontsize=8,
                        fontweight='bold', color=text_color)
    
    ax.set_yticks(range(len(strategies)))
    ax.set_yticklabels([s.name for s in strategies], fontsize=10)
    ax.set_xlabel('Lap Number')
    ax.set_xlim(0, TOTAL_LAPS)
    ax.invert_yaxis()
    
    # Legend
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#FF3333',
               markersize=12, label='Soft', linestyle='None'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#FFD700',
               markersize=12, label='Medium', linestyle='None'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='#cccccc',
               markersize=12, label='Hard', linestyle='None'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', framealpha=0.8)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"  ✅ Saved: {save_path}")
    
    return fig


def generate_all_visualizations(mc_sim: MonteCarloSimulator = None,
                                 output_dir: str = "output"):
    """
    Menghasilkan semua visualisasi dan menyimpannya ke folder output.
    
    Args:
        mc_sim: MonteCarloSimulator yang sudah dijalankan (opsional)
        output_dir: Folder untuk menyimpan gambar
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    strategies = load_all_strategies()
    
    print("\n" + "=" * 60)
    print("📊 MENGHASILKAN VISUALISASI")
    print("=" * 60)
    
    # 1. Degradasi Ban
    print("\n  1/7 Kurva Degradasi Ban...")
    plot_tire_degradation(save_path=f"{output_dir}/01_degradasi_ban.png")
    
    # 2. Lap Time Progression
    print("  2/7 Lap Time Progression...")
    plot_lap_time_progression(strategies, save_path=f"{output_dir}/02_lap_time_progression.png")
    
    # 3. Total Race Time Comparison
    print("  3/7 Perbandingan Total Race Time...")
    plot_total_race_time_comparison(strategies, save_path=f"{output_dir}/03_total_race_time.png")
    
    # 4. Stint Timeline
    print("  4/7 Timeline Stint...")
    plot_strategy_stint_timeline(strategies, save_path=f"{output_dir}/04_stint_timeline.png")
    
    # 5. Heatmap
    print("  5/7 Heatmap Pit Window...")
    plot_pit_window_heatmap(strategies, save_path=f"{output_dir}/05_heatmap_pit_window.png")
    
    # Monte Carlo plots (jika ada)
    if mc_sim is not None and mc_sim.is_completed:
        # 6. Monte Carlo Distribution
        print("  6/7 Distribusi Monte Carlo...")
        plot_monte_carlo_distributions(mc_sim, save_path=f"{output_dir}/06_monte_carlo_distribusi.png")
        
        # 7. Win Probability
        print("  7/7 Win Probability...")
        plot_win_probability(mc_sim, save_path=f"{output_dir}/07_win_probability.png")
    else:
        print("  6/7 ⏭️ Monte Carlo belum tersedia, skip...")
        print("  7/7 ⏭️ Win Probability belum tersedia, skip...")
    
    print(f"\n  ✅ Semua visualisasi tersimpan di folder '{output_dir}/'")
    print("=" * 60)


# ==========================================
# DEMONSTRASI
# ==========================================
if __name__ == "__main__":
    # Generate grafik degradasi saja sebagai demo
    plot_tire_degradation()
    plt.show()
