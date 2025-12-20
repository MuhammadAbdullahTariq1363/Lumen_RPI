"""
Base Effect Class

All effects inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from ..colors import RGB
from ..effects import EffectState  # Reuse existing EffectState


class BaseEffect(ABC):
    """
    Base class for all LED effects.

    Effects calculate LED colors based on time, state, and parameters.
    Each effect must implement the calculate() method.
    """

    # Effect metadata
    name: str = "unknown"
    description: str = "No description"
    requires_led_count: bool = False  # True if effect needs to know LED count
    requires_state_data: bool = False  # True if effect needs printer state

    @abstractmethod
    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """
        Calculate LED colors for this effect.

        Args:
            state: Current effect state (color, speed, parameters, etc.)
            now: Current time in seconds (monotonic)
            led_count: Number of LEDs in the strip (only if requires_led_count=True)
            state_data: Printer state data (only if requires_state_data=True)

        Returns:
            Tuple of (colors, should_update):
                - colors: List of RGB tuples (or None) for each LED
                  Single RGB for same color on all LEDs
                  List of RGB for per-LED colors (disco, progress, thermal)
                  Empty list [] if no update needed
                - should_update: True if driver should apply these colors
                  False if effect hasn't changed yet (throttling)

        Example:
            # Simple single-color effect (pulse, heartbeat)
            return [(r, g, b)], True

            # Per-LED effect (disco, progress)
            return [(r1,g1,b1), (r2,g2,b2), ...], True

            # No update needed yet (throttled)
            return [], False
        """
        raise NotImplementedError(f"Effect '{self.name}' must implement calculate()")

    def validate_state(self, state: EffectState) -> None:
        """
        Validate effect state has required parameters.

        Override this to check for effect-specific parameters.

        Args:
            state: Effect state to validate

        Raises:
            ValueError: If required parameters are missing
        """
        pass

    def __str__(self) -> str:
        return f"{self.name} effect"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
