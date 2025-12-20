"""
Sleep State Detector - Detects very extended idle time
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class SleepDetector(BaseStateDetector):
    """
    Detects when printer has been idle/bored for a very extended period.

    Detection logic:
        - Currently in "bored" state
        - Bored duration exceeds sleep_timeout
        - Deep idle with no activity

    This state is time-based and requires context tracking of how long
    the printer has been bored.

    Common use:
        - Turn off LEDs to save power
        - Dim lights for nighttime operation
        - Deep idle state until next print
    """

    name = "sleep"
    description = "Very extended idle period (deep sleep)"
    priority = 90  # Very low priority, checked after bored

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if printer has been bored long enough to 'sleep'."""

        if not context:
            return False

        # Get sleep timeout from context (default 300 seconds = 5 minutes)
        sleep_timeout = context.get('sleep_timeout', 300.0)

        # Get current state info
        last_state = context.get('last_state', '')
        state_enter_time = context.get('state_enter_time', 0.0)
        current_time = context.get('current_time', 0.0)

        # Must currently be in bored state
        if last_state != 'bored':
            return False

        # Check if we've been bored long enough
        bored_duration = current_time - state_enter_time

        if bored_duration >= sleep_timeout:
            return True

        return False
