# Contributing to LUMEN

Thank you for considering contributing to LUMEN! This document provides guidelines and instructions for contributing.

---

## 🌟 Ways to Contribute

- **Report bugs** - Help us identify issues
- **Suggest features** - Share ideas for improvements
- **Submit pull requests** - Fix bugs or add features
- **Improve documentation** - Help others understand LUMEN
- **Test on new hardware** - Validate compatibility
- **Share configs** - Contribute example configurations

---

## 🐛 Reporting Bugs

Before submitting a bug report:

1. **Check existing issues** - Your bug may already be reported
2. **Test with debug mode** - Set `debug: console` in moonraker.conf
3. **Try latest version** - Run `git pull` to ensure you're up to date
4. **Hot reload config** - Try `curl -X POST http://localhost:7125/server/lumen/reload`

Use our [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- LUMEN version (`git describe --tags`)
- Hardware details (Pi model, LED type, GPIO pin)
- Full logs (`sudo journalctl -u moonraker | grep LUMEN`)
- Configuration file (`lumen.cfg`)

---

## 💡 Suggesting Features

Check [TODO.md](TODO.md) first to see if your idea is already planned.

Use our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md) and include:
- **Problem statement** - What issue does this solve?
- **Proposed solution** - How should it work?
- **Example usage** - Show config or API examples
- **Use cases** - Who would benefit?

---

## 🔧 Development Setup

### Prerequisites

- Raspberry Pi with Klipper/Moonraker installed
- Python 3.7+ with venv support
- Git installed
- Basic understanding of async Python

### Clone and Setup

```bash
cd ~
git clone https://github.com/MakesBadDecisions/Lumen_RPI.git lumen
cd lumen
git checkout -b your-feature-branch
```

### Testing Changes

1. **Make your changes** in the appropriate files
2. **Test locally** - Restart Moonraker after code changes
3. **Check logs** - Enable debug mode and verify no errors
4. **Test all states** - Validate idle, heating, printing, cooldown, etc.
5. **Test effects** - Verify visual appearance of changes

---

## 📝 Code Standards

### Python Style

- **PEP 8 compliant** - Use standard Python formatting
- **Type hints** - Add type annotations where practical
- **Async/await** - Use async patterns for I/O operations
- **Docstrings** - Document functions, classes, and modules

**Example:**
```python
async def set_color(self, r: float, g: float, b: float) -> None:
    """Set LED color with RGB values.

    Args:
        r: Red value (0.0-1.0)
        g: Green value (0.0-1.0)
        b: Blue value (0.0-1.0)
    """
    # Implementation
```

### Code Organization

- **Single responsibility** - Functions should do one thing well
- **Clear naming** - Variables and functions should be self-documenting
- **Comments for "why"** - Code shows what, comments explain why
- **Error handling** - Graceful failures with helpful error messages

### Logging

Use LUMEN's logging system:

```python
# Debug logging (only when debug enabled)
self._log_debug(f"Setting color to RGB({r}, {g}, {b})")

# Important info (always logged)
_logger.info(f"[LUMEN] Initialized {len(self.led_groups)} LED groups")

# Warnings
_logger.warning(f"[LUMEN] Invalid color_order '{value}', using GRB")

# Errors
_logger.error(f"[LUMEN] Failed to connect to proxy: {e}")
```

---

## 🚀 Submitting Pull Requests

### Before Submitting

1. **Test thoroughly** - Verify on real hardware if possible
2. **Update documentation** - Modify README.md if adding features
3. **Update CHANGELOG.md** - Add your changes under "Unreleased"
4. **Check for conflicts** - Rebase on latest main branch
5. **Keep commits atomic** - One logical change per commit

### PR Guidelines

**Title Format:**
- `[FEATURE] Add rainbow effect`
- `[FIX] Resolve GPIO 19 initialization error`
- `[DOCS] Improve installation instructions`
- `[PERF] Optimize disco effect random generation`

**Description Should Include:**
- **What changed** - Summary of modifications
- **Why it changed** - Reasoning behind the change
- **Testing done** - What you tested and results
- **Breaking changes** - If any, with migration guide
- **Screenshots/videos** - If visual changes

