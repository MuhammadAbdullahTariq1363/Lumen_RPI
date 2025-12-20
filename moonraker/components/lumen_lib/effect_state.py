"""
LUMEN Effect State - State tracking for LED effects
"""

from dataclasses import dataclass
from .colors import RGB


@dataclass
class EffectState:
    """Tracks the current effect state for a group."""
    effect: str = "off"
    color: RGB = (0.0, 0.0, 0.0)
    base_color: RGB = (0.0, 0.0, 0.0)
    start_time: float = 0.0
    last_update: float = 0.0
    # Effect parameters
    speed: float = 1.0
    min_brightness: float = 0.2
    max_brightness: float = 1.0
    # Disco-specific
    min_sparkle: int = 1
    max_sparkle: int = 6
    # Thermal/Progress fill effects
    start_color: RGB = (0.5, 0.5, 0.5)  # steel
    end_color: RGB = (0.0, 1.0, 0.0)    # green
    gradient_curve: float = 1.0          # 1.0=linear, >1=sharp at end, <1=sharp at start
    # Thermal-specific
    temp_source: str = "extruder"        # extruder | bed | chamber
    # Direction for fill effects ('standard' or 'reverse')
    direction: str = "standard"
