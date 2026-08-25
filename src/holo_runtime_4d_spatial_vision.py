"""HoloRT4D spatial vision probe — governed, deterministic observer frame.

Mythic: HoloRT4D Spatial Vision
Engineering: HoloRuntime4dSpatialVisionEngine

Inputs:
  observer, space_id, optional targets / tick / seed_demo / nodes+edges
Outputs:
  SpatialVisionProbeResult with visible/occluded/depth_order
Constraints:
  read-only probe; no autonomous space mutation unless seed_demo or build payload
Failure modes:
  missing observer/space_id → ValueError (fail-closed)
"""

from __future__ import annotations

from typing import Any

from src.Spatial_reasoning import SpatialReasoningPlug

ENGINE_ID = "holo_runtime_4d_spatial_vision"
ENGINE_VERSION = "holo_runtime_4d_spatial_vision.v1"
MODULE_ID = "AAIS-HRT4D-SV-01"
DEFAULT_SPACE_ID = "holo_rt4d_demo"
DEMO_OBSERVER = "observer"


def build_holo_rt4d_spatial_vision_status(
    *,
    plug: SpatialReasoningPlug | None = None,
) -> dict[str, Any]:
    """Read-only posture snapshot for console / status routes."""
    active = plug if plug is not None else SpatialReasoningPlug()
    summary = (
        f"engine={ENGINE_VERSION};spaces={len(active.spaces)};"
        f"entities={len(active.entities)};bridge=holo_rt4d"
    )[:128]
    return {
        "holo_rt4d_spatial_vision_version": ENGINE_VERSION,
        "module_id": MODULE_ID,
        "engine_id": ENGINE_ID,
        "status_summary": summary,
        "bridge_capability_id": "holo_rt4d",
        "bridge_tool": "holo_rt4d_spatial_vision",
        "active_space_count": len(active.spaces),
        "active_entity_count": len(active.entities),
        "bridge_safe": True,
        "operator_gated": True,
        "cisiv_stage": "implementation",
        "claim_label": "asserted",
        "read_only": True,
        "seed_demo_space_id": DEFAULT_SPACE_ID,
    }


