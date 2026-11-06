"""Constants for the Kubu integration."""

DOMAIN = "kubu"
MANUFACTURER = "Kubu"
API_BASE = "https://api-green.kubusmart.com"

CONF_SENSORS = "sensors"
CONF_ACCOUNT_ID = "account_id"

# Logic types whose status word can report these states (see protocol.sensor_state).
LOCK_LOGICS = {8}
TAMPER_LOGICS = {4, 5, 8, 11, 12}
SECURE_LOGICS = {4, 5, 11, 12, 40, 41}

# Battery readings below this are treated as glitches (seen on real RetroPro frames).
MIN_VALID_BATTERY_MV = 1500


def signal_update(entry_id: str, mac: str) -> str:
    """Dispatcher signal for one sensor's state change."""
    return f"{DOMAIN}_update_{entry_id}_{mac}"


def normalize_mac(value: str) -> str:
    """Return a MAC/serial as 12 upper-case hex digits with no separators."""
    return "".join(c for c in value.upper() if c in "0123456789ABCDEF")
