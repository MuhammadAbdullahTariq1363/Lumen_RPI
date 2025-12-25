"""
Chase Effect - Two colored segments chasing each other
"""

import random
import math
from typing import List, Optional, Tuple, Dict, Any
from .base import BaseEffect
from ..colors import RGB
from ..effects import EffectState


class ChaseEffect(BaseEffect):
    """
    Chase effect - two colored segments chasing each other around the strip.

    Creates a dynamic chase pattern with two segments that vary their distance
    from each other during animation for visual interest.

    Multi-group support: When multiple groups use chase with numbering
    (e.g., "chase 1", "chase 2"), they coordinate to create a seamless
    animation across all strips.

    Parameters (from EffectState):
        - chase_color_1: Color of first segment (predator)
        - chase_color_2: Color of second segment (prey)
        - speed: Movement speed (LEDs per second)
        - chase_size: LEDs per segment
        - chase_offset_base: Base distance between segments (0.0-1.0 of strip length)
        - chase_offset_variation: How much offset varies (0.0-1.0)
        - chase_proximity_threshold: Distance threshold for proximity acceleration (0.0-1.0)
        - chase_accel_factor: Speed multiplier when hunting/fleeing
        - chase_role_swap_interval: Average seconds between random role swaps
        - chase_collision_pause: Seconds to pause after collision
        - max_brightness: Maximum brightness
    """

    name = "chase"
    description = "Two colored segments chasing each other"
    requires_led_count = True

    def __init__(self):
        super().__init__()
        # Single-group mode state
        self._offset_phase = 0.0

        # Multi-group mode state
        self._predator_pos = 0.0  # Position in circular array
        self._prey_pos = 0.0
        self._predator_vel = 1.0  # Velocity (LEDs per second)
        self._prey_vel = -1.0
        self._predator_is_first = True  # True if predator is color_1
        self._last_role_swap = 0.0
        self._collision_pause_until = 0.0
        self._last_random_change = 0.0

    def calculate(
        self,
        state: EffectState,
        now: float,
        led_count: int = 1,
        state_data: Optional[dict] = None
    ) -> Tuple[List[Optional[RGB]], bool]:
        """Calculate chase segment positions and colors."""
        # Check if multi-group mode (state_data contains multi_group_info)
        if state_data and "multi_group_info" in state_data:
            return self._calculate_multi_group(state, now, led_count, state_data["multi_group_info"])

        # Single-group mode
        if led_count <= 1:
            # Single LED: just alternate colors
            elapsed = now - state.start_time
            phase = int(elapsed * state.speed) % 2
            return [state.chase_color_1 if phase == 0 else state.chase_color_2], True

        elapsed = now - state.start_time

        # Calculate first segment position (wraps around)
        position_1 = (elapsed * state.speed) % led_count

        # Calculate dynamic offset
        # Base offset + sinusoidal variation
        self._offset_phase = (elapsed * 0.5) % (2 * math.pi)  # Slow variation
        offset_variation = math.sin(self._offset_phase) * state.chase_offset_variation
        current_offset = state.chase_offset_base + offset_variation

        # Ensure offset stays in reasonable range (0.2 to 0.8 of strip length)
        current_offset = max(0.2, min(0.8, current_offset))

        # Second segment position
        position_2 = (position_1 + led_count * current_offset) % led_count

        colors: List[Optional[RGB]] = []

        for i in range(led_count):
            # Check if LED is in segment 1
            in_segment_1 = self._in_segment(i, position_1, state.chase_size, led_count)
            # Check if LED is in segment 2
            in_segment_2 = self._in_segment(i, position_2, state.chase_size, led_count)

            if in_segment_1:
                # Apply brightness to color 1
                r, g, b = state.chase_color_1
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            elif in_segment_2:
                # Apply brightness to color 2
                r, g, b = state.chase_color_2
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            else:
                # LED off
                colors.append(None)

        return colors, True

    def _calculate_multi_group(
        self,
        state: EffectState,
        now: float,
        total_leds: int,
        multi_group_info: Dict[str, Any]
    ) -> Tuple[List[Optional[RGB]], bool]:
        """
        Calculate chase for multi-group circular array with predator/prey behavior.

        Args:
            state: Effect state
            now: Current time
            total_leds: Total LEDs in circular array
            multi_group_info: Dict with group mapping info from lumen.py

        Returns:
            Full circular array of colors
        """
        # Initialize positions on first call
        if self._predator_pos == 0.0 and self._prey_pos == 0.0:
            self._predator_pos = 0.0
            self._prey_pos = total_leds * 0.5  # Start on opposite side
            self._last_role_swap = now
            self._last_random_change = now

        # Check if we're paused after collision
        if now < self._collision_pause_until:
            # Return current frozen state
            return self._render_segments(state, total_leds), True

        # Calculate time delta for physics
        dt = 1.0 / 60.0  # Assume 60 FPS for smooth animation

        # Check for random role swap (every ~7 seconds on average)
        swap_interval = getattr(state, 'chase_role_swap_interval', 7.0)
        if now - self._last_role_swap > swap_interval:
            variation = random.uniform(-2.0, 2.0)
            if random.random() < 0.5:  # 50% chance to swap
                self._swap_roles()
                self._last_role_swap = now + variation

        # Calculate distance between predator and prey
        distance = self._get_circular_distance(self._predator_pos, self._prey_pos, total_leds)
        proximity_threshold = getattr(state, 'chase_proximity_threshold', 0.15) * total_leds

        # Check for collision
        if distance < state.chase_size:
            # Collision! Bounce, pause, and swap roles
            self._handle_collision(state, now, total_leds)
            return self._render_segments(state, total_leds), True

        # Proximity acceleration
        accel_factor = getattr(state, 'chase_accel_factor', 1.5)
        base_speed = state.speed

        if distance < proximity_threshold:
            # Close proximity - predator speeds up, prey flees
            predator_speed = base_speed * accel_factor
            prey_speed = base_speed * accel_factor
        else:
            # Normal speed
            predator_speed = base_speed
            prey_speed = base_speed

        # Add random speed variation every ~2 seconds
        if now - self._last_random_change > 2.0:
            self._last_random_change = now
            if random.random() < 0.3:  # 30% chance
                # Random direction change or speed variation
                if random.random() < 0.5:
                    self._predator_vel *= -1  # Reverse direction
                else:
                    self._prey_vel *= -1

        # Update velocities
        predator_dir = 1.0 if self._predator_vel > 0 else -1.0
        prey_dir = 1.0 if self._prey_vel > 0 else -1.0

        # Update positions
        self._predator_pos = (self._predator_pos + predator_dir * predator_speed * dt) % total_leds
        self._prey_pos = (self._prey_pos + prey_dir * prey_speed * dt) % total_leds

        # Render segments
        return self._render_segments(state, total_leds), True

    def _render_segments(self, state: EffectState, total_leds: int) -> List[Optional[RGB]]:
        """Render predator and prey segments to color array."""
        colors: List[Optional[RGB]] = []

        # Determine which color goes with which position
        if self._predator_is_first:
            predator_color = state.chase_color_1
            prey_color = state.chase_color_2
        else:
            predator_color = state.chase_color_2
            prey_color = state.chase_color_1

        for i in range(total_leds):
            in_predator = self._in_segment(i, self._predator_pos, state.chase_size, total_leds)
            in_prey = self._in_segment(i, self._prey_pos, state.chase_size, total_leds)

            if in_predator:
                r, g, b = predator_color
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            elif in_prey:
                r, g, b = prey_color
                colors.append((r * state.max_brightness, g * state.max_brightness, b * state.max_brightness))
            else:
                colors.append(None)

        return colors

    def _get_circular_distance(self, pos1: float, pos2: float, total: int) -> float:
        """Calculate shortest distance between two positions on circular array."""
        direct = abs(pos2 - pos1)
        wraparound = total - direct
        return min(direct, wraparound)

    def _swap_roles(self) -> None:
        """Swap predator and prey roles."""
        self._predator_is_first = not self._predator_is_first

    def _handle_collision(self, state: EffectState, now: float, total_leds: int) -> None:
        """Handle collision between predator and prey."""
        # Reverse both velocities (bounce)
        self._predator_vel *= -1
        self._prey_vel *= -1

        # Swap roles
        self._swap_roles()

        # Set pause duration
        pause_duration = getattr(state, 'chase_collision_pause', 0.3)
        self._collision_pause_until = now + pause_duration

        # Move them apart slightly to prevent immediate re-collision
        separation = state.chase_size * 1.5
        if self._predator_vel > 0:
            self._predator_pos = (self._predator_pos + separation) % total_leds
            self._prey_pos = (self._prey_pos - separation) % total_leds
        else:
            self._predator_pos = (self._predator_pos - separation) % total_leds
            self._prey_pos = (self._prey_pos + separation) % total_leds

    @staticmethod
    def _in_segment(led_index: int, segment_position: float, segment_size: int, led_count: int) -> bool:
        """
        Check if LED is within a segment, handling wrap-around.

        Args:
            led_index: LED position (0 to led_count-1)
            segment_position: Center of segment (0.0 to led_count)
            segment_size: Number of LEDs in segment
            led_count: Total LEDs in strip

        Returns:
            True if LED is in segment
        """
        # Segment spans from (position - size/2) to (position + size/2)
        start = segment_position - segment_size / 2.0
        end = segment_position + segment_size / 2.0

        # Check if LED is in range, handling wrap-around
        if end <= led_count:
            # No wrap-around
            return start <= led_index < end
        else:
            # Wraps around end
            return led_index >= start or led_index < (end % led_count)
