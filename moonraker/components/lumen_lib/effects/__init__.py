"""
LUMEN Effects Package

Modular effect system for LED animations.
Each effect is a separate file for easy extension.
"""

from typing import Dict, Type, List, Optional, Tuple
from ..effect_state import EffectState  # Import EffectState from separate module

# Import all effect implementations
from .solid import SolidEffect
from .pulse import PulseEffect
from .heartbeat import HeartbeatEffect
from .disco import DiscoEffect
from .thermal import ThermalEffect
from .progress import ProgressEffect
from .rainbow import RainbowEffect
from .fire import FireEffect
from .comet import CometEffect
from .off import OffEffect

# Base effect class
from .base import BaseEffect

# Effect registry - maps effect names to classes
EFFECT_REGISTRY: Dict[str, Type[BaseEffect]] = {
    'solid': SolidEffect,
    'pulse': PulseEffect,
    'heartbeat': HeartbeatEffect,
    'disco': DiscoEffect,
    'thermal': ThermalEffect,
    'progress': ProgressEffect,
    'rainbow': RainbowEffect,
    'fire': FireEffect,
    'comet': CometEffect,
    'off': OffEffect,
}


def get_effect(name: str) -> Type[BaseEffect]:
    """
    Get effect class by name.

    Args:
        name: Effect name (e.g., 'solid', 'pulse')

    Returns:
        Effect class

    Raises:
        ValueError: If effect name is unknown
    """
    if name not in EFFECT_REGISTRY:
        raise ValueError(
            f"Unknown effect '{name}'. "
            f"Available: {', '.join(EFFECT_REGISTRY.keys())}"
        )
    return EFFECT_REGISTRY[name]


def list_effects() -> List[str]:
    """Return list of available effect names."""
    return sorted(EFFECT_REGISTRY.keys())


__all__ = [
    'BaseEffect',
    'EffectState',
    'EFFECT_REGISTRY',
    'get_effect',
    'list_effects',
    # Individual effects
    'SolidEffect',
    'PulseEffect',
    'HeartbeatEffect',
    'DiscoEffect',
    'ThermalEffect',
    'ProgressEffect',
    'RainbowEffect',
    'FireEffect',
    'CometEffect',
    'OffEffect',
]
