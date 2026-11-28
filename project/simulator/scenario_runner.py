from communication.network_simulator import NetworkSettings
from config.settings import Settings
from simulator.simulation_engine import Simulation

SCENARIOS = {
    "normal": NetworkSettings(),
    "single-outage": NetworkSettings(),
    "double-outage": NetworkSettings(),
    "loss": NetworkSettings(loss=0.20),
    "duplicate": NetworkSettings(duplicate=0.60),
    "delay": NetworkSettings(min_delay=0.50, max_delay=1.25),
    "partition": NetworkSettings(),
    "recovery": NetworkSettings(),
    "competition": NetworkSettings(),
}


def scenario_steps(name: str, sim: Simulation):
    yield 2
    if name in ("partition", "recovery"):
        sim.partition({"001", "002", "003"})
    if name == "competition":
        sim.set_link("001", "002", False)
    sim.publish("006", "survey", (0, 0), frozenset({"COMM"}))
    yield 7
    if name == "competition":
        sim.set_link("001", "002", True)
    if name in ("single-outage", "double-outage"):
        sim.power("001", False)
        if name == "double-outage":
            sim.power("002", False)
        yield 16
        sim.power("001", True)
        if name == "double-outage":
            sim.power("002", True)
        yield 3
    elif name == "recovery":
        yield 8
        sim.heal()
        yield 13
    else:
        yield 4

def run_scenario(name: str, record, seed: int,
                 network: NetworkSettings | None = None) -> dict:
    settings = Settings(seed=seed)
    network = network if network is not None else SCENARIOS[name]
    sim = Simulation(settings, network, record)
    from dataclasses import asdict
    record(0, "scenario_started", "SIMULATOR",
           dict(name=name, settings=asdict(settings), network=asdict(network), origin="SIMULATION"))
    for seconds in scenario_steps(name, sim):
        sim.advance(seconds)
    result = {
        "origin": "SIMULATION",
        "scenario": name,
        "simulation_time": sim.now,
        "nodes": {
            node_id: {
                "status": node.node_status,
                "executing": [] if node_id in sim.network.down else [
                    key for key, view in node.local_task_table.items()
                    if view.status == "EXECUTING"
                ],
                "peers": {peer_id: peer.status for peer_id, peer in node.known_nodes.items()},
                "tasks": {key: dict(status=view.status, epoch=view.epoch, owner=view.owner,
                                    outcome_unknown=view.outcome_unknown)
                          for key, view in node.local_task_table.items()},
            }
            for node_id, node in sim.nodes.items()
        },
    }
    record(sim.now, "scenario_finished", "SIMULATOR", result)
    return result
