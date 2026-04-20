"""Care Plan Architect — AI layer that converts natural-language requests into
validated CareTask objects for the existing PawPal+ Scheduler."""

# Side-effect import: load .env + configure logging before any other ai.* module
# reads os.environ.
from ai import config as _config  # noqa: F401
