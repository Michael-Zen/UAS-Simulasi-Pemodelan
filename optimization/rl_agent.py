"""Q-learning agent for simple pit-stop policy learning."""

from __future__ import annotations

import os
import random
from collections import defaultdict
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from config import PIT_LANE_DELTA, PIT_STOP_TIME_MEAN, RANDOM_SEED, get_circuit_config
from core.race_simulator import RaceSimulator
from core.strategy import load_all_strategies
from core.tire_model import Tire
from optimization.monte_carlo import MonteCarloSimulator


ACTION_TO_COMPOUND = {
    1: "Soft",
    2: "Medium",
    3: "Hard",
}


class QLearningPitAgent:
    """Learn a coarse pit-stop policy from lap-by-lap rewards."""

    def __init__(
        self,
        circuit_name: str = "Silverstone",
        episodes: int = 500,
        alpha: float = 0.15,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        random_seed: int = RANDOM_SEED,
    ) -> None:
        self.circuit_name = circuit_name
        self.circuit = get_circuit_config(circuit_name)
        self.episodes = episodes
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.random = random.Random(random_seed)
        self.q_table: Dict[Tuple[int, int, int, int], np.ndarray] = defaultdict(lambda: np.zeros(4))
        self.rewards_history: List[float] = []
        self.compound_to_index = {"Soft": 0, "Medium": 1, "Hard": 2}

    def _bucket_state(self, tire_age: int, compound: str, current_lap: int) -> Tuple[int, int, int, int]:
        lap_remaining = self.circuit["total_laps"] - current_lap
        return (
            min(tire_age, 40) // 2,
            self.compound_to_index[compound],
            (current_lap - 1) // 5,
            max(lap_remaining, 0) // 5,
        )

    def _choose_action(self, state: Tuple[int, int, int, int]) -> int:
        if self.random.random() < self.epsilon:
            return self.random.choice([0, 1, 2, 3])
        return int(np.argmax(self.q_table[state]))

    def _simulate_episode(self, greedy: bool = False) -> tuple[float, List[tuple[int, str]]]:
        total_reward = 0.0
        pit_plan: List[tuple[int, str]] = []
        current_compound = "Medium"
        tire_age = 0
        crossed_cliff = False

        for lap in range(1, self.circuit["total_laps"] + 1):
            state = self._bucket_state(tire_age, current_compound, lap)
            action = int(np.argmax(self.q_table[state])) if greedy else self._choose_action(state)

            if action in ACTION_TO_COMPOUND:
                current_compound = ACTION_TO_COMPOUND[action]
                tire_age = 0
                pit_plan.append((lap, current_compound))
                pit_loss = PIT_LANE_DELTA + PIT_STOP_TIME_MEAN
            else:
                pit_loss = 0.0

            tire = Tire(current_compound)
            lap_time = (
                tire.get_lap_time(base_time=self.circuit["base_lap_time"], age=tire_age)
                - (0.03 * (lap - 1))
                + pit_loss
            )
            crossed_cliff = crossed_cliff or tire_age > tire.cliff_point
            reward = -lap_time
            if lap == self.circuit["total_laps"] and not crossed_cliff:
                reward += 100.0
            total_reward += reward

            next_age = tire_age + 1
            next_state = self._bucket_state(next_age, current_compound, min(lap + 1, self.circuit["total_laps"]))

            if not greedy:
                best_next = np.max(self.q_table[next_state])
                self.q_table[state][action] += self.alpha * (
                    reward + self.gamma * best_next - self.q_table[state][action]
                )

            tire_age = next_age

        return total_reward, pit_plan

    def train(self, output_dir: str = "output") -> dict:
        os.makedirs(output_dir, exist_ok=True)
        for _ in range(self.episodes):
            reward, _ = self._simulate_episode(greedy=False)
            self.rewards_history.append(reward)
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        greedy_reward, pit_plan = self._simulate_episode(greedy=True)
        reward_plot = self._plot_rewards(output_dir)
        heatmap_plot = self._plot_q_heatmap(output_dir)
        comparison = self.compare_against_monte_carlo()
        return {
            "reward_history": self.rewards_history,
            "greedy_reward": greedy_reward,
            "pit_plan": pit_plan,
            "reward_plot": reward_plot,
            "heatmap_plot": heatmap_plot,
            "comparison": comparison,
        }

    def _plot_rewards(self, output_dir: str) -> str:
        output_path = os.path.join(output_dir, "rl_rewards.png")
        plt.figure(figsize=(10, 4))
        plt.plot(self.rewards_history, color="#00D2FF", linewidth=1.8)
        plt.title(f"Q-Learning Reward per Episode - {self.circuit_name}")
        plt.xlabel("Episode")
        plt.ylabel("Reward")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        return output_path

    def _plot_q_heatmap(self, output_dir: str) -> str:
        output_path = os.path.join(output_dir, "rl_qtable_heatmap.png")
        age_buckets = sorted({state[0] for state in self.q_table})
        matrix = np.zeros((len(age_buckets), 4))
        for row_index, age_bucket in enumerate(age_buckets):
            matching = [values for state, values in self.q_table.items() if state[0] == age_bucket]
            if matching:
                matrix[row_index] = np.mean(matching, axis=0)

        plt.figure(figsize=(8, 5))
        sns.heatmap(
            matrix,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            xticklabels=["Stay", "Pit Soft", "Pit Medium", "Pit Hard"],
            yticklabels=[f"{bucket * 2}-{bucket * 2 + 1}" for bucket in age_buckets],
        )
        plt.title(f"Q-Table Heatmap by Tire Age - {self.circuit_name}")
        plt.xlabel("Action")
        plt.ylabel("Tire age bucket")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        return output_path

    def compare_against_monte_carlo(self) -> dict:
        mc = MonteCarloSimulator(circuit_name=self.circuit_name, n_iterations=200)
        mc.run(verbose=False)
        best_strategy_name = mc.get_best_strategy()
        best_strategy = next(strategy for strategy in load_all_strategies(self.circuit_name) if strategy.name == best_strategy_name)
        simulator = RaceSimulator(
            strategy=best_strategy,
            circuit_name=self.circuit_name,
            enable_variability=False,
            enable_safety_car=False,
        )
        simulator.simulate()
        greedy_reward, pit_plan = self._simulate_episode(greedy=True)
        return {
            "best_monte_carlo_strategy": best_strategy_name,
            "best_monte_carlo_time": simulator.total_race_time,
            "agent_reward": greedy_reward,
            "agent_pit_plan": pit_plan,
        }

