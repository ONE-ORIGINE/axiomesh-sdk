from __future__ import annotations

import math
from dataclasses import dataclass

from edp_core import (
    Action,
    ActionCategory,
    ContextKind,
    Element,
    Environment,
    EnvironmentKind,
    MissionObjective,
    MultiAgentCoordinator,
    ReactionRecord,
    RuleMode,
    SenseVector,
    TaskSpec,
)
from savoir_core import Evidence, KnowledgeBase, KnowledgeConstraint, KnowledgePolicy, SharedKnowledgeMesh


@dataclass(slots=True)
class DronePhysicalState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    yaw: float = 0.0
    battery: float = 100.0
    gps_lock: bool = True
    airborne: bool = False
    wind_speed: float = 0.0


class Drone(Element):
    def __init__(self, name: str, drone_id: str):
        super().__init__(name, "drone", sense=SenseVector.spatial(f"drone:{name}", 0.82))
        self.drone_id = drone_id
        self.physical = DronePhysicalState()
        self.set_static("drone_id", drone_id)
        self.set_static("role", "pilot")
        self.set_dynamic("battery", self.physical.battery)
        self.set_dynamic("gps_lock", self.physical.gps_lock)
        self.set_dynamic("airborne", self.physical.airborne)
        self.set_dynamic("wind_speed", self.physical.wind_speed)
        self.sync_physical_state()

    def sync_physical_state(self) -> None:
        self.physical_state.update({
            "x": self.physical.x,
            "y": self.physical.y,
            "z": self.physical.z,
            "vx": self.physical.vx,
            "vy": self.physical.vy,
            "vz": self.physical.vz,
            "yaw": self.physical.yaw,
            "battery": self.physical.battery,
            "gps_lock": float(self.physical.gps_lock),
            "airborne": float(self.physical.airborne),
            "wind_speed": self.physical.wind_speed,
        })
        for dim in ["x", "y", "z", "battery", "vx", "vy", "vz", "yaw"]:
            self.knowledge_state[f"{dim}_certainty"] = 1.0 if dim in {"x", "y", "z", "battery"} else 0.8
            self.knowledge_state[f"{dim}_quality"] = 1.0

    async def on_impacted(self, reaction: ReactionRecord, request, ctx) -> None:
        if not reaction.ok:
            return
        if reaction.action_type == "drone.takeoff":
            self.physical.airborne = True
            self.physical.z = float(request.payload.get("altitude", 5.0))
            self.physical.battery = max(0.0, self.physical.battery - 2.0)
        elif reaction.action_type == "drone.move":
            self.physical.x += float(request.payload.get("dx", 0.0))
            self.physical.y += float(request.payload.get("dy", 0.0))
            self.physical.z += float(request.payload.get("dz", 0.0))
            self.physical.battery = max(0.0, self.physical.battery - 0.5)
        elif reaction.action_type == "drone.land":
            self.physical.airborne = False
            self.physical.z = 0.0
            self.physical.battery = max(0.0, self.physical.battery - 0.5)
        elif reaction.action_type == "drone.goto":
            self.physical.x = float(request.payload.get("x", self.physical.x))
            self.physical.y = float(request.payload.get("y", self.physical.y))
            self.physical.z = float(request.payload.get("z", self.physical.z))
            self.physical.battery = max(0.0, self.physical.battery - 0.8)
        self.set_dynamic("battery", self.physical.battery)
        self.set_dynamic("gps_lock", self.physical.gps_lock)
        self.set_dynamic("airborne", self.physical.airborne)
        self.set_dynamic("wind_speed", self.physical.wind_speed)
        self.sync_physical_state()

    def sensor_update(self, x: float, y: float, z: float, battery: float, gps_lock: bool, wind_speed: float | None = None) -> None:
        self.physical.x = x
        self.physical.y = y
        self.physical.z = z
        self.physical.battery = battery
        self.physical.gps_lock = gps_lock
        if wind_speed is not None:
            self.physical.wind_speed = wind_speed
        self.set_dynamic("battery", battery)
        self.set_dynamic("gps_lock", gps_lock)
        self.set_dynamic("wind_speed", self.physical.wind_speed)
        self.sync_physical_state()


