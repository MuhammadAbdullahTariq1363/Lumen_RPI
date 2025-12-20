#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Modular Architecture - Quick validation script

Verifies that modular effects and states load correctly.
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add moonraker/components to path
component_dir = Path(__file__).parent / "moonraker" / "components"
sys.path.insert(0, str(component_dir))

def test_effect_registry():
    """Test that all effects load from registry."""
    print("Testing Effect Registry...")

    from lumen_lib.effects import EFFECT_REGISTRY

    expected_effects = {'solid', 'pulse', 'heartbeat', 'disco', 'thermal', 'progress', 'off'}
    loaded_effects = set(EFFECT_REGISTRY.keys())

    print(f"  Expected: {sorted(expected_effects)}")
    print(f"  Loaded:   {sorted(loaded_effects)}")

    if loaded_effects == expected_effects:
        print("  [OK] All effects loaded!")
        return True
    else:
        missing = expected_effects - loaded_effects
        extra = loaded_effects - expected_effects
        if missing:
            print(f"  [FAIL] Missing effects: {missing}")
        if extra:
            print(f"  [WARN]  Extra effects: {extra}")
        return False


def test_state_registry():
    """Test that all states load from registry."""
    print("\nTesting State Registry...")

    from lumen_lib.states import STATE_REGISTRY, STATE_PRIORITY

    expected_states = {'idle', 'heating', 'printing', 'cooldown', 'error', 'bored', 'sleep'}
    loaded_states = set(STATE_REGISTRY.keys())

    print(f"  Expected: {sorted(expected_states)}")
    print(f"  Loaded:   {sorted(loaded_states)}")

    if loaded_states == expected_states:
        print("  [OK] All states loaded!")
    else:
        missing = expected_states - loaded_states
        extra = loaded_states - expected_states
        if missing:
            print(f"  [FAIL] Missing states: {missing}")
        if extra:
            print(f"  [WARN]  Extra states: {extra}")
        return False

    print(f"  Priority order: {STATE_PRIORITY}")
    print("  [OK] State priority configured!")
    return True


def test_effect_instances():
    """Test that effect classes can be instantiated."""
    print("\nTesting Effect Instantiation...")

    from lumen_lib.effects import EFFECT_REGISTRY
    from lumen_lib.effects import EffectState
    import time

    errors = []

    for name, effect_class in EFFECT_REGISTRY.items():
        try:
            effect = effect_class()
            state = EffectState(base_color=(1.0, 1.0, 1.0))
            colors, needs_update = effect.calculate(state, time.time(), led_count=10)
            print(f"  [OK] {name}: {len(colors)} colors")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            errors.append((name, e))

    if not errors:
        print("  [OK] All effects instantiate correctly!")
        return True
    else:
        return False


def test_state_instances():
    """Test that state detectors can be instantiated."""
    print("\nTesting State Detector Instantiation...")

    from lumen_lib.states import STATE_REGISTRY

    errors = []

    for name, detector_class in STATE_REGISTRY.items():
        try:
            detector = detector_class()
            # Test detection with empty status
            result = detector.detect({}, {})
            print(f"  [OK] {name}: detector created")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            errors.append((name, e))

    if not errors:
        print("  [OK] All state detectors instantiate correctly!")
        return True
    else:
        return False


def test_state_detector_integration():
    """Test StateDetector class with modular detectors."""
    print("\nTesting StateDetector Integration...")

    from lumen_lib.state import StateDetector, PrinterState

    try:
        detector = StateDetector(temp_floor=25.0, bored_timeout=60.0)
        print(f"  [OK] StateDetector created")
        print(f"  Loaded {len(detector._detectors)} detectors: {list(detector._detectors.keys())}")

        # Test with empty printer state
        state = PrinterState()
        event = detector.update(state)
        print(f"  [OK] Initial event: {event}")

        return True
    except Exception as e:
        print(f"  [FAIL] StateDetector failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("LUMEN Modular Architecture Test")
    print("=" * 60)

    results = []

    results.append(("Effect Registry", test_effect_registry()))
    results.append(("State Registry", test_state_registry()))
    results.append(("Effect Instances", test_effect_instances()))
    results.append(("State Instances", test_state_instances()))
    results.append(("StateDetector Integration", test_state_detector_integration()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("[SUCCESS] All tests passed! Modular architecture is ready.")
        return 0
    else:
        print("[FAIL] Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
