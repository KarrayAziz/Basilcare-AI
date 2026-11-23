#!/usr/bin/env bash
# BasilCare edge gateway without systemd:  bash run.sh start | stop | restart | status | log
cd "$(dirname "$0")"
PID=data/gateway.pid
mkdir -p data
running() { [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; }
case "${1:-status}" in
    start)   if running; then echo "already running (pid $(cat $PID))"; exit 0; fi
             nohup .venv/bin/python -m basilcare_edge --config config.toml >> data/gateway.log 2>&1 &
             echo $! > "$PID"; sleep 3
             running && echo "started (pid $(cat $PID)), log: data/gateway.log" || { echo "failed to start:"; tail -20 data/gateway.log; exit 1; } ;;
    stop)    if running; then kill "$(cat "$PID")"; for _ in 1 2 3 4 5 6 7 8 9 10; do running || break; sleep 1; done; fi
             rm -f "$PID"; echo stopped ;;
    restart) bash "$0" stop; bash "$0" start ;;
    status)  running && echo "running (pid $(cat $PID))" || echo "not running" ;;
    log)     tail -n "${2:-30}" data/gateway.log ;;
    *)       echo "usage: bash run.sh start|stop|restart|status|log [lines]"; exit 2 ;;
esac