class HoloRuntime4dSpatialVisionEngine:
    """Probe what an observer can see in a spatial graph at a given tick."""

    def __init__(self, plug: SpatialReasoningPlug | None = None) -> None:
        self.plug = plug if plug is not None else SpatialReasoningPlug()

    def ensure_demo_space(self, space_id: str = DEFAULT_SPACE_ID) -> dict[str, Any]:
        """Install a deterministic demo grid when the operator has no prior space."""
        normalized = " ".join(str(space_id or DEFAULT_SPACE_ID).split()).strip() or DEFAULT_SPACE_ID
        if normalized in self.plug.spaces:
            return {
                "space_id": normalized,
                "seeded": False,
                "node_count": len(self.plug.spaces[normalized]["nodes"]),
            }
        built = self.plug.build_space(
            normalized,
            nodes=[
                {"id": "observer", "x": 0, "y": 0, "z": 0},
                {"id": "north", "x": 0, "y": 2, "z": 0},
                {"id": "east", "x": 2, "y": 0, "z": 0},
                {"id": "west", "x": -2, "y": 0, "z": 0},
                {"id": "south", "x": 0, "y": -2, "z": 0},
                {"id": "blocker", "x": 0, "y": 1, "z": 0, "type": "obstacle", "name": "blocker"},
            ],
            edges=[
                {"from": "observer", "to": "east", "weight": 2},
                {"from": "observer", "to": "west", "weight": 2},
                {"from": "observer", "to": "south", "weight": 2},
                {"from": "observer", "to": "blocker", "weight": 1, "obstacle": True, "name": "blocker"},
                {"from": "blocker", "to": "north", "weight": 1},
            ],
        )
        self.plug.place_entity("scout", normalized, "east", role="mobile", active_ticks=[0, 1, 2])
        self.plug.place_entity("beacon", normalized, "south", role="static", active_ticks=[0, 1, 2, 3])
        self.plug.place_entity("phantom", normalized, "north", role="ephemeral", active_ticks=[2, 3])
        return {
            "space_id": built["space_id"],
            "seeded": True,
            "node_count": built["node_count"],
            "edge_count": built["edge_count"],
        }

    def probe(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """
        Run one spatial-vision probe.

        Required: observer (or from), space_id (unless seed_demo builds default).
        Optional: targets, tick, seed_demo, nodes, edges.

        SpatialPlugLiveSpaceBinding: when the shared plug already has live spaces,
        prefer those over seeding the demo grid (demo is fallback only).
        """
        args = dict(payload or {})
        space_id = " ".join(str(args.get("space_id") or "").split()).strip()
        observer = " ".join(
            str(args.get("observer") or args.get("from") or "").split()
        ).strip()
        seed_demo = _coerce_bool(args.get("seed_demo"), default=True)
        tick = _coerce_int(args.get("tick"), default=0)
        if tick < 0:
            raise ValueError("tick must be >= 0")

        live_space_ids = [sid for sid in self.plug.spaces.keys() if sid]
        prefer_live = bool(live_space_ids) and _coerce_bool(
            args.get("prefer_live_spaces"),
            default=True,
        )

        nodes = args.get("nodes")
        edges = args.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list) and space_id:
            self.plug.build_space(space_id, nodes, edges)

        binding = "explicit"
        if not space_id:
            if prefer_live and live_space_ids:
                # Prefer non-demo live spaces first, then any live space.
                non_demo = [sid for sid in live_space_ids if sid != DEFAULT_SPACE_ID]
                space_id = non_demo[0] if non_demo else live_space_ids[0]
                binding = "live_spatial_plug"
                seed_demo = False
            elif seed_demo:
                space_id = DEFAULT_SPACE_ID
                binding = "demo_seed_fallback"
            else:
                raise ValueError("space_id is required when seed_demo is false")
        elif prefer_live and space_id not in self.plug.spaces and live_space_ids:
            # Requested space missing but live spaces exist — use live instead of seeding.
            non_demo = [sid for sid in live_space_ids if sid != DEFAULT_SPACE_ID]
            space_id = non_demo[0] if non_demo else live_space_ids[0]
            binding = "live_spatial_plug_redirect"
            seed_demo = False

        if seed_demo and space_id not in self.plug.spaces:
            self.ensure_demo_space(space_id)
            binding = "demo_seed_fallback"

        if space_id not in self.plug.spaces:
            raise ValueError(f"Space '{space_id}' has not been built yet.")

        if not observer:
            nodes_map = self.plug.spaces[space_id]["nodes"]
            if DEMO_OBSERVER in nodes_map:
                observer = DEMO_OBSERVER
            elif seed_demo:
                raise ValueError("observer is required")
            else:
                raise ValueError("observer is required")

        targets = _normalize_targets(args.get("targets") or args.get("to"))
        if not targets:
            targets = _default_targets(self.plug, space_id, observer)

        visible: list[dict[str, Any]] = []
        occluded: list[dict[str, Any]] = []
        for target in targets:
            if not _target_active_at_tick(self.plug, space_id, target, tick):
                occluded.append(
                    {
                        "id": target,
                        "visible": False,
                        "reason": f"target inactive at tick {tick}",
                        "blocked_by": ["temporal_gate"],
                        "distance": None,
                    }
                )
                continue
            sight = self.plug.visibility(space_id, observer, target, line_of_sight=True)
            entry = {
                "id": target,
                "visible": bool(sight.get("visible")),
                "reason": sight.get("reason") or "",
                "blocked_by": list(sight.get("blocked_by") or []),
                "distance": sight.get("distance"),
                "path": list(sight.get("path") or []),
            }
            if entry["visible"]:
                visible.append(entry)
            else:
                occluded.append(entry)

        depth_order = sorted(
            [item for item in visible if isinstance(item.get("distance"), (int, float))],
            key=lambda item: float(item["distance"]),
        )
        depth_ids = [item["id"] for item in depth_order] + [
            item["id"] for item in visible if item["id"] not in {row["id"] for row in depth_order}
        ]

        include_layout = _coerce_bool(args.get("include_layout"), default=True)
        frame = {
            "type": "holo_rt4d_spatial_vision",
            "engine": ENGINE_VERSION,
            "module_id": MODULE_ID,
            "space_id": space_id,
            "observer": observer,
            "tick": tick,
            "target_count": len(targets),
            "visible_count": len(visible),
            "occluded_count": len(occluded),
            "visible": visible,
            "occluded": occluded,
            "depth_order": depth_ids,
            "space_binding": binding,
            "live_space_count": len(live_space_ids),
            "summary": (
                f"HoloRT4D probe at tick {tick}: {len(visible)} visible, "
                f"{len(occluded)} occluded from '{observer}' in '{space_id}' "
                f"(binding={binding})."
            ),
            "console_path": (
                f"/holo-rt4d?space_id={space_id}&observer={observer}&tick={tick}"
            ),
        }
        if include_layout:
            frame["layout"] = self.build_layout(space_id, tick=tick)
            frame["view_model"] = build_spatial_vision_view_model(frame)
        return frame

    def build_layout(self, space_id: str, *, tick: int = 0) -> dict[str, Any]:
        """Export node/edge/entity coordinates for the operator map surface."""
        normalized = " ".join(str(space_id or "").split()).strip()
        if not normalized or normalized not in self.plug.spaces:
            raise ValueError(f"Space '{space_id}' has not been built yet.")
        space = self.plug.spaces[normalized]
        nodes = []
        for node_id, attrs in space["nodes"].items():
            payload = dict(attrs or {})
            kind = "obstacle" if payload.get("type") == "obstacle" else "node"
            nodes.append(
                {
                    "id": node_id,
                    "x": float(payload.get("x", 0) or 0),
                    "y": float(payload.get("y", 0) or 0),
                    "z": float(payload.get("z", 0) or 0),
                    "kind": kind,
                    "name": str(payload.get("name") or node_id),
                }
            )
        edges = []
        for edge in space.get("edges") or []:
            edges.append(
                {
                    "from": edge.get("from"),
                    "to": edge.get("to"),
                    "weight": edge.get("weight"),
                    "obstacle": bool(edge.get("obstacle")),
                    "name": edge.get("name"),
                }
            )
        entities = []
        for entity_id, entity in self.plug.entities.items():
            if entity.get("space") != normalized:
                continue
            host = space["nodes"].get(entity.get("node") or "", {})
            active_ticks = entity.get("active_ticks")
            active = True
            if isinstance(active_ticks, (list, tuple, set)):
                active = tick in {int(item) for item in active_ticks}
            entities.append(
                {
                    "id": entity_id,
                    "node": entity.get("node"),
                    "x": float(host.get("x", 0) or 0),
                    "y": float(host.get("y", 0) or 0),
                    "z": float(host.get("z", 0) or 0),
                    "role": entity.get("role") or "entity",
                    "active_ticks": list(active_ticks or []) if active_ticks is not None else None,
                    "active": active,
                }
            )
        return {
            "space_id": normalized,
            "tick": tick,
            "nodes": nodes,
            "edges": edges,
            "entities": entities,
            "bounds": _layout_bounds(nodes + entities),
        }


