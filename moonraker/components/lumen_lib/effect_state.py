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
    # Rainbow-specific
    rainbow_spread: float = 1.0          # 0.0-1.0, how much rainbow spreads across strip
    # Fire-specific
    fire_cooling: float = 0.3            # 0.0-1.0, cooling rate per update (higher = more chaotic)
    # Comet-specific
    comet_tail_length: int = 10          # Length of trailing tail in LEDs
    comet_fade_rate: float = 0.5         # 0.0-1.0, how quickly tail fades (higher = shorter tail)
    # Chase-specific
    chase_color_1: RGB = (1.0, 0.0, 0.0) # First segment color (red)
    chase_color_2: RGB = (0.0, 0.0, 1.0) # Second segment color (blue)
    chase_size: int = 5                  # LEDs per segment
    chase_offset_base: float = 0.5       # Base distance between segments (0.0-1.0)
    chase_offset_variation: float = 0.1  # Offset variation amount (0.0-1.0)
    # KITT-specific
    kitt_eye_size: int = 3               # LEDs in bright center eye
    kitt_tail_length: int = 8            # Fading LEDs on each side
    kitt_tracking_axis: str = "none"     # "none" | "x" | "y"
    # Thermal/Progress fill effects
    start_color: RGB = (0.5, 0.5, 0.5)  # steel
    end_color: RGB = (0.0, 1.0, 0.0)    # green
    gradient_curve: float = 1.0          # 1.0=linear, >1=sharp at end, <1=sharp at start
    # Thermal-specific
    temp_source: str = "extruder"        # extruder | bed | chamber
    # Direction for fill effects ('standard' or 'reverse')
    direction: str = "standard"
