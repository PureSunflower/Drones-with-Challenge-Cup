import logging

from storage.database import Database


class ExperimentLogger:
    def __init__(self, database: Database, run_id: str) -> None:
        self.database = database
        self.run_id = run_id
        self.logger = logging.getLogger("simulation")

    def __call__(self, now: float, event: str, node_id: str, details: dict) -> None:
        self.database.event(self.run_id, now, event, node_id, details)
        level = (logging.DEBUG if event.startswith(("message_", "packet_", "link_unavailable"))
                 or event in {"heartbeat", "delivery_attempt"} else logging.INFO)
        self.logger.log(level, "SIMULATION run=%s t=%.2f %s %s %s",
                        self.run_id, now, node_id, event, details)
