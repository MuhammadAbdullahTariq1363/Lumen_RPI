"""
LUMEN Effects - Backward compatibility import

Effect calculation is now handled by modular effect classes in effects/ directory.
"""

# For backward compatibility, re-export EffectState
from .effect_state import EffectState

__all__ = ['EffectState']
