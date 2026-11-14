"""Shared test doubles."""
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image

TUNIS = timezone(timedelta(hours=1))


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, start=datetime(2026, 11, 4, 14, 0, 0, tzinfo=TUNIS)):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def leaf_image(width=640, height=480, seed=0):
    """A sharp, well-lit, mostly green textured picture: passes every quality check."""
    rng = np.random.default_rng(seed)
    base = np.zeros((height, width, 3), dtype=np.float32)
    base[..., 0] = 60
    base[..., 1] = 150
    base[..., 2] = 50
    # texture at a coarser scale than single pixels (leaf edges, veins, shadows), so it
    # survives the down-scaling done by the quality checks, like a real photo's structure
    coarse = rng.normal(0, 40, size=(height // 4, width // 4, 1))
    base += np.repeat(np.repeat(coarse, 4, axis=0), 4, axis=1)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


class FakeInfo:
    def __init__(self, mid, rc=0):
        self.mid = mid
        self.rc = rc

    def wait_for_publish(self, timeout=None):
        return True


class FakeMqttClient:
    """Records publications; the test decides when the broker acknowledges them."""

    def __init__(self, connected=True):
        self.connected = connected
        self.published = []      # (topic, payload dict, retain, mid)
        self.next_mid = 1
        self.on_publish = None

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload, qos=0, retain=False):
        import json
        mid = self.next_mid
        self.next_mid += 1
        self.published.append((topic, json.loads(payload), retain, mid))
        return FakeInfo(mid)

    def ack_all(self, gateway):
        for _, _, retain, mid in list(self.published):
            gateway.on_publish(self, None, mid)

    def subscribe(self, *args, **kwargs):
        pass

    def will_set(self, *args, **kwargs):
        pass

    def connect_async(self, *args, **kwargs):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        self.connected = False
