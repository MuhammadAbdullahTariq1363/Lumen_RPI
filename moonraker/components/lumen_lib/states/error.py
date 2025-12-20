"""
Error State Detector - Detects Klipper shutdown or error conditions
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class ErrorDetector(BaseStateDetector):
    """
    Detects when Klipper is in an error or shutdown state.

    This is the highest priority state - if Klipper has an error,
    it takes precedence over all other states.

    Detection logic:
        - idle_timeout state is "Error"
        - print_stats state contains "error" or "shutdown"
        - Any critical error condition reported by Klipper

    Common error triggers:
        - Emergency stop / firmware restart
        - MCU communication loss
        - Heater runaway / thermal error
        - Endstop/probe failure
        - Manual FIRMWARE_RESTART command
    """

    name = "error"
    description = "Klipper shutdown or error condition"
    priority = 0  # Highest priority

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if Klipper is in error/shutdown state."""

        # Check idle_timeout state
        idle_timeout = status.get('idle_timeout', {})
        if idle_timeout.get('state', '').lower() == 'error':
            return True

        # Check print_stats state
        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()
        if 'error' in ps_state or 'shutdown' in ps_state:
            return True

        return False