class DroneSubsystem(Element):
    def __init__(self, name: str, role: str, parent: Drone):
        super().__init__(name, "drone_subsystem", sense=SenseVector.technical(f"{role}:{name}", 0.78))
        self.parent = parent
        self.set_static("role", role)
        self.set_static("parent_agent_id", parent.element_id)
        self.set_static("drone_id", parent.drone_id)
        self.set_dynamic("battery", parent.physical.battery)
        self.set_dynamic("gps_lock", parent.physical.gps_lock)
        self.set_dynamic("airborne", parent.physical.airborne)
        self.set_dynamic("wind_speed", parent.physical.wind_speed)
        self.physical_state.update({"x": parent.physical.x, "y": parent.physical.y, "z": parent.physical.z, "battery": parent.physical.battery})
        for dim in ["x", "y", "z", "battery"]:
            self.knowledge_state[f"{dim}_certainty"] = 0.9
            self.knowledge_state[f"{dim}_quality"] = 0.9

    def sync_from_parent(self) -> None:
        self.set_dynamic("battery", self.parent.physical.battery)
        self.set_dynamic("gps_lock", self.parent.physical.gps_lock)
        self.set_dynamic("airborne", self.parent.physical.airborne)
        self.set_dynamic("wind_speed", self.parent.physical.wind_speed)
        self.physical_state.update({"x": self.parent.physical.x, "y": self.parent.physical.y, "z": self.parent.physical.z, "battery": self.parent.physical.battery})

    async def on_tick(self, tick: int) -> None:
        self.sync_from_parent()

    async def on_impacted(self, reaction: ReactionRecord, request, ctx) -> None:
        self.sync_from_parent()


