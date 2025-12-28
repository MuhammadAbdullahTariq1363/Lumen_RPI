#!/usr/bin/env python3
"""
WS281x Debug Proxy - Heavy logging to diagnose flickering

Run with: sudo python3 ws281x_proxy_debug.py --port 3769
Watch logs: sudo journalctl -u ws281x-proxy -f
"""

import argparse
import os
import sys
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock
import time

from rpi_ws281x import PixelStrip, Color, ws

logging.basicConfig(level=logging.INFO, format='[WS281X] %(asctime)s.%(msecs)03d %(message)s', datefmt='%H:%M:%S')
_logger = logging.getLogger(__name__)

STRIP_TYPES = {
    'RGB': ws.WS2811_STRIP_RGB,
    'RBG': ws.WS2811_STRIP_RBG,
    'GRB': ws.WS2811_STRIP_GRB,
    'GBR': ws.WS2811_STRIP_GBR,
    'BRG': ws.WS2811_STRIP_BRG,
    'BGR': ws.WS2811_STRIP_BGR,
}
DEFAULT_STRIP_TYPE = ws.WS2811_STRIP_GRB

# Single strip, single lock - absolute simplicity
_strip: Optional[PixelStrip] = None
_strip_size: int = 0
_strip_lock = Lock()
_request_count = 0
_last_show_time = 0.0


def _init_strip(total: int, pin: int = 18, strip_type: int = DEFAULT_STRIP_TYPE) -> PixelStrip:
    """Initialize or get the strip."""
    global _strip, _strip_size
    
    with _strip_lock:
        if _strip is None or total > _strip_size:
            _logger.info(f"Creating strip: {total} LEDs on GPIO {pin}")
            _strip = PixelStrip(total, pin, 800000, 10, False, 255, 0, strip_type)
            _strip.begin()
            _strip_size = total
        return _strip


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging
    
    def _send_json(self, code: int, payload: Dict):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        if self.path == '/status':
            self._send_json(200, {'strip_size': _strip_size, 'requests': _request_count})
        else:
            self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        global _request_count, _last_show_time
        
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        data = json.loads(body or b'{}')
        
        _request_count += 1
        req_id = _request_count
        
        if self.path == '/set_color':
            gpio_pin = int(data.get('gpio_pin', 18))
            start = int(data.get('index_start', 1))
            end = int(data.get('index_end', start))
            r = float(data.get('r', 0))
            g = float(data.get('g', 0))
            b = float(data.get('b', 0))
            color_order = data.get('color_order', 'GRB').upper()
            strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)
            
            _logger.info(f"[{req_id}] set_color: LEDs {start}-{end}, RGB=({r:.2f},{g:.2f},{b:.2f})")
            
            strip = _init_strip(end, gpio_pin, strip_type)
            
            with _strip_lock:
                t0 = time.time()
                c = Color(int(r * 255), int(g * 255), int(b * 255))
                for i in range(start - 1, end):
                    strip.setPixelColor(i, c)
                t1 = time.time()
                strip.show()
                t2 = time.time()
                _last_show_time = t2
                
            _logger.info(f"[{req_id}] set_color done: setPixels={1000*(t1-t0):.1f}ms, show={1000*(t2-t1):.1f}ms")
            self._send_json(200, {'result': 'ok'})
            return
            
        if self.path == '/set_leds':
            gpio_pin = int(data.get('gpio_pin', 18))
            start = int(data.get('index_start', 1))
            colors = data.get('colors', [])
            end_needed = start - 1 + len(colors)
            color_order = data.get('color_order', 'GRB').upper()
            strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)
            
            # Sample first few colors for logging
            sample = []
            for c in colors[:3]:
                if c is None:
                    sample.append("None")
                else:
                    sample.append(f"({c[0]:.2f},{c[1]:.2f},{c[2]:.2f})")
            
            _logger.info(f"[{req_id}] set_leds: start={start}, count={len(colors)}, sample={sample}")
            
            strip = _init_strip(end_needed, gpio_pin, strip_type)
            
            with _strip_lock:
                t0 = time.time()
                for i, color in enumerate(colors):
                    led_index = start - 1 + i
                    if led_index >= _strip_size:
                        _logger.warning(f"[{req_id}] LED index {led_index} >= strip size {_strip_size}!")
                        break
                    if color is None:
                        strip.setPixelColor(led_index, Color(0, 0, 0))
                    else:
                        cr, cg, cb = color
                        strip.setPixelColor(led_index, Color(int(cr * 255), int(cg * 255), int(cb * 255)))
                t1 = time.time()
                strip.show()
                t2 = time.time()
                
                # Check time since last show
                gap = t0 - _last_show_time if _last_show_time > 0 else 0
                _last_show_time = t2
                
            _logger.info(f"[{req_id}] set_leds done: setPixels={1000*(t1-t0):.1f}ms, show={1000*(t2-t1):.1f}ms, gap={1000*gap:.1f}ms")
            self._send_json(200, {'result': 'ok'})
            return
            
        self._send_json(404, {'error': 'not found'})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=3769)
    p.add_argument('--host', type=str, default='127.0.0.1')
    args = p.parse_args()

    _logger.info(f"Starting DEBUG proxy on {args.host}:{args.port}")
    _logger.info(f"Python: {sys.executable}, PID: {os.getpid()}")
    
    # Use simple single-threaded server to avoid any threading issues
    httpd = HTTPServer((args.host, args.port), Handler)
    _logger.info("Using single-threaded HTTPServer (no threading)")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _logger.info("Stopping")
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()