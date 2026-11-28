import argparse
import json
import logging
from dataclasses import replace
from pathlib import Path

from config.settings import ROOT, Settings
from simulator.scenario_runner import SCENARIOS, run_scenario
from storage.database import Database
from storage.experiment_logger import ExperimentLogger


def main() -> None:
    parser = argparse.ArgumentParser(description="Six-node SIMULATION prototype")
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--seed", type=int, default=Settings().seed)
    parser.add_argument("--min-delay", type=float)
    parser.add_argument("--max-delay", type=float)
    parser.add_argument("--loss", type=float)
    parser.add_argument("--duplicate", type=float)
    parser.add_argument("--db", type=Path, default=ROOT / "data/experiments.sqlite3")
    parser.add_argument("--log", type=Path, default=ROOT / "logs/simulation.log")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    overrides = {key: getattr(args, key) for key in ("min_delay", "max_delay", "loss", "duplicate")
                 if getattr(args, key) is not None}
    paths = [path.resolve() for path in (args.db, args.log, args.csv) if path is not None]
    if len(set(paths)) != len(paths):
        parser.error("database, log and CSV paths must be distinct")
    try:
        network = replace(SCENARIOS[args.scenario], **overrides)
    except ValueError as exc:
        parser.error(str(exc))
    args.log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=args.log, encoding="utf-8", level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s %(message)s")
    with Database(args.db) as database:
        run_id = database.start(args.scenario)
        result = run_scenario(args.scenario, ExperimentLogger(database, run_id), args.seed, network)
        database.finish(run_id, result)
        if args.csv:
            database.export(args.csv, run_id)
    print(json.dumps({"run_id": run_id, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
