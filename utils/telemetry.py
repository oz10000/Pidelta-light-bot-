# utils/telemetry.py
import json
from datetime import datetime

def log_event(event, data=None):
    """Registra un evento estructurado en JSON por stdout."""
    try:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "event": event,
            "data": data or {}
        }
        print(json.dumps(entry), flush=True)
    except Exception:
        # El bot no debe fallar por un log
        pass