def probe_spatial_vision(
    payload: dict[str, Any] | None = None,
    *,
    plug: SpatialReasoningPlug | None = None,
) -> dict[str, Any]:
    """Module-level helper for API / capability adapters."""
    return HoloRuntime4dSpatialVisionEngine(plug=plug).probe(payload)


def build_spatial_vision_view_model(frame: dict[str, Any] | None) -> dict[str, Any]:
    """Project a probe frame into SVG-friendly map geometry for the console surface."""
    payload = dict(frame or {})
    layout = dict(payload.get("layout") or {})
    nodes = list(layout.get("nodes") or [])
    entities = list(layout.get("entities") or [])
    edges = list(layout.get("edges") or [])
    bounds = dict(layout.get("bounds") or _layout_bounds(nodes + entities))
    visible_ids = {str(item.get("id")) for item in (payload.get("visible") or []) if item}
    occluded_ids = {str(item.get("id")) for item in (payload.get("occluded") or []) if item}
    observer_id = str(payload.get("observer") or "")
    sight_by_id = {
        str(item.get("id")): item
        for item in list(payload.get("visible") or []) + list(payload.get("occluded") or [])
        if isinstance(item, dict) and item.get("id")
    }

    projected_nodes = [
        {
            **node,
            "sx": _project_axis(node.get("x"), bounds, "x"),
            "sy": _project_axis(node.get("y"), bounds, "y", invert=True),
            "state": _node_state(str(node.get("id")), observer_id, visible_ids, occluded_ids, node.get("kind")),
        }
        for node in nodes
    ]
    projected_entities = [
        {
            **entity,
            "sx": _project_axis(entity.get("x"), bounds, "x"),
            "sy": _project_axis(entity.get("y"), bounds, "y", invert=True),
            "state": (
                "inactive"
                if not entity.get("active", True)
                else _node_state(str(entity.get("id")), observer_id, visible_ids, occluded_ids, "entity")
            ),
        }
        for entity in entities
    ]
    position_index = {
        str(item["id"]): item for item in projected_nodes + projected_entities if item.get("id")
    }
    observer_point = position_index.get(observer_id)
    rays = []
    for target_id, sight in sight_by_id.items():
        target_point = position_index.get(target_id)
        if not observer_point or not target_point:
            continue
        rays.append(
            {
                "id": target_id,
                "visible": bool(sight.get("visible")),
                "x1": observer_point["sx"],
                "y1": observer_point["sy"],
                "x2": target_point["sx"],
                "y2": target_point["sy"],
                "distance": sight.get("distance"),
                "blocked_by": list(sight.get("blocked_by") or []),
                "path": list(sight.get("path") or []),
            }
        )
    projected_edges = []
    for edge in edges:
        source = position_index.get(str(edge.get("from") or ""))
        target = position_index.get(str(edge.get("to") or ""))
        if not source or not target:
            continue
        projected_edges.append(
            {
                "from": edge.get("from"),
                "to": edge.get("to"),
                "obstacle": bool(edge.get("obstacle")),
                "x1": source["sx"],
                "y1": source["sy"],
                "x2": target["sx"],
                "y2": target["sy"],
            }
        )
    cone = _visibility_cone(observer_point, [ray for ray in rays if ray.get("visible")])
    return {
        "view_box": "0 0 100 100",
        "bounds": bounds,
        "nodes": projected_nodes,
        "entities": projected_entities,
        "edges": projected_edges,
        "rays": rays,
        "cone": cone,
        "observer": observer_point,
        "visible_count": int(payload.get("visible_count") or len(visible_ids)),
        "occluded_count": int(payload.get("occluded_count") or len(occluded_ids)),
        "tick": payload.get("tick", 0),
        "space_id": payload.get("space_id"),
        "summary": payload.get("summary") or "",
    }


