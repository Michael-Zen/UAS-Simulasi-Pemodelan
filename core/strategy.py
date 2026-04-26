"""Pit strategy definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from config import CIRCUIT_NAME, get_circuit_config, get_strategies


Stint = Tuple[str, int, int]


@dataclass
class Strategy:
    """Represent a race strategy as a sequence of tyre stints."""

    name: str
    stints: List[Stint]
    description: str = ""
    total_laps: int | None = None

    def __post_init__(self) -> None:
        self.total_laps = self.total_laps or self.stints[-1][2]
        self.num_stops = max(len(self.stints) - 1, 0)
        self._validate()

    def _validate(self) -> None:
        if not self.stints:
            raise ValueError(f"Strategy '{self.name}' has no stints.")
        if self.stints[0][1] != 1:
            raise ValueError(f"Strategy '{self.name}' must start on lap 1.")
        if self.stints[-1][2] != self.total_laps:
            raise ValueError(
                f"Strategy '{self.name}' must end on lap {self.total_laps}, "
                f"not lap {self.stints[-1][2]}."
            )
        for previous, current in zip(self.stints, self.stints[1:]):
            if current[1] != previous[2] + 1:
                raise ValueError(
                    f"Strategy '{self.name}' has a gap or overlap between "
                    f"laps {previous[2]} and {current[1]}."
                )
        if len({compound for compound, _, _ in self.stints}) < 2:
            raise ValueError(
                f"Strategy '{self.name}' must use at least two compounds to stay FIA-compatible."
            )

    @classmethod
    def from_pit_plan(
        cls,
        name: str,
        start_compound: str,
        pit_plan: Sequence[Tuple[int, str]],
        total_laps: int,
        description: str = "",
    ) -> "Strategy":
        """Create a strategy from a starting compound and pit stop plan."""
        sorted_plan = sorted((int(lap), compound) for lap, compound in pit_plan)
        stints: List[Stint] = []
        current_compound = start_compound
        stint_start = 1

        for pit_lap, next_compound in sorted_plan:
            if pit_lap < stint_start or pit_lap >= total_laps:
                raise ValueError(f"Invalid pit lap {pit_lap} for strategy '{name}'.")
            stints.append((current_compound, stint_start, pit_lap))
            current_compound = next_compound
            stint_start = pit_lap + 1

        stints.append((current_compound, stint_start, total_laps))
        return cls(name=name, stints=stints, description=description, total_laps=total_laps)

    def get_compound_at_lap(self, lap: int) -> str:
        for compound, start_lap, end_lap in self.stints:
            if start_lap <= lap <= end_lap:
                return compound
        raise ValueError(f"Lap {lap} is not covered by strategy '{self.name}'.")

    def get_tire_age_at_lap(self, lap: int) -> int:
        for _, start_lap, end_lap in self.stints:
            if start_lap <= lap <= end_lap:
                return lap - start_lap
        raise ValueError(f"Lap {lap} is not covered by strategy '{self.name}'.")

    def get_pit_stop_laps(self) -> List[int]:
        return [stint[2] for stint in self.stints[:-1]]

    def get_stint_info(self) -> List[Dict[str, int | str]]:
        return [
            {
                "compound": compound,
                "start_lap": start_lap,
                "end_lap": end_lap,
                "length": end_lap - start_lap + 1,
            }
            for compound, start_lap, end_lap in self.stints
        ]

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "total_laps": self.total_laps,
            "num_stops": self.num_stops,
            "stints": self.get_stint_info(),
            "pit_stop_laps": self.get_pit_stop_laps(),
        }

    @classmethod
    def from_custom_stints(
        cls,
        custom_stints: Sequence[Dict[str, object]],
        total_laps: int,
        name: str = "Custom",
    ) -> "Strategy":
        """Build a Strategy from a list of ``{"compound": ..., "laps": ...}`` dicts."""
        stints: List[Stint] = []
        lap_cursor = 1
        for entry in custom_stints:
            compound = str(entry["compound"])
            length = int(entry["laps"])
            end_lap = min(lap_cursor + length - 1, total_laps)
            stints.append((compound, lap_cursor, end_lap))
            lap_cursor = end_lap + 1
        # Extend or trim the last stint to match total_laps exactly.
        if stints:
            last_compound, last_start, _ = stints[-1]
            stints[-1] = (last_compound, last_start, total_laps)
        return cls(name=name, stints=stints, total_laps=total_laps)

    def __repr__(self) -> str:
        compounds = " -> ".join(stint[0][0] for stint in self.stints)
        return f"Strategy('{self.name}', stops={self.num_stops}, [{compounds}])"


def load_all_strategies(circuit_name: str | None = None) -> List[Strategy]:
    """Load all configured strategy templates for a circuit."""
    selected_circuit = circuit_name or CIRCUIT_NAME
    total_laps = int(get_circuit_config(selected_circuit)["total_laps"])
    strategies: List[Strategy] = []
    for name, data in get_strategies(selected_circuit).items():
        strategies.append(
            Strategy(
                name=name,
                stints=list(data["stints"]),
                description=str(data["description"]),
                total_laps=total_laps,
            )
        )
    return strategies

