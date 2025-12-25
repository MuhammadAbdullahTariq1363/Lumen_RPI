"""
Cancelled State Detector - Print cancelled by user or macro

Detects when a print is cancelled.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class CancelledDetector(BaseStateDetector):
    """Detect cancelled print state."""

    name = "cancelled"
    description = "Print cancelled by user or macro"
    priority = 10  # Medium priority - after error/printing, before heating

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if print was cancelled.

        Triggered by macro tracking when configured cancel macros are detected
        in G-code responses (typically CANCEL_PRINT macro).

        This is typically a brief state - printer quickly transitions to cooldown or idle.

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if cancel macro is active
        """
        if context and context.get('active_macro_state') == 'cancelled':
            return True
        return False
