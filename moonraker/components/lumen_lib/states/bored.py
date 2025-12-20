"""
Bored State Detector - Detects extended idle time
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class BoredDetector(BaseStateDetector):
    """
    Detects when printer has been idle for an extended period.

    Detection logic:
        - Currently in "idle" state
        - Idle duration exceeds bored_timeout
        - Not yet in "sleep" state

    This state is time-based and requires context tracking of how long
    the printer has been idle.

    Common use:
        - Transition from static "idle" lights to animated "bored" effects
        - Show disco/rainbow patterns during long idle periods
        - Attract attention when printer is available
    """

    name = "bored"
    description = "Extended idle period (timeout-based)"
    priority = 80  # Low priority, checked after active states

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if printer has been idle long enough to be 'bored'."""

        if not context:
            return False

        # Get bored timeout from context (default 60 seconds)
        bored_timeout = context.get('bored_timeout', 60.0)

        # Get current state info
        last_state = context.get('last_state', '')
        state_enter_time = context.get('state_enter_time', 0.0)
        current_time = context.get('current_time', 0.0)

        # Must currently be in idle state
        if last_state != 'idle':
            return False

        # Check if we've been idle long enough
        idle_duration = current_time - state_enter_time

        if idle_duration >= bored_timeout:
            return True

        return False
