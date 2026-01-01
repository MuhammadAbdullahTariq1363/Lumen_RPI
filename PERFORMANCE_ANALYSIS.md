# LUMEN Performance Analysis & Optimization Plan

**Date:** January 1, 2026
**Version:** v1.5.0
**Goal:** Ensure LUMEN has minimal impact on Klipper performance during prints

---

## Executive Summary

**Current Status:** LUMEN is achieving 31+ FPS with 3 ProxyDriver groups during printing. Health metrics show 811 HTTP requests with 100% success rate. Need to verify this rate is optimal and not causing unnecessary overhead.

**Key Findings:**
1. ✅ ProxyDriver has health tracking and backpressure (stops at 10 consecutive failures)
2. ✅ Thermal logging is throttled (only on 1°C change or 10s interval)
3. ⚠️ 811 HTTP requests during print needs analysis - is this normal or excessive?
4. ⚠️ Console logging to Klipper needs review - could block G-code queue
5. ✅ Klipper drivers skip updates during macro states (v1.4.1 fix)

---

## Identified Performance Concerns

### 1. ProxyDriver HTTP Request Rate ⚠️

**Observation:**
```
"total_requests": 811
```

**Analysis Needed:**
- How long was the print? (Need print duration to calculate requests/second)
- Expected rate: 31 FPS × 3 groups = 93 requests/second
- If print was ~10 seconds: 811 / 10 = 81 req/s ✓ (matches ~31 FPS × 3 groups)
- If print was ~30 seconds: 811 / 30 = 27 req/s ✓ (reasonable)
- If print was ~2 minutes: 811 / 120 = 6.7 req/s ✓ (low, good)

**Potential Issues:**
- Each HTTP request has ~1-5ms overhead (network stack, JSON encoding, urllib)
- At 31 FPS × 3 groups = 93 HTTP requests/second during printing
- At 60 FPS × 3 groups = 180 HTTP requests/second target (if we hit 60 FPS)

**Risk Level:** MEDIUM - Need to measure actual overhead

### 2. Console Logging Frequency 🔍

**Current Console Sends:**
```python
# Line 1279 - Thermal effect logging (throttled)
self._log_debug(f"Thermal {group_name}: source={state.temp_source}, ...")
```

**Throttling Logic (lines 1268-1279):**
- Only logs when temp changes ≥1°C OR every 10 seconds
- Per-group throttling (not global)
- During heating: ~6 logs/minute per thermal group (reasonable)
- During printing at stable temp: ~6 logs/minute per thermal group

**Analysis:**
- Console sends go through Klipper's G-code queue
- Each console send is a RESPOND command
- RESPOND commands can block if queue is full

**Current Logging Sources:**
1. Thermal effect debug (throttled) ✓
2. Driver interval caching (startup only) ✓
3. State change events (infrequent) ✓
4. Error messages (rare) ✓

**Risk Level:** LOW - Already well throttled

### 3. Klipper Driver Queue Blocking ✅ FIXED

**Status:** Already addressed in v1.4.1

**Fix Applied (lines 1226-1227):**
```python
# Skip Klipper drivers during macro states (G-code queue blocked)
if self._active_macro_state and isinstance(driver, KlipperDriver):
    continue
```

**Result:** Klipper drivers don't spam SET_LED during macros ✓

**Risk Level:** NONE - Already resolved

### 4. Animation Loop Sleep Precision ⚠️

**Current Code (lines 1315-1321):**
```python
if next_update_times:
    next_update = min(next_update_times)
    interval = max(next_update - now, 0.001)  # Clamp to 1ms minimum
else:
    interval = self.update_rate

# Clamp to maximum 1s to ensure responsive shutdown
interval = min(interval, 1.0)
```

**Analysis:**
- `asyncio.sleep()` precision on Linux: ~1-10ms depending on system load
- Target: 0.0167s (60 FPS) = 16.7ms
- Sleep jitter at high FPS can cause frame timing issues
- At 31 FPS (~32ms per frame), jitter is less problematic

