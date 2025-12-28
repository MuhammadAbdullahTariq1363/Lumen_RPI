"""
Meshing State Detector - Bed mesh calibration in progress

Detects when printer is performing bed mesh calibration.
Activated via macro tracking in lumen.cfg.
"""

from typing import Dict, Optional, Any
from .base import BaseStateDetector


class MeshingDetector(BaseStateDetector):
    """Detect bed mesh calibration state."""

    name = "meshing"
    description = "Bed mesh calibration in progress"
    priority = 5  # High priority - check before heating/idle

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Detect if bed meshing is active.

        Triggered by macro tracking when configured meshing macros are detected
        in G-code responses (typically BED_MESH_CALIBRATE).

        Args:
            status: Printer status (not used for macro-triggered states)
            context: Contains 'active_macro_state' set by macro tracking

        Returns:
            True if meshing macro is active
        """
        if context and context.get('active_macro_state') == 'meshing':
            return True
        return False
