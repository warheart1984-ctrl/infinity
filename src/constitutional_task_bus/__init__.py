"""Constitutional Task Bus — thin AAIS host; canonical impl is aais-middleware/.

# Mythic: Constitutional Task Bus
# Engineering: ConstitutionalTaskBusHost
"""

from src.constitutional_task_bus.dispatch import (
    cache_trace,
    dispatch_task_bus_request,
    get_cached_trace,
    task_bus_status,
)

# Capability bridge adapter (Python) still available for jarvis tools
try:
    from src.constitutional_task_bus.capability import TASK_BUS_COMPONENT_ID, TaskBusCapability
except Exception:  # pragma: no cover
    TASK_BUS_COMPONENT_ID = "jarvis.capability.task_bus"
    TaskBusCapability = None  # type: ignore

__all__ = [
    "dispatch_task_bus_request",
    "task_bus_status",
    "cache_trace",
    "get_cached_trace",
    "TaskBusCapability",
    "TASK_BUS_COMPONENT_ID",
]
