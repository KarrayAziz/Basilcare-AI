"""The gateway main loop: sensors -> local queue -> MQTT, pump commands, screenings.

Threads:
- main thread: one measurement cycle every interval_s, pump watchdog about every 0.5 s,
  sending the queue whenever connected;
- paho's network thread: connection, reconnection, incoming pump commands, acknowledgements;
- a short-lived screening thread, so a slow inference never delays readings or the watchdog;
- the live-view thread (optional): camera frames with detections, QoS 0, only while connected.

The gateway keeps working without network: readings go to the SQLite queue and the pump
watchdog keeps enforcing the duration and water-level limits locally (scope section 4.2).
"""
import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

from . import SOFTWARE, messages

log = logging.getLogger(__name__)

MAX_INFLIGHT = 50   # messages published but not yet acknowledged


class Gateway:
    def __init__(self, config, sensors, guard, outbox, screening=None, client=None, clock=messages.local_now,
                 live=None):
        self.config = config
        self.device_id = config.device_id
        self.sensors = sensors
        self.guard = guard
        self.outbox = outbox
        self.screening = screening
        self.live = live
        self.live_thread = None
        self.clock = clock
        self.started_at = clock()
        self.seq = {}                 # per sensor; restarts at 1 with the software (contract section 3.2)
        self.failures = {}            # consecutive read failures per sensor
        self.inflight = {}            # MQTT message id -> outbox row id
        self.acked_early = set()      # acknowledged before flush() recorded them
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.stop_event = threading.Event()
        self.shut_down = False
        self.screening_thread = None
        self.client = client or self._make_client()

    # ---- MQTT -------------------------------------------------------------------------

    def _make_client(self):
        cfg = self.config.mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.device_id}-edge")
        if cfg.username:
            client.username_pw_set(cfg.username, cfg.password or None)
        if cfg.tls:
            client.tls_set(ca_certs=cfg.ca_file or None)
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        return client

    def _status(self, online, will=False):
        return messages.status(self.device_id, online, self.started_at, self.config.interval_s, SOFTWARE,
                               None if will else self.clock())

    def connect(self):
        will_topic, will, _ = self._status(False, will=True)
        self.client.will_set(will_topic, json.dumps(will), qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        # connect_async + loop_start: the gateway runs (and queues) even if the broker is unreachable
        self.client.connect_async(self.config.mqtt.host, self.config.mqtt.port, self.config.mqtt.keepalive_s)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            log.error("broker refused the connection: %s", reason_code)
            return
        log.info("connected to %s:%s", self.config.mqtt.host, self.config.mqtt.port)
        client.subscribe(messages.topic(self.device_id, "pump", "cmd"), qos=1)
        self._publish_now(self._status(True))     # replaces the retained Last Will
        self._publish_now(self.guard.current())
        self.connected.set()

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected.clear()
        with self.lock:
            self.inflight.clear()
            self.acked_early.clear()
        self.outbox.release_inflight()
        log.warning("disconnected from the broker (%s); readings are queued locally", reason_code)

    def on_message(self, client, userdata, msg):
        reply = self.guard.handle(msg.payload)
        if reply:
            log.info("pump command: %s", reply[1])
            self._publish_now(reply)

    def on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        with self.lock:
            row_id = self.inflight.pop(mid, None)
            if row_id is None:
                self.acked_early.add(mid)   # PUBACK faster than flush() recording the mid
        if row_id is not None:
            self.outbox.done(row_id)

    def _publish_now(self, message):
        """Retained state messages (status, pump/state): sent directly, the latest state is what matters."""
        topic, payload, retain = message
        if self.client.is_connected():
            self.client.publish(topic, json.dumps(payload), qos=1, retain=retain)

    # ---- work -------------------------------------------------------------------------

    def measure(self):
        """One measurement cycle: every sensor read once, readings queued."""
        now = self.clock()
        for sensor in self.sensors:
            try:
                value = sensor.read()
            except Exception as error:   # one broken probe must not stop the others
                count = self.failures.get(sensor.name, 0) + 1
                self.failures[sensor.name] = count
                if count in (1, 10) or count % 100 == 0:
                    log.warning("sensor %s failed %d time(s) in a row: %s", sensor.name, count, error)
                continue
            self.failures[sensor.name] = 0
            if sensor.name == "water_level":
                self.guard.set_water_level(value)
            self.seq[sensor.name] = self.seq.get(sensor.name, 0) + 1
            topic, payload, _ = messages.reading(self.device_id, sensor.name, value, now, sensor.calibrated,
                                                 self.seq[sensor.name])
            self.outbox.add(topic, payload)

    def flush(self):
        """Sends queued messages, oldest first, while connected."""
        if not self.client.is_connected():
            return
        with self.lock:
            room = MAX_INFLIGHT - len(self.inflight)
        if room <= 0:
            return
        late_after = 1.5 * self.config.interval_s
        now = self.clock()
        for row_id, topic, payload in self.outbox.take(room):
            if "/telemetry/" in topic and not payload.get("buffered"):
                measured = messages.parse_time(payload.get("measured_at"))
                # waited in the queue (outage): history, never shown as a live value (contract 3.2)
                if measured and (now - measured).total_seconds() > late_after:
                    payload["buffered"] = True
            # Never hold self.lock while calling paho: paho may run on_publish while holding its
            # own lock, and on_publish takes self.lock (deadlock). Instead, an acknowledgement
            # that arrives before the mid is recorded is remembered in acked_early.
            info = self.client.publish(topic, json.dumps(payload), qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                self.outbox.release_inflight()
                return
            with self.lock:
                already_acked = info.mid in self.acked_early
                self.acked_early.discard(info.mid)
                if not already_acked:
                    self.inflight[info.mid] = row_id
            if already_acked:
                self.outbox.done(row_id)

    def watchdog(self):
        message = self.guard.watchdog()
        if message:
            log.info("pump stopped by the device: %s", message[1]["reason"])
            self._publish_now(message)

    def start_screening(self):
        if self.screening is None or (self.screening_thread and self.screening_thread.is_alive()):
            return

        def work():
            try:
                topic, payload, _ = self.screening.run()
                self.outbox.add(topic, payload)
            except Exception:
                log.exception("screening failed")

        self.screening_thread = threading.Thread(target=work, name="screening", daemon=True)
        self.screening_thread.start()

    def start_live(self):
        if self.live is None:
            return

        def publish(topic, payload):
            self.client.publish(topic, json.dumps(payload), qos=0, retain=False)

        self.live_thread = threading.Thread(target=self.live.run, args=(publish, self.connected, self.stop_event),
                                            name="live", daemon=True)
        self.live_thread.start()

    # ---- life cycle -------------------------------------------------------------------

    def run(self):
        """Main loop. Whatever ends it (stop(), an exception such as a full SD card), the
        pump is switched off and the broker is told we are gone (review finding #2)."""
        self.connect()
        self.start_live()
        interval = self.config.interval_s
        screening_every = self.config.camera.every_s
        next_measure = time.monotonic()
        next_screening = time.monotonic() + 15   # first picture shortly after start
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now >= next_measure:
                    self.measure()
                    next_measure += interval
                    if next_measure < now:            # the Pi was suspended or very slow: do not catch up
                        next_measure = now + interval
                if self.screening and now >= next_screening:
                    self.start_screening()
                    next_screening = now + screening_every
                self.watchdog()
                self.flush()
                self.stop_event.wait(0.5)
        except BaseException:
            log.exception("gateway loop failed; stopping the pump and going offline")
            raise
        finally:
            self.shutdown()

    def stop(self):
        self.stop_event.set()

    def shutdown(self):
        """Clean stop: pump off FIRST, then say goodbye (the broker does not send the Last Will
        then). Each step is independent: a failure in one never skips the relay."""
        if self.shut_down:
            return
        self.shut_down = True
        try:
            self.guard.shutdown()
        except Exception:
            log.exception("could not switch the relay off")
        try:
            if self.client.is_connected():
                topic, payload, retain = self._status(False)
                self.client.publish(topic, json.dumps(payload), qos=1, retain=retain).wait_for_publish(timeout=5)
                self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            log.exception("could not say goodbye to the broker")
        try:
            log.info("stopped; %d message(s) still queued for the next start", self.outbox.pending())
            self.outbox.close()
        except Exception:
            log.exception("could not close the outbox")
