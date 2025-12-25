"""
Filament State Detector - Filament change/runout/load/unload

Detects when filament change operations are in progress.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class FilamentDetector(BaseStateDetector):
    """Detect filament change/runout state."""

    name = "filament"
    description = "Filament change/runout/load/unload in progress"
    priority = 10  # Medium priority - after error/printing, before heating

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if filament change is active.

        Triggered by macro tracking when configured filament macros are detected
        in G-code responses (typically M600, FILAMENT_RUNOUT, LOAD_FILAMENT, UNLOAD_FILAMENT).

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if filament change macro is active
        """
        if context and context.get('active_macro_state') == 'filament':
            return True
        return False
