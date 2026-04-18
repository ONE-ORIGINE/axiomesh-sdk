from __future__ import annotations

import asyncio

from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer

from .model import Drone, DroneSwarmEnvironment, SwarmKnowledge


async def main() -> None:
    drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
    env = DroneSwarmEnvironment(drones)
    swarm = SwarmKnowledge(drones)
    internal = []
    for drone in drones:
        await env.admit(drone)
        internal.extend(env.build_internal_agents(drone))
    for agent in internal:
        await env.admit(agent)
    drones[0].sensor_update(0.0, 0.0, 0.0, 100.0, True, wind_speed=3.0)
    drones[1].sensor_update(6.0, 0.0, 0.0, 94.0, True, wind_speed=4.0)
    for drone in drones:
        drone.physical.airborne = True
        drone.set_dynamic("airborne", True)
        drone.sync_physical_state()
    swarm.sync()
    swarm.connect_neighbors_by_distance(radius=10.0)
    swarm.publish_neighbors()

    gateway = MEPGateway(env, swarm.kb, mesh=swarm.mesh, coordinator=env.coordinator)
    hub = FederatedMEPHub()
    env_a = hub.register("drone-swarm", gateway, tags=["swarm", "drone"])

    reserve = [Drone("GAMMA", "drone_2")]
    env2 = DroneSwarmEnvironment(reserve)
    swarm2 = SwarmKnowledge(reserve)
    for drone in reserve:
        await env2.admit(drone)
        drone.sensor_update(12.0, 0.0, 2.0, 88.0, True, wind_speed=2.0)
        drone.physical.airborne = True
        drone.set_dynamic("airborne", True)
        drone.sync_physical_state()
    swarm2.sync()
    gateway2 = MEPGateway(env2, swarm2.kb, mesh=swarm2.mesh, coordinator=env2.coordinator)
    env_b = hub.register("reserve-swarm", gateway2, tags=["reserve", "drone"])
    server = MEPJsonRpcServer(gateway, hub=hub)

    handshake = await server.handle(JsonRpcRequest(method="mep.handshake", params={"client_id": "demo"}, id=1))
    print("HANDSHAKE", handshake.to_dict()["result"]["body"]["environment"]["version"])
    spec = await server.handle(JsonRpcRequest(method="mep.spec", params={}, id=1001))
    print("SPEC_METHODS", spec.to_dict()["result"]["method_count"])
    health = await server.handle(JsonRpcRequest(method="mep.health", params={}, id=1002))
    print("HEALTH_EVENTS", health.to_dict()["result"]["counts"]["events"], "PROV_OK", health.to_dict()["result"]["provenance"]["ok"])
    fault = await server.handle(JsonRpcRequest(method="mep.fault.inject", params={"scope": "task", "target": swarm.formation_tasks()[0].task_id, "count": 1, "message": "simulated motor jitter"}, id=1003))
    print("FAULT_INJECTED", fault.to_dict()["result"]["scope"], fault.to_dict()["result"]["target"])

    bindings = env.mixed_bindings()
    alloc = await server.handle(JsonRpcRequest(method="mep.multi.assign", params={
        "bindings": [binding.to_dict() for binding in bindings],
        "tasks": [task.to_dict() for task in swarm.formation_tasks()],
        "neighborhood_radius": 10.0,
    }, id=2), actor=drones[0], context=env.flight)
    alloc_result = alloc.to_dict()["result"]
    print("ASSIGNMENTS", len(alloc_result["assignments"]), "LAYERS", alloc_result["dependency_layers"])

    neighborhood = await server.handle(JsonRpcRequest(method="mep.neighborhood", params={"knowledge_prefix": "drone_"}, id=3), actor=drones[0], context=env.flight)
    neighborhood_result = neighborhood.to_dict()["result"]
    print("NEIGHBORS", neighborhood_result["neighbors"], "VISIBLE", len(neighborhood_result["visible_facts"]))

    multi_context = await server.handle(JsonRpcRequest(method="mep.multi.context.plan", params={
        "goal": {"dimension": "technical", "meaning": "coordinated mission", "magnitude": 0.84},
        "bindings": [binding.to_dict() for binding in bindings],
    }, id=4), actor=drones[0], context=env.flight)
    print("MULTI_CONTEXT_ITEMS", len(multi_context.to_dict()["result"]["items"]))


    negotiation = await server.handle(JsonRpcRequest(method="mep.multi.negotiate", params={
        "bindings": [binding.to_dict() for binding in bindings],
        "task": swarm.formation_tasks()[0].to_dict(),
    }, id=5), actor=drones[0], context=env.flight)
    print("NEGOTIATION_BIDS", len(negotiation.to_dict()["result"]["bids"]))

    execute = await server.handle(JsonRpcRequest(method="mep.multi.execute", params={
        "bindings": [binding.to_dict() for binding in bindings],
        "tasks": [task.to_dict() for task in swarm.formation_tasks()],
        "initiator": "demo-controller",
        "recovery_policy": "retry_once",
    }, id=6), actor=drones[0], context=env.flight)
    print("EXECUTED", len(execute.to_dict()["result"]["executed"]), "CAUSAL", len(execute.to_dict()["result"]["causal_links"]), "ROLLBACK", execute.to_dict()["result"]["rollback_policy"], "RECOVERED", execute.to_dict()["result"]["recovered_task_ids"])

    causal = await server.handle(JsonRpcRequest(method="mep.causal.trace", params={"limit": 10}, id=7), actor=drones[0], context=env.flight)
    print("CAUSAL_TRACE", len(causal.to_dict()["result"]["items"]))

    propagated = await server.handle(JsonRpcRequest(method="mep.knowledge.propagate", params={
        "key": "drone_0.x",
        "channels": ["proximity"],
        "max_hops": 1,
    }, id=8), actor=drones[0], context=env.flight)
    print("PROPAGATED", propagated.to_dict()["result"]["propagated"])

    provenance = await server.handle(JsonRpcRequest(method="mep.provenance.trace", params={"limit": 10}, id=9), actor=drones[0], context=env.flight)
    print("PROVENANCE", len(provenance.to_dict()["result"]["items"]))

    prov_verify = await server.handle(JsonRpcRequest(method="mep.provenance.verify", params={}, id=91), actor=drones[0], context=env.flight)
    print("PROV_VERIFY", prov_verify.to_dict()["result"]["ok"], prov_verify.to_dict()["result"]["count"])

    federation = await server.handle(JsonRpcRequest(method="mep.federation.card", params={}, id=10), actor=drones[0], context=env.flight)
    print("FEDERATION_ENVS", len(federation.to_dict()["result"]["environments"]))

    fed_prov = await server.handle(JsonRpcRequest(method="mep.federation.provenance.verify", params={}, id=101), actor=drones[0], context=env.flight)
    print("FED_PROV_OK", fed_prov.to_dict()["result"]["ok"], len(fed_prov.to_dict()["result"]["reports"]))

    gateway2.inject_fault("route", "mep.multi.execute", count=1, message="reserve link down")
    print("ROUTE_FAULT", "mep.multi.execute")

    routed = await server.handle(JsonRpcRequest(method="mep.federation.route", params={
        "environment_id": env_b,
        "forward_method": "mep.environment.card",
        "forward_params": {},
    }, id=11), actor=drones[0], context=env.flight)
    print("ROUTED", routed.to_dict()["result"]["response"]["result"]["version"])

    priority_task = swarm.formation_tasks()[0]
    priority_task.mission_policy = {"preset": "risk_averse", "load_weight": 3.0, "certainty_weight": 1.8, "locality_weight": 1.4, "risk_weight": 2.0}
    priority_task.preferred_environment_tags = ["reserve"]
    resolved = await server.handle(JsonRpcRequest(method="mep.federation.resolve_task", params={
        "task": priority_task.to_dict(),
        "required_method": "mep.multi.negotiate",
    }, id=12), actor=drones[0], context=env.flight)
    print("FED_TASK_TARGET", resolved.to_dict()["result"]["selected"]["environment_id"])

    routed_task = await server.handle(JsonRpcRequest(method="mep.federation.route_task", params={
        "task": priority_task.to_dict(),
        "required_method": "mep.multi.negotiate",
    }, id=13), actor=drones[0], context=env.flight)
    print("ROUTED_TASK_METHOD", routed_task.to_dict()["result"]["method"])

    spec_schema = await server.handle(JsonRpcRequest(method="mep.spec.schema", params={}, id=1301), actor=drones[0], context=env.flight)
    print("SPEC_SCHEMA_METHODS", len(spec_schema.to_dict()["result"]["methods"]))

    spec_markdown = await server.handle(JsonRpcRequest(method="mep.spec.markdown", params={}, id=1302), actor=drones[0], context=env.flight)
    print("SPEC_MARKDOWN", spec_markdown.to_dict()["result"]["markdown"].splitlines()[0])

    describe_alias = await server.handle(JsonRpcRequest(method="mep.method.describe", params={"method": "mep.capabilities"}, id=1303), actor=drones[0], context=env.flight)
    print("DESCRIBE_ALIAS", describe_alias.to_dict()["result"]["canonical_method"])

    resolved_alias = await server.handle(JsonRpcRequest(method="mep.capabilities", params={}, id=1304), actor=drones[0], context=env.flight)
    print("ALIAS_ENV_CARD", resolved_alias.to_dict()["result"]["version"])

    resolved_plan = await server.handle(JsonRpcRequest(method="mep.federation.resolve_plan", params={
        "tasks": [task.to_dict() for task in swarm.formation_tasks()],
    }, id=14), actor=drones[0], context=env.flight)
    print("FED_PLAN_GROUPS", len(resolved_plan.to_dict()["result"]["groups"]))

    federated_exec = await server.handle(JsonRpcRequest(method="mep.federation.execute_task", params={
        "task": priority_task.to_dict(),
        "rollback_policy": "layer",
        "recovery_policy": "reroute",
    }, id=15), actor=drones[0], context=env.flight)
    print("FED_EXEC_TASK", federated_exec.to_dict()["result"]["environment_id"], federated_exec.to_dict()["result"]["response"]["result"]["rollback_policy"], "ATTEMPTS", len(federated_exec.to_dict()["result"]["attempts"]))

    federated_plan = await server.handle(JsonRpcRequest(method="mep.federation.execute_plan", params={
        "tasks": [task.to_dict() for task in swarm.formation_tasks()],
        "rollback_policy": "layer",
    }, id=16), actor=drones[0], context=env.flight)
    print("FED_EXEC_PLAN", len(federated_plan.to_dict()["result"]["executions"]), len(federated_plan.to_dict()["result"]["failed_routes"]))

    mission_graph = await server.handle(JsonRpcRequest(method="mep.federation.mission_graph", params={
        "tasks": [
            {**swarm.formation_tasks()[0].to_dict(), "task_id": "mission-1"},
            {**swarm.formation_tasks()[1].to_dict(), "task_id": "mission-2", "depends_on": ["mission-1"], "preferred_environment_tags": ["reserve"]},
        ],
    }, id=17), actor=drones[0], context=env.flight)
    print("MISSION_GRAPH", mission_graph.to_dict()["result"]["stage_count"], len(mission_graph.to_dict()["result"]["cross_environment_edges"]))

    execute_mission = await server.handle(JsonRpcRequest(method="mep.federation.execute_mission", params={
        "tasks": [
            {**swarm.formation_tasks()[0].to_dict(), "task_id": "mission-1"},
            {**swarm.formation_tasks()[1].to_dict(), "task_id": "mission-2", "depends_on": ["mission-1"], "preferred_environment_tags": ["reserve"]},
        ],
        "rollback_policy": "layer",
    }, id=18), actor=drones[0], context=env.flight)
    print("FED_EXEC_MISSION", len(execute_mission.to_dict()["result"]["stage_results"]), len(execute_mission.to_dict()["result"]["failed_stages"]))
    fault_status = await server.handle(JsonRpcRequest(method="mep.fault.status", params={}, id=1900), actor=drones[0], context=env.flight)
    print("FAULT_STATUS", fault_status.to_dict()["result"]["recovery_stats"])


if __name__ == "__main__":
    asyncio.run(main())
