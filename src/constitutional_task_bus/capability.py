"""Capability-bridge adapter for Constitutional Task Bus.

# Mythic: Task & Skills Bus ingress (capability tool)
# Engineering: TaskBusCapability
"""

from __future__ import annotations

from typing import Any

from src.capability_module import AAISCapabilityModule
from src.constitutional_task_bus.dispatch import (
    cache_trace,
    dispatch_task_bus_request,
    task_bus_status,
)

TASK_BUS_COMPONENT_ID = "jarvis.capability.task_bus"


class TaskBusCapability(AAISCapabilityModule):
    module_name = "task_bus"
    supported_actions = frozenset({"dispatch", "status", "catalog"})

    def __init__(self) -> None:
        super().__init__(provider_name="aais_task_bus")
        self.handlers = {
            "dispatch": self._handle_dispatch,
            "status": self._handle_status,
            "catalog": self._handle_status,
        }

    def _handle_dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dispatch_task_bus_request(payload)
        cache_trace(result)
        return self._ok("dispatch", result)

    def _handle_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._ok("status", task_bus_status())
