"""Constants for the NomadDeck integration."""

DOMAIN = "nomaddeck"

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 8787
DEFAULT_SCAN_INTERVAL = 30

# Endpoints on the NomadDeck control plane
ENDPOINT_HEALTH = "/api/fleet-health"
ENDPOINT_STATUS = "/api/status"

MANUFACTURER = "Yepiz Tech LLC"
MODEL = "NomadDeck Control Plane"

# Coordinator keys
DATA_HEALTH = "health"
DATA_STATUS = "status"
