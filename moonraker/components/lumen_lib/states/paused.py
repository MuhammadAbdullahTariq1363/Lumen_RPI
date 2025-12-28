"""
Paused State Detector - Print paused by user or macro

Detects when a print is paused.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class PausedDetector(BaseStateDetector):
    """Detect paused print state."""

    name = "paused"
    description = "Print paused by user or macro"
    priority = 10  # Medium priority - after error/printing, before heating

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if print is paused.

        Triggered by macro tracking when configured pause macros are detected
        in G-code responses (typically PAUSE macro).

        Can also detect via print_stats.state == "paused" if Klipper reports it.

        Args:
            status: Printer status with print_stats
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if print is paused
        """
        # Check macro tracking first
        if context and context.get('active_macro_state') == 'paused':
            return True

        # Fallback: check Klipper print_stats state
        print_stats = status.get('print_stats', {})
        if print_stats.get('state') == 'paused':
            return True

        return False
