"""
Base State Detector - Abstract base class for all state detectors
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseStateDetector(ABC):
    """
    Abstract base class for printer state detection.

    Each state detector analyzes printer status data to determine if the
    printer is in a specific state (idle, heating, printing, etc.).

    Subclasses must implement:
        - name: Unique state identifier
        - description: Human-readable state description
        - detect(): Logic to determine if state is active

    Example Implementation:
        class HeatingDetector(BaseStateDetector):
            name = "heating"
            description = "Heaters warming up to target temperature"

            def detect(self, status: Dict[str, Any], context: Optional[Dict] = None) -> bool:
                # Check if any heater is active and below target
                return status.get('heater_bed', {}).get('target', 0) > 0
    """

    # Class attributes (must be overridden by subclasses)
    name: str = "unknown"
    description: str = "No description"
    priority: int = 50  # Lower = higher priority (error=0, idle=100)

    @abstractmethod
    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if this state is currently active.

        Args:
            status: Current printer status dictionary from Klipper
                Common keys:
                    - heater_bed: {temperature, target}
                    - extruder: {temperature, target}
                    - print_stats: {state, filename, print_duration}
                    - toolhead: {position, status, homed_axes}
                    - idle_timeout: {state, printing_time}

            context: Additional context for detection (optional)
                - temp_floor: Ambient temperature threshold
                - bored_timeout: Seconds idle before "bored"
                - sleep_timeout: Seconds bored before "sleep"
                - last_state: Previous state name
                - state_enter_time: When current state started

        Returns:
            True if this state is active, False otherwise
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement detect()")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
