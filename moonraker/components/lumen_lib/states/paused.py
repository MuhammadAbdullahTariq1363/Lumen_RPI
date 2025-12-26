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

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if pause macro is active
        """
        if context and context.get('active_macro_state') == 'paused':
            return True
        return False