**Potential Issue:**
- If animation loop sleeps for wrong interval, GPIO strips may update slower than intended
- Need to verify `next_update_times` is correctly populated for all active groups

**Risk Level:** LOW - Current 31 FPS suggests timing is working

### 5. Effect Calculation Overhead 🔍

**Effects with High Computation:**

1. **Thermal Effect** - Gradient calculation per LED
   - O(n) where n = LED count
   - Division, color interpolation
   - Runs on every update when target changes

2. **Progress Effect** - Gradient calculation per LED
   - O(n) where n = LED count
   - Similar overhead to thermal

3. **Fire Effect** - Heat simulation per LED
   - O(n) heat tracking array
   - Random number generation per LED
   - HSV → RGB conversion per LED

4. **Chase Effect** - Multi-group coordination
   - O(groups × LEDs) per update
   - Collision detection, proximity calculations

**Risk Level:** LOW - Python is fast enough for <100 LEDs at 30 FPS

### 6. Unnecessary State Data Rebuilding ✅ FIXED

**Status:** Already optimized in v1.4.0

**Fix Applied (line 1166):**
```python
# v1.4.0: Build state_data once per cycle (optimization)
state_data_cache = { ... }
```

**Result:** 93% reduction in dictionary operations ✓

**Risk Level:** NONE - Already resolved

---

## Performance Optimization Plan

### Phase 1: Measurement & Baseline (IMMEDIATE)

**Goal:** Gather empirical data on actual performance impact

**Tasks:**
1. ✅ Add FPS counter to status API (DONE in v1.5.0)
2. 📊 Add request rate metrics to status API
   - HTTP requests per second (ProxyDriver)
   - Console sends per minute
   - Average frame time (ms)
3. 📊 Add CPU/memory profiling endpoint
   - CPU % used by LUMEN animation loop
   - Memory usage (RSS, VMS)
   - Peak frame time (worst case latency)
4. 🧪 Run benchmark during print
   - Monitor Klipper performance metrics
   - Check for G-code queue delays
   - Measure actual FPS during different states

### Phase 2: ProxyDriver Optimization (HIGH PRIORITY)

**Goal:** Reduce HTTP request overhead

**Option A: Batch Updates (RECOMMENDED)**
```python
# Instead of: 3 separate HTTP requests for left/right/center
await driver_left.set_color(r, g, b)
await driver_right.set_color(r, g, b)
await driver_center.set_leds(colors)

# Batch into: 1 HTTP request with multiple groups
await proxy_client.batch_update([
    {"pin": 21, "index_start": 1, "index_end": 50, "color": (r, g, b)},
    {"pin": 21, "index_start": 51, "index_end": 100, "color": (r, g, b)},
    {"pin": 21, "index_start": 101, "index_end": 150, "colors": colors},
])
```

**Benefits:**
- Reduces 3 HTTP requests → 1 HTTP request (67% reduction)
- Reduces network overhead from 93 req/s → 31 req/s at 31 FPS
- Reduces JSON encoding overhead
- Reduces urllib connection overhead

**Implementation:**
1. Add `/batch_update` endpoint to ws281x_proxy.py
2. Add `ProxyBatchClient` class to drivers.py
3. Group ProxyDriver instances by same (proxy_host, proxy_port)
4. Collect color updates during animation loop
5. Send batch at end of loop

**Estimated Impact:** 30-50% reduction in ProxyDriver overhead

**Option B: HTTP Keep-Alive Connections**
- Reuse TCP connections instead of creating new socket per request
- Requires switching from `urllib` to `aiohttp` or similar
- Less impactful than batching, but easier to implement

### Phase 3: Console Logging Optimization (MEDIUM PRIORITY)

**Goal:** Minimize Klipper G-code queue usage

**Current State:**
- Thermal logging: ~6 logs/minute per thermal group
- With 2 thermal groups (left, right): ~12 logs/minute
- 12 RESPOND commands/minute = 0.2 commands/second

**Optimization:**
```python
# Option 1: Increase throttle interval
_last_thermal_log: 10s → 30s  # Reduce from 6 logs/min to 2 logs/min

# Option 2: Disable thermal logging during printing
if is_printing and state.effect == "thermal":
    should_log = False  # Only log during heating/idle

# Option 3: Add global debug level for console
if self.debug != "console":
    return  # Don't send to console, only journalctl
```