class SwarmKnowledge:
    def __init__(self, drones: list[Drone]):
        self.kb = KnowledgeBase()
        self.mesh = SharedKnowledgeMesh(shared=self.kb)
        policy = KnowledgePolicy(prefix="drone_", default_ttl_ms=120000, decay_rate=0.995, source_bias={"lidar": 1.1, "gps": 1.0, "imu": 0.9, "baro": 0.95, "sensor": 1.0}, contradiction_threshold=0.5)
        self.mesh.register_policy(policy)
        self.drones = {drone.drone_id: drone for drone in drones}
        for drone_id in self.drones:
            self.kb.add_constraint(KnowledgeConstraint(constraint_id=f"{drone_id}.battery.safe", key=f"{drone_id}.battery", comparator=">=", target=15.0, weight=0.02, description="Battery must stay above mission reserve"))

    def sync(self) -> None:
        for drone_id, drone in self.drones.items():
            self.mesh.observe(drone_id, f"{drone_id}.x", drone.physical.x, source="gps", share=True)
            self.mesh.observe(drone_id, f"{drone_id}.y", drone.physical.y, source="gps", share=True)
            self.mesh.observe(drone_id, f"{drone_id}.z", drone.physical.z, source="baro", share=True)
            self.mesh.observe(drone_id, f"{drone_id}.battery", drone.physical.battery, source="sensor", share=True)
            self.mesh.expect(drone_id, f"{drone_id}.battery", drone.physical.battery, share=True)
            self.mesh.expect(drone_id, f"{drone_id}.z", drone.physical.z, share=True)

    def revise_position(self, drone_id: str, gps_xyz: tuple[float, float, float], lidar_xyz: tuple[float, float, float]) -> None:
        observations_x = [Evidence(source="gps", value=gps_xyz[0], weight=1.0, freshness=1.0), Evidence(source="lidar", value=lidar_xyz[0], weight=1.1, freshness=0.95)]
        observations_y = [Evidence(source="gps", value=gps_xyz[1], weight=1.0, freshness=1.0), Evidence(source="lidar", value=lidar_xyz[1], weight=1.1, freshness=0.95)]
        observations_z = [Evidence(source="baro", value=gps_xyz[2], weight=0.9, freshness=1.0), Evidence(source="lidar", value=lidar_xyz[2], weight=1.1, freshness=0.95)]
        self.mesh.revise_numeric(drone_id, f"{drone_id}.x", observations_x, share=True)
        self.mesh.revise_numeric(drone_id, f"{drone_id}.y", observations_y, share=True)
        self.mesh.revise_numeric(drone_id, f"{drone_id}.z", observations_z, share=True)



    def connect_neighbors_by_distance(self, radius: float = 12.0) -> None:
        ids = list(self.drones)
        for i, left_id in enumerate(ids):
            left = self.drones[left_id]
            for right_id in ids[i + 1:]:
                right = self.drones[right_id]
                dist = math.sqrt((left.physical.x - right.physical.x) ** 2 + (left.physical.y - right.physical.y) ** 2 + (left.physical.z - right.physical.z) ** 2)
                if dist <= radius:
                    self.mesh.connect(left_id, right_id, channel="proximity", relation="swarm-neighbor", max_hops=1)

    def publish_neighbors(self) -> None:
        for drone_id in self.drones:
            for suffix in ('x', 'y', 'z', 'battery'):
                self.mesh.publish_to_neighbors(drone_id, f"{drone_id}.{suffix}")

    def formation_tasks(self) -> list[TaskSpec]:
        ordered = sorted(self.drones.values(), key=lambda drone: drone.name)
        tasks: list[TaskSpec] = []
        for idx, drone in enumerate(ordered):
            depends = [f"{ordered[idx-1].drone_id}.hold" ] if idx > 0 else []
            tasks.append(TaskSpec(
                task_id=f"{drone.drone_id}.hold",
                description=f"Hold formation slot for {drone.name}",
                goal_dimension='spatial',
                goal_meaning='hold formation',
                goal_magnitude=0.88,
                required_roles=['pilot'],
                preferred_contexts=['Flight', 'Navigation'],
                target_agent_ids=[drone.element_id],
                depends_on=depends,
                channel='swarm',
            ))
        tasks.append(TaskSpec(
            task_id='swarm.scan',
            description='Run distributed perception sweep',
            goal_dimension='technical',
            goal_meaning='distributed scan',
            goal_magnitude=0.9,
            required_roles=['perception'],
            preferred_contexts=['InnerPerception'],
            depends_on=[f"{ordered[-1].drone_id}.hold"] if ordered else [],
            channel='internal',
        ))
        return tasks


    def mission_objectives(self, drone_id: str) -> list[MissionObjective]:
        return [
            MissionObjective(objective_id=f"{drone_id}.stabilize", description="Stay in valid flight envelope", target_sense=SenseVector.spatial("stable flight", 0.8), priority=10, success_threshold=0.3, preferred_contexts=["Flight"]),
            MissionObjective(objective_id=f"{drone_id}.navigate", description="Reach waypoint efficiently", target_sense=SenseVector.temporal("reach waypoint", 0.95), priority=20, success_threshold=0.15, preferred_contexts=["Navigation", "Flight"]),
        ]

    def formation_objective(self) -> SenseVector:
        return SenseVector.spatial("maintain swarm formation", 0.88)

    def shared_summary(self) -> str:
        snapshot = self.mesh.shared_snapshot("drone_")
        return f"shared_facts={len(snapshot['facts'])} tension={snapshot['tension']:.4f} revalidation={len(snapshot['revalidation'])}"

    def summary(self) -> str:
        self.sync()
        lines = ["SWARM KNOWLEDGE", ""]
        for drone_id, drone in self.drones.items():
            view = self.mesh.agent_view(drone_id, prefix="drone_")
            lines.append(
                f"{drone.name:<10} pos=({drone.physical.x:.1f},{drone.physical.y:.1f},{drone.physical.z:.1f}) "
                f"battery={drone.physical.battery:.0f}% local_tension={view.local_tension:.2f} shared_tension={view.shared_tension:.2f}"
            )
        lines.append("")
        lines.append(self.shared_summary())
        return "\n".join(lines)