def _layout_bounds(points: list[dict[str, Any]]) -> dict[str, float]:
    if not points:
        return {"min_x": -1.0, "max_x": 1.0, "min_y": -1.0, "max_y": 1.0}
    xs = [float(point.get("x", 0) or 0) for point in points]
    ys = [float(point.get("y", 0) or 0) for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if abs(max_x - min_x) < 1e-6:
        min_x -= 1.0
        max_x += 1.0
    if abs(max_y - min_y) < 1e-6:
        min_y -= 1.0
        max_y += 1.0
    pad_x = (max_x - min_x) * 0.18
    pad_y = (max_y - min_y) * 0.18
    return {
        "min_x": min_x - pad_x,
        "max_x": max_x + pad_x,
        "min_y": min_y - pad_y,
        "max_y": max_y + pad_y,
    }


def _project_axis(
    value: Any,
    bounds: dict[str, float],
    axis: str,
    *,
    invert: bool = False,
) -> float:
    raw = float(value or 0)
    low = float(bounds.get(f"min_{axis}", -1.0))
    high = float(bounds.get(f"max_{axis}", 1.0))
    span = high - low or 1.0
    normalized = (raw - low) / span
    if invert:
        normalized = 1.0 - normalized
    return round(8.0 + normalized * 84.0, 3)


def _node_state(
    node_id: str,
    observer_id: str,
    visible_ids: set[str],
    occluded_ids: set[str],
    kind: Any,
) -> str:
    if kind == "obstacle":
        return "obstacle"
    if node_id == observer_id:
        return "observer"
    if node_id in visible_ids:
        return "visible"
    if node_id in occluded_ids:
        return "occluded"
    return "neutral"


def _visibility_cone(
    observer_point: dict[str, Any] | None,
    visible_rays: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not observer_point or not visible_rays:
        return None
    points = [f"{observer_point['sx']},{observer_point['sy']}"]
    for ray in visible_rays:
        points.append(f"{ray['x2']},{ray['y2']}")
    if len(points) < 3:
        # Degenerate cone — still draw a soft wedge toward the only target.
        points.append(f"{observer_point['sx']},{observer_point['sy']}")
    return {
        "points": " ".join(points),
        "target_count": len(visible_rays),
    }


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = " ".join(str(value).split()).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("tick must be an integer") from exc


def _normalize_targets(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("\n", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        return [
            text
            for text in (" ".join(str(item or "").split()).strip() for item in value)
            if text
        ]
    text = " ".join(str(value).split()).strip()
    return [text] if text else []


def _default_targets(
    plug: SpatialReasoningPlug,
    space_id: str,
    observer: str,
) -> list[str]:
    space = plug.spaces[space_id]
    node_ids = [
        node_id
        for node_id in space["nodes"]
        if node_id != observer and (space["nodes"][node_id].get("type") != "obstacle")
    ]
    entity_ids = [
        entity_id
        for entity_id, entity in plug.entities.items()
        if entity.get("space") == space_id and entity.get("node") != observer
    ]
    # Prefer placed entities; fall back to non-obstacle nodes.
    ordered = list(dict.fromkeys([*entity_ids, *node_ids]))
    return ordered


def _target_active_at_tick(
    plug: SpatialReasoningPlug,
    space_id: str,
    target: str,
    tick: int,
) -> bool:
    entity = plug.entities.get(target)
    if not entity or entity.get("space") != space_id:
        return True
    active_ticks = entity.get("active_ticks")
    if active_ticks is None:
        return True
    if isinstance(active_ticks, (list, tuple, set)):
        return tick in {int(item) for item in active_ticks}
    return True
