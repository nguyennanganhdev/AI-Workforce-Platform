"""Container health probes, Prometheus metrics and transition alerts (stdout + optional webhook)."""
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGETS = {'api': 'http://api:8000/ready', 'reception': 'http://reception:4202/health',
           'coordination': 'http://coordination:4300/health', 'platform': 'http://platform:3001/health',
           'knowledge': 'http://knowledge:8787/health', 'technical-tools': 'http://technical-tools:8788/health',
           'factory': 'http://factory:4010/health', 'operations': 'http://operations:3020/operations/login',
           'field': 'http://field:3023/operations/login',
           'resident': 'http://resident:3011/', 'minio': 'http://minio:9000/minio/health/live',
           'routines': 'http://routines:8789/health'}
STATE = {name: {'up': False, 'failures': 0, 'alerting': False} for name in TARGETS}
LOCK = threading.Lock()
LAST = 0


def notify(event):
    print(json.dumps(event), flush=True)
    webhook = os.getenv('MONITOR_ALERT_WEBHOOK', '').strip()
    if webhook:
        try:
            req = urllib.request.Request(webhook, data=json.dumps(event).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            print(json.dumps({'type': 'alert-delivery-failed', 'service': event['service']}), flush=True)


def probe():
    global LAST
    while True:
        for name, url in TARGETS.items():
            start = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=4) as response:
                    up = response.status == 200
            except Exception:
                up = False
            with LOCK:
                previous = STATE[name]
                failures = 0 if up else previous['failures'] + 1
                alerting = failures >= 3
                event = ('service-recovered' if up else 'service-unavailable') if alerting != previous['alerting'] else None
                STATE[name] = {'up': up, 'failures': failures, 'alerting': alerting,
                               'latency_seconds': round(time.monotonic() - start, 3)}
            if event:
                notify({'type': event, 'service': name, 'time': time.time(), 'failures': failures})
        LAST = time.time()
        time.sleep(int(os.getenv('MONITOR_INTERVAL_SECONDS', '15')))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with LOCK:
            snapshot = dict(STATE)
        if self.path == '/metrics':
            body = '\n'.join(f'vinhomes_service_up{{service="{name}"}} {int(value["up"])}' for name, value in snapshot.items()).encode()
            status, mime = 200, 'text/plain; version=0.0.4'
        elif self.path == '/health':
            status = 200 if LAST and time.time() - LAST < 120 else 503
            body, mime = json.dumps({'status': 'ok' if status == 200 else 'stale', 'services': snapshot}).encode(), 'application/json'
        else:
            body, mime, status = b'Not found', 'text/plain', 404
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    threading.Thread(target=probe, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 9099), Handler).serve_forever()