class DroneSwarmEnvironment(Environment):
    def __init__(self, drones: list[Drone]):
        super().__init__("DroneSwarm", EnvironmentKind.LIVING)
        self.drones = {drone.element_id: drone for drone in drones}
        self.coordinator = MultiAgentCoordinator(self)
        self.coordinator.ensure_channel("swarm", role="shared-airspace")
        self.coordinator.ensure_channel("internal", role="subsystems")
        self.preflight = self.create_context("PreFlight", ContextKind.GOVERNANCE, SenseVector.normative("preflight", 0.9))
        self.flight = self.create_context("Flight", ContextKind.SPATIAL, SenseVector.spatial("flight", 0.95))
        self.navigation = self.create_context("Navigation", ContextKind.TEMPORAL, SenseVector.temporal("navigation", 0.9), parent=self.flight)
        self.emergency = self.create_context("Emergency", ContextKind.CAUSAL, SenseVector.causal("emergency", 1.0), parent=self.flight)
        self.inner_navigation = self.create_context("InnerNavigation", ContextKind.OBSERVATION, SenseVector.technical("inner-navigation", 0.86), parent=self.navigation)
        self.inner_safety = self.create_context("InnerSafety", ContextKind.CAUSAL, SenseVector.causal("inner-safety", 0.98), parent=self.emergency)
        self.inner_perception = self.create_context("InnerPerception", ContextKind.OBSERVATION, SenseVector.technical("inner-perception", 0.9), parent=self.flight)
        self._install_rules()
        self._install_actions()

    def build_internal_agents(self, drone: Drone) -> list[DroneSubsystem]:
        return [
            DroneSubsystem(f"{drone.name}-NAV", "navigator", drone),
            DroneSubsystem(f"{drone.name}-SAFE", "safety", drone),
            DroneSubsystem(f"{drone.name}-SENSE", "perception", drone),
        ]

    async def admit(self, element: Element) -> None:
        await super().admit(element)
        if isinstance(element, Drone):
            self.coordinator.add_member("swarm", element)
        if isinstance(element, DroneSubsystem):
            self.coordinator.add_member("internal", element)
            self.coordinator.add_member(f"parent:{element.parent.element_id}", element)
        self.coordinator.auto_register()

    def _install_rules(self) -> None:
        self.preflight.when_expr("on.ground", "Drone on ground", "not airborne", priority=10)
        self.flight.when_expr("battery.safe", "Battery > 15%", "battery > 15", priority=10)
        self.flight.when_expr("gps.lock", "GPS lock active", "gps_lock == True", priority=11)
        self.flight.when_expr("is.airborne", "Drone is airborne", "airborne == True", priority=12)
        self.flight.when_expr("role.pilot", "Pilot role in outer flight", "role == 'pilot' or role == 'safety'", priority=13)
        self.flight.when_expr("wind.moderate", "Wind under safe cruise threshold", "wind_speed < 12", mode=RuleMode.SOFT, priority=30, penalty=0.15)
        self.navigation.when_expr("battery.safe", "Battery > 15%", "battery > 15", priority=10)
        self.navigation.when_expr("gps.lock", "GPS lock active", "gps_lock == True", priority=11)
        self.navigation.when_expr("is.airborne", "Drone is airborne", "airborne == True", priority=12)
        self.navigation.when_expr("role.nav", "Navigation allowed for pilot or navigator", "role == 'pilot' or role == 'navigator'", priority=13)
        self.navigation.when_expr("wind.nav", "Wind under navigation threshold", "wind_speed < 10", mode=RuleMode.SOFT, priority=20, penalty=0.2)
        self.emergency.when_expr("always", "Emergency context always available", "True", priority=1)
        self.inner_navigation.when_expr("role.navigator", "Only navigator role in inner navigation", "role == 'navigator'", priority=5)
        self.inner_navigation.when_expr("gps.lock", "GPS lock active", "gps_lock == True", priority=6)
        self.inner_safety.when_expr("role.safety", "Only safety role in safety context", "role == 'safety'", priority=5)
        self.inner_perception.when_expr("role.perception", "Only perception role in perception context", "role == 'perception'", priority=5)

    def _install_actions(self) -> None:
        async def takeoff(actor: Drone, request, ctx):
            altitude = float(request.payload.get("altitude", 5.0))
            if actor.physical.airborne:
                return ReactionRecord("drone.takeoff", ok=False, message="Already airborne")
            return ReactionRecord("drone.takeoff", ok=True, message=f"Takeoff to {altitude:.1f}m", result={"altitude": altitude}, sense=SenseVector.spatial("takeoff", 0.8))

        async def move(actor: Drone, request, ctx):
            if request.payload.get('force_fail'):
                return ReactionRecord("drone.move", ok=False, message="Forced move failure", sense=SenseVector.spatial("move-fail", 0.3))
            dx = float(request.payload.get("dx", 0.0))
            dy = float(request.payload.get("dy", 0.0))
            dz = float(request.payload.get("dz", 0.0))
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            return ReactionRecord("drone.move", ok=True, message=f"Move by ({dx:.1f},{dy:.1f},{dz:.1f}) dist={dist:.1f}", result={"distance": round(dist, 2)}, sense=SenseVector.spatial("move", 0.9))

        async def land(actor: Drone, request, ctx):
            return ReactionRecord("drone.land", ok=True, message="Landing", sense=SenseVector.spatial("land", 0.7))

        async def goto(actor: Drone, request, ctx):
            x = float(request.payload.get("x", actor.physical.x))
            y = float(request.payload.get("y", actor.physical.y))
            z = float(request.payload.get("z", actor.physical.z))
            return ReactionRecord("drone.goto", ok=True, message=f"Navigate to ({x:.1f},{y:.1f},{z:.1f})", result={"target": (x, y, z)}, sense=SenseVector.temporal("goto", 0.95))

        async def rth(actor: Drone, request, ctx):
            return ReactionRecord("drone.rth", ok=True, message="Return to home", sense=SenseVector.causal("return-home", 1.0))

        async def solve_path(actor: DroneSubsystem, request, ctx):
            target = tuple(request.payload.get(k, actor.parent.physical_state.get(k, 0.0)) for k in ("x", "y", "z"))
            return ReactionRecord("inner.nav.solve", ok=True, message=f"Solve path to {target}", result={"target": target}, sense=SenseVector.technical("path-solve", 0.9))

        async def safety_override(actor: DroneSubsystem, request, ctx):
            return ReactionRecord("inner.safety.override", ok=True, message="Safety override evaluated", result={"mode": request.payload.get("mode", "hold")}, sense=SenseVector.causal("safety-override", 1.0))

        async def fuse_scan(actor: DroneSubsystem, request, ctx):
            return ReactionRecord("inner.perception.fuse", ok=True, message="Sensor fusion completed", result={"sources": request.payload.get("sources", ["gps", "lidar"])}, sense=SenseVector.technical("sensor-fusion", 0.92))

        takeoff_action = Action("drone.takeoff", ActionCategory.COMMAND, "Take off", SenseVector.spatial("takeoff", 0.85), handler=takeoff, cost=0.05)
        move_action = Action("drone.move", ActionCategory.COMMAND, "Relative move", SenseVector.spatial("move", 0.95), handler=move, cost=0.1)
        land_action = Action("drone.land", ActionCategory.COMMAND, "Land", SenseVector.spatial("land", 0.7), handler=land, cost=0.02)
        goto_action = Action("drone.goto", ActionCategory.COMMAND, "Go to waypoint", SenseVector.temporal("goto", 0.95), handler=goto, cost=0.12)
        rth_action = Action("drone.rth", ActionCategory.SIGNAL, "Return home now", SenseVector.causal("return-home", 1.0), handler=rth, cost=0.01)
        solve_action = Action("inner.nav.solve", ActionCategory.QUERY, "Solve path internally", SenseVector.technical("path-solve", 0.92), handler=solve_path, cost=0.03)
        safety_action = Action("inner.safety.override", ActionCategory.SIGNAL, "Evaluate safety override", SenseVector.causal("safety-override", 1.0), handler=safety_override, cost=0.01)
        fuse_action = Action("inner.perception.fuse", ActionCategory.QUERY, "Fuse sensor observations", SenseVector.technical("sensor-fusion", 0.94), handler=fuse_scan, cost=0.02)

        self.preflight.add_action(takeoff_action)
        self.flight.add_action(move_action).add_action(land_action).add_action(rth_action)
        self.navigation.add_action(move_action).add_action(land_action).add_action(goto_action).add_action(rth_action)
        self.emergency.add_action(rth_action).add_action(land_action)
        self.inner_navigation.add_action(solve_action)
        self.inner_safety.add_action(safety_action)
        self.inner_perception.add_action(fuse_action)


    def mixed_bindings(self) -> list:
        bindings = []
        for actor in self.elements.values():
            role = str(actor.static_properties.get('role', actor.dynamic_properties.get('role', actor.element_type)))
            parent = str(actor.static_properties.get('parent_agent_id', ''))
            if actor.element_type == 'drone':
                bindings.append(self.coordinator.binding_for(actor, 'Flight', channel='swarm'))
            elif role == 'navigator':
                bindings.append(self.coordinator.binding_for(actor, 'InnerNavigation', channel='internal'))
            elif role == 'safety':
                bindings.append(self.coordinator.binding_for(actor, 'InnerSafety', channel='internal'))
            elif role == 'perception':
                bindings.append(self.coordinator.binding_for(actor, 'InnerPerception', channel='internal'))
        return bindings
