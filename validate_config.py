#!/usr/bin/env python3
"""
LUMEN Configuration Validator

Validates lumen.cfg syntax and settings without requiring Moonraker.
Useful for checking config before deployment or debugging issues.

Usage:
    python3 validate_config.py /path/to/lumen.cfg
    python3 validate_config.py ~/printer_data/config/lumen.cfg

Returns:
    Exit 0 if config is valid
    Exit 1 if errors found
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ANSI color codes
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color


class ConfigValidator:
    """Validates LUMEN configuration files."""

    VALID_DRIVERS = ['proxy', 'klipper', 'pwm']
    VALID_DIRECTIONS = ['standard', 'reverse']
    VALID_COLOR_ORDERS = ['RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR']
    VALID_EFFECTS = ['solid', 'pulse', 'heartbeat', 'disco', 'thermal', 'progress', 'off']
    VALID_STATES = ['on_idle', 'on_heating', 'on_printing', 'on_cooldown', 'on_error', 'on_bored', 'on_sleep']
    VALID_TEMP_SOURCES = ['bed', 'extruder', 'chamber']
    GPIO_PINS = [12, 13, 18, 19, 21]

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.groups: Dict[str, Dict] = {}
        self.settings: Dict = {}

    def validate(self) -> bool:
        """Run all validation checks."""
        if not self._check_file_exists():
            return False

        self._parse_config()

        if not self.errors:
            self._validate_settings()
            self._validate_groups()
            self._check_consistency()

        return len(self.errors) == 0

    def _check_file_exists(self) -> bool:
        """Check if config file exists."""
        if not self.config_path.exists():
            self.errors.append(f"Config file not found: {self.config_path}")
            return False
        if not self.config_path.is_file():
            self.errors.append(f"Path is not a file: {self.config_path}")
            return False
        return True

    def _parse_config(self):
        """Parse INI-style config file."""
        current_section = None
        current_data = {}

        try:
            with open(self.config_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Section header
                    if line.startswith('[') and line.endswith(']'):
                        # Save previous section
                        if current_section:
                            self._store_section(current_section, current_data)

                        current_section = line[1:-1].strip()
                        current_data = {}
                        continue

                    # Key-value pair
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.split('#')[0].strip()  # Remove inline comments
                        current_data[key] = value
                    else:
                        self.warnings.append(f"Line {line_num}: Malformed line (no colon): {line}")

                # Save last section
                if current_section:
                    self._store_section(current_section, current_data)

        except Exception as e:
            self.errors.append(f"Failed to parse config: {e}")

    def _store_section(self, section: str, data: Dict):
        """Store parsed section data."""
        if section == 'lumen_settings':
            self.settings = data
        elif section.startswith('lumen_group '):
            group_name = section.replace('lumen_group ', '')
            self.groups[group_name] = data
        elif section.startswith('lumen_effect '):
            # Effect settings are optional, just skip
            pass
        else:
            self.warnings.append(f"Unknown section: [{section}]")

    def _validate_settings(self):
        """Validate global settings."""
        if not self.settings:
            self.warnings.append("No [lumen_settings] section found (will use defaults)")
            return

        # Check brightness
        if 'max_brightness' in self.settings:
            try:
                val = float(self.settings['max_brightness'])
                if not (0.0 <= val <= 1.0):
                    self.errors.append(f"max_brightness must be 0.0-1.0 (got {val})")
            except ValueError:
                self.errors.append(f"max_brightness must be a number (got '{self.settings['max_brightness']}')")

        # Check FPS
        if 'gpio_fps' in self.settings:
            try:
                val = int(self.settings['gpio_fps'])
                if not (1 <= val <= 120):
                    self.warnings.append(f"gpio_fps should be 1-120 (got {val}), high values may cause issues")
            except ValueError:
                self.errors.append(f"gpio_fps must be an integer (got '{self.settings['gpio_fps']}')")

        # Check timeouts
        for timeout_key in ['bored_timeout', 'sleep_timeout']:
            if timeout_key in self.settings:
                try:
                    val = int(self.settings[timeout_key])
                    if val < 0:
                        self.errors.append(f"{timeout_key} must be >= 0 (got {val})")
                except ValueError:
                    self.errors.append(f"{timeout_key} must be an integer (got '{self.settings[timeout_key]}')")

    def _validate_groups(self):
        """Validate LED group configurations."""
        if not self.groups:
            self.errors.append("No LED groups defined (no [lumen_group XXX] sections)")
            return

        for group_name, config in self.groups.items():
            self._validate_group(group_name, config)

    def _validate_group(self, group_name: str, config: Dict):
        """Validate a single LED group."""
        # Driver is required
        if 'driver' not in config:
            self.errors.append(f"Group '{group_name}': Missing 'driver' setting")
            return

        driver = config['driver']
        if driver not in self.VALID_DRIVERS:
            self.errors.append(f"Group '{group_name}': Invalid driver '{driver}' (valid: {', '.join(self.VALID_DRIVERS)})")
            return

        # Validate driver-specific requirements
        if driver == 'proxy':
            self._validate_proxy_group(group_name, config)
        elif driver == 'klipper':
            self._validate_klipper_group(group_name, config)
        elif driver == 'pwm':
            self._validate_pwm_group(group_name, config)

        # Validate state effects
        self._validate_state_effects(group_name, config)

        # Validate optional settings
        if 'direction' in config and config['direction'] not in self.VALID_DIRECTIONS:
            self.errors.append(f"Group '{group_name}': Invalid direction '{config['direction']}' (valid: standard, reverse)")

        if 'color_order' in config and config['color_order'].upper() not in self.VALID_COLOR_ORDERS:
            self.warnings.append(f"Group '{group_name}': Uncommon color_order '{config['color_order']}' (common: GRB, RGB)")

    def _validate_proxy_group(self, group_name: str, config: Dict):
        """Validate proxy driver configuration."""
        if 'gpio_pin' not in config:
            self.errors.append(f"Group '{group_name}': proxy driver requires 'gpio_pin'")
        else:
            try:
                pin = int(config['gpio_pin'])
                if pin not in self.GPIO_PINS:
                    self.warnings.append(f"Group '{group_name}': GPIO pin {pin} may not support PWM (valid: {self.GPIO_PINS})")
            except ValueError:
                self.errors.append(f"Group '{group_name}': gpio_pin must be an integer (got '{config['gpio_pin']}')")

        # Check index range
        self._validate_index_range(group_name, config)

    def _validate_klipper_group(self, group_name: str, config: Dict):
        """Validate Klipper driver configuration."""
        if 'neopixel' not in config:
            self.errors.append(f"Group '{group_name}': klipper driver requires 'neopixel' setting")

        # Check index range
        self._validate_index_range(group_name, config)

    def _validate_pwm_group(self, group_name: str, config: Dict):
        """Validate PWM driver configuration."""
        if 'pin_name' not in config:
            self.errors.append(f"Group '{group_name}': pwm driver requires 'pin_name' setting")

        # PWM driver doesn't use index range
        if 'index_start' in config or 'index_end' in config:
            self.warnings.append(f"Group '{group_name}': pwm driver ignores index_start/index_end (brightness only)")

    def _validate_index_range(self, group_name: str, config: Dict):
        """Validate index_start and index_end."""
        if 'index_start' in config:
            try:
                start = int(config['index_start'])
                if start < 1:
                    self.errors.append(f"Group '{group_name}': index_start must be >= 1 (got {start})")
            except ValueError:
                self.errors.append(f"Group '{group_name}': index_start must be an integer")

        if 'index_end' in config:
            try:
                end = int(config['index_end'])
                if end < 1:
                    self.errors.append(f"Group '{group_name}': index_end must be >= 1 (got {end})")
            except ValueError:
                self.errors.append(f"Group '{group_name}': index_end must be an integer")

        # Check range consistency
        if 'index_start' in config and 'index_end' in config:
            try:
                start = int(config['index_start'])
                end = int(config['index_end'])
                if start > end:
                    self.errors.append(f"Group '{group_name}': index_start ({start}) > index_end ({end})")
            except ValueError:
                pass  # Already reported above

    def _validate_state_effects(self, group_name: str, config: Dict):
        """Validate state effect definitions."""
        for state in self.VALID_STATES:
            if state not in config:
                self.warnings.append(f"Group '{group_name}': Missing '{state}' (will use default)")
                continue

            effect_line = config[state]
            self._validate_effect_syntax(group_name, state, effect_line)

    def _validate_effect_syntax(self, group_name: str, state: str, effect_line: str):
        """Validate effect syntax."""
        parts = effect_line.split()
        if not parts:
            self.errors.append(f"Group '{group_name}' {state}: Empty effect definition")
            return

        effect = parts[0]
        if effect not in self.VALID_EFFECTS:
            self.errors.append(f"Group '{group_name}' {state}: Unknown effect '{effect}' (valid: {', '.join(self.VALID_EFFECTS)})")
            return

        # Validate effect-specific syntax
        if effect == 'solid' and len(parts) < 2:
            self.errors.append(f"Group '{group_name}' {state}: 'solid' requires a color (e.g., 'solid white')")
        elif effect in ['pulse', 'heartbeat'] and len(parts) < 2:
            self.errors.append(f"Group '{group_name}' {state}: '{effect}' requires a color (e.g., '{effect} blue')")
        elif effect == 'thermal' and len(parts) < 5:
            self.warnings.append(f"Group '{group_name}' {state}: 'thermal' expects 4 args: source start_color end_color curve")
        elif effect == 'progress' and len(parts) < 4:
            self.warnings.append(f"Group '{group_name}' {state}: 'progress' expects 3 args: start_color end_color curve")

    def _check_consistency(self):
        """Check for consistency issues across config."""
        # Check for duplicate GPIO pins (warning, not error - could be intentional)
        gpio_usage: Dict[int, List[str]] = {}
        for group_name, config in self.groups.items():
            if config.get('driver') == 'proxy' and 'gpio_pin' in config:
                try:
                    pin = int(config['gpio_pin'])
                    if pin not in gpio_usage:
                        gpio_usage[pin] = []
                    gpio_usage[pin].append(group_name)
                except ValueError:
                    pass

        for pin, groups in gpio_usage.items():
            if len(groups) > 1:
                self.warnings.append(f"GPIO pin {pin} used by multiple groups: {', '.join(groups)} (this is OK if intentional)")

    def print_results(self):
        """Print validation results."""
        print(f"\n{BOLD}{CYAN}LUMEN Configuration Validator{NC}")
        print(f"Config: {self.config_path}\n")

        if self.errors:
            print(f"{RED}{BOLD}❌ ERRORS ({len(self.errors)}):{NC}")
            for error in self.errors:
                print(f"  {RED}✗{NC} {error}")
            print()

        if self.warnings:
            print(f"{YELLOW}{BOLD}⚠️  WARNINGS ({len(self.warnings)}):{NC}")
            for warning in self.warnings:
                print(f"  {YELLOW}⚠{NC} {warning}")
            print()

        if not self.errors and not self.warnings:
            print(f"{GREEN}{BOLD}✅ Configuration is valid!{NC}\n")
            print(f"  Found {len(self.groups)} LED group(s)")
            print(f"  Settings: {len(self.settings)} option(s) configured")
        elif not self.errors:
            print(f"{GREEN}{BOLD}✅ Configuration is valid (with warnings){NC}\n")
            print(f"  Found {len(self.groups)} LED group(s)")
        else:
            print(f"{RED}{BOLD}❌ Configuration has errors{NC}\n")

def main():
    parser = argparse.ArgumentParser(
        description='Validate LUMEN configuration file',
        epilog='Example: python3 validate_config.py ~/printer_data/config/lumen.cfg'
    )
    parser.add_argument('config', help='Path to lumen.cfg file')
    parser.add_argument('-q', '--quiet', action='store_true', help='Only show errors (no warnings)')
    args = parser.parse_args()

    validator = ConfigValidator(args.config)
    is_valid = validator.validate()

    if args.quiet:
        validator.warnings = []  # Suppress warnings in quiet mode

    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