**Recommendation:** Option 2 - Disable thermal debug during printing

**Estimated Impact:** Eliminates 12 RESPOND/minute during prints

### Phase 4: Animation Loop Optimization (LOW PRIORITY)

**Goal:** Improve frame timing precision

**Current Issues:**
- Sleep interval calculated per group, then min() taken
- Groups that skip updates still add to `next_update_times`

**Optimization:**
```python
# Only add next_update for groups that actually need updating
if time_since_update >= group_interval:
    # Update group
    await driver.set_color(r, g, b)
    next_update = now + group_interval
    next_update_times.append(next_update)
else:
    # Skip update, but still track when it needs updating
    next_update = last_update + group_interval
    next_update_times.append(next_update)  # ← This is correct
```

**Current code is already correct** - verified at lines 1238-1246

**No changes needed** ✓

### Phase 5: Effect Calculation Caching (FUTURE)

**Goal:** Reduce redundant calculations for static effects

**Example:**
```python
# Solid effect with same color - cache the result
if state.effect == "solid" and state.color == self._last_solid_color:
    return self._cached_solid_result  # Skip calculation
```

**Estimated Impact:** Minimal - solid effect is already O(1)

**Priority:** DEFER - Not worth complexity

---

## Monitoring Dashboard

**Add to `/server/lumen/status` API:**

```json
{
  "performance": {
    "fps": 31.11,
    "avg_frame_time_ms": 32.2,
    "max_frame_time_ms": 45.7,
    "http_requests_per_second": 87.3,
    "console_sends_per_minute": 12,
    "cpu_percent": 2.3,
    "memory_mb": 52.4
  }
}
```

---

## Testing Protocol

### Test 1: Baseline Print Performance

**Setup:**
- Start a known print (e.g., 30min test cube)
- Monitor Klipper metrics during entire print

**Metrics to Capture:**
- Print time (compare with/without LUMEN)
- Klipper CPU usage
- G-code queue depth
- MCU buffer depth
- Any "Timer too close" errors

**Expected Results:**
- Print time difference: <1% (negligible)
- Klipper CPU increase: <5%
- No MCU errors

### Test 2: ProxyDriver Stress Test

**Setup:**
- Set all groups to disco effect (maximum updates)
- Run for 5 minutes during idle
- Monitor HTTP request rate

**Metrics:**
- Total requests in 5 minutes
- Requests per second
- Proxy server CPU usage
- Any failed requests

**Expected Results:**
- At 60 FPS × 3 groups: ~54,000 requests in 5 min (180 req/s)
- At 31 FPS × 3 groups: ~27,900 requests in 5 min (93 req/s)
- 0% failure rate

### Test 3: Console Logging Impact

**Setup:**
- Enable debug="console" mode
- Use thermal effects on all groups
- Run during heating phase (max thermal logging)

**Metrics:**
- Console sends per minute
- Klipper response time
- Any "Klipper busy" messages

**Expected Results:**
- <20 console sends per minute
- No noticeable Klipper slowdown

---

## Implementation Priority

1. **HIGH:** Add performance metrics to status API
2. **HIGH:** Implement ProxyDriver batch updates
3. **MEDIUM:** Disable thermal debug logging during printing
4. **LOW:** Monitor and document baseline performance
5. **DEFER:** Advanced caching and optimizations

---

## Success Criteria

✅ **LUMEN adds <3% CPU overhead to Raspberry Pi**
✅ **No impact on print time or quality**
✅ **No G-code queue delays or "Timer too close" errors**
✅ **ProxyDriver <100 HTTP requests/second during printing**
✅ **Console logging <10 sends/minute during printing**
✅ **Animation FPS ≥30 during all printer states**

---

**Next Steps:**
1. Implement performance metrics in status API
2. Run Test 1 (Baseline Print Performance)
3. Implement ProxyDriver batch updates
4. Re-run tests and compare metrics