**Example:**
```markdown
## What Changed
Added rainbow effect that cycles through full color spectrum.

## Why
Users requested a classic rainbow pattern for idle state (Issue #42).

## Testing
- Tested on Voron Trident with 60-LED strip (GPIO 18)
- Verified smooth color transitions at 60fps
- CPU usage <1% on Pi 4
- No conflicts with other effects

## Breaking Changes
None - backward compatible.

## Screenshots
[Attach video of rainbow effect]
```

### Commit Messages

Follow conventional commits format:

```
feat: add rainbow effect to effects.py

- Implemented HSV to RGB color conversion
- Added configurable speed parameter
- Updated lumen.cfg.example with rainbow usage

Closes #42
```

**Commit Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `perf:` Performance improvement
- `refactor:` Code refactoring (no behavior change)
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

---

## 🧪 Testing Guidelines

### Manual Testing Checklist

Before submitting, verify:

- [ ] All LED groups initialize without errors
- [ ] State transitions work (idle → heating → printing → cooldown)
- [ ] Effects render correctly (solid, pulse, heartbeat, disco)
- [ ] Hot reload works without restart
- [ ] API endpoints return valid responses
- [ ] Debug logging works (False/True/console modes)
- [ ] No memory leaks during long runs (24+ hours)

### Test on Multiple Configurations

If possible, test with:
- Different GPIO pins (12, 13, 18, 19, 21)
- Different LED counts (1, 10, 60, 100+)
- Different color orders (GRB, RGB)
- Different Raspberry Pi models (Pi 3, Pi 4, Zero 2W)

---

## 📁 Project Structure

```
lumen/
├── moonraker/components/
│   ├── lumen.py              # Main component (state, API, orchestration)
│   └── lumen_lib/
│       ├── colors.py         # Named color definitions
│       ├── drivers.py        # LED drivers (GPIO, Klipper, PWM)
│       ├── effects.py        # Effect implementations
│       └── state.py          # State detection logic
├── ws281x_proxy.py           # GPIO proxy service (runs as root)
├── install.sh                # Installation script
├── uninstall.sh              # Uninstallation script
├── config/
│   └── lumen.cfg.example     # Example configuration
└── .github/
    └── ISSUE_TEMPLATE/       # Issue templates
```

**Key Files:**
- **lumen.py** - All core logic (state detection, effect orchestration, API endpoints)
- **drivers.py** - Hardware abstraction (ProxyDriver, KlipperDriver, PWMDriver)
- **effects.py** - Visual effects (solid, pulse, heartbeat, disco, thermal, progress)
- **state.py** - Printer state detection (idle, heating, printing, etc.)
- **colors.py** - Named color palette (50+ colors)

---

## 🎨 Adding New Features

### Adding a New Effect

1. **Add to effects.py:**
```python
def calculate_rainbow_effect(num_leds: int, offset: float, brightness: float) -> list:
    """Calculate rainbow effect colors.

    Args:
        num_leds: Number of LEDs in strip
        offset: Animation offset (0.0-1.0)
        brightness: Global brightness multiplier

    Returns:
        List of (r, g, b) tuples for each LED
    """
    # Implementation
```

2. **Update config parser in lumen.py** (search for "effect name parsing")

3. **Add settings section to lumen.cfg.example:**
```ini
[lumen_effect rainbow]
speed: 2.0                 # Cycles per second
brightness: 0.8
```

4. **Update README.md** with usage example

5. **Test thoroughly** on real hardware

### Adding a New Printer State

1. **Add to state.py** - Define detection logic
2. **Update lumen.py** - Add state transition handling
3. **Update lumen.cfg.example** - Add `on_<state>` examples
4. **Update README.md** - Document the new state
5. **Test all transitions** to/from the new state

---

## 🏆 Recognition

Contributors will be credited in:
- **CHANGELOG.md** - Under the relevant release
- **GitHub Release Notes** - In the credits section
- **README.md** - For significant contributions

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## ❓ Questions?

- Open a [Discussion](https://github.com/MakesBadDecisions/Lumen_RPI/discussions)
- Ask in the issue thread
- Check existing code for patterns

---

**Thank you for contributing to LUMEN! 🎉**
