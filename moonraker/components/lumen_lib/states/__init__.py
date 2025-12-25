"""
State Detection System - Modular printer state detectors

This module provides a registry of state detector classes that analyze printer
status to determine the current operational state.

Usage:
    from .states import STATE_REGISTRY

    detector = STATE_REGISTRY['heating']()
    if detector.detect(printer_status):
        # Heating state detected
        ...

Available States:
    - idle: Printer ready, all temps nominal, not printing
    - heating: Heaters active, warming up to target
    - printing: Active print job, at temperature
    - cooldown: Print finished, still above ambient temp
    - error: Klipper shutdown or error condition
    - bored: Idle for extended period (timeout-based)
    - sleep: Bored for extended period (timeout-based)
    - homing: G28 homing in progress (v1.2.0)
    - meshing: Bed mesh calibration (v1.2.0)
    - leveling: Gantry/bed leveling (v1.2.0)
    - probing: Probe calibration (v1.2.0)
    - paused: Print paused by user/macro (v1.2.0)
    - cancelled: Print cancelled (v1.2.0)
    - filament: Filament change/runout/load/unload (v1.2.0)
"""

from typing import Dict, Type
from .base import BaseStateDetector

# Import all state detector implementations
from .idle import IdleDetector
from .heating import HeatingDetector
from .printing import PrintingDetector
from .cooldown import CooldownDetector
from .error import ErrorDetector
from .bored import BoredDetector
from .sleep import SleepDetector
# v1.2.0 - Macro-triggered states
from .homing import HomingDetector
from .meshing import MeshingDetector
from .leveling import LevelingDetector
from .probing import ProbingDetector
from .paused import PausedDetector
from .cancelled import CancelledDetector
from .filament import FilamentDetector


# State registry: maps state names to detector classes
STATE_REGISTRY: Dict[str, Type[BaseStateDetector]] = {
    'idle': IdleDetector,
    'heating': HeatingDetector,
    'printing': PrintingDetector,
    'cooldown': CooldownDetector,
    'error': ErrorDetector,
    'bored': BoredDetector,
    'sleep': SleepDetector,
    # v1.2.0
    'homing': HomingDetector,
    'meshing': MeshingDetector,
    'leveling': LevelingDetector,
    'probing': ProbingDetector,
    'paused': PausedDetector,
    'cancelled': CancelledDetector,
    'filament': FilamentDetector,
}


# Evaluation order (most specific to least specific)
# Error and printing should be checked first, idle last
STATE_PRIORITY = [
    'error',      # Highest priority - always check errors first
    'homing',     # Homing in progress (v1.2.0)
    'meshing',    # Bed meshing (v1.2.0)
    'leveling',   # Gantry leveling (v1.2.0)
    'probing',    # Probe calibration (v1.2.0)
    'paused',     # Print paused (v1.2.0)
    'cancelled',  # Print cancelled (v1.2.0)
    'filament',   # Filament change (v1.2.0)
    'printing',   # Active print job
    'heating',    # Warming up
    'cooldown',   # Cooling down after print
    'sleep',      # Timeout-based deep idle
    'bored',      # Timeout-based idle
    'idle',       # Default fallback state
]


__all__ = [
    'STATE_REGISTRY',
    'STATE_PRIORITY',
    'BaseStateDetector',
    'IdleDetector',
    'HeatingDetector',
    'PrintingDetector',
    'CooldownDetector',
    'ErrorDetector',
    'BoredDetector',
    'SleepDetector',
    # v1.2.0
    'HomingDetector',
    'MeshingDetector',
    'LevelingDetector',
    'ProbingDetector',
    'PausedDetector',
    'CancelledDetector',
    'FilamentDetector',
]
