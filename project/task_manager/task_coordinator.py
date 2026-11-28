from collections.abc import Callable

from communication.message import Message, MessageType as Kind
from communication.protocol import finite
from config.settings import Settings
from node_manager.node_state import NodeStatus
from task_manager.task import Round, Task, TaskStatus as Status, TaskView
from task_manager.task_allocator import best_candidate, certified_owner
from task_manager.task_recovery import epoch_at, epoch_start
from task_manager.task_scorer import score_task


class TaskCoordinator:
    def __init__(self, node, members: frozenset[str], settings: Settings, record: Callable) -> None:
        self.node = node
        self.members = members
        self.settings = settings
        self.record = record
        self.views: dict[str, TaskView] = {}

    def register(self, task: Task, now: float) -> None:
        existing = self.views.get(task.task_id)
        if existing:
            if existing.task != task:
                raise ValueError("Conflicting task definition")
            return
        self.views[task.task_id] = TaskView(task)
        self.record(now, "task_known", task.payload())

    def transition(self, view: TaskView, status: Status, now: float) -> None:
        if view.status != status:
            self.record(now, "task_state", dict(task_id=view.task.task_id, epoch=view.epoch,
                        before=view.status, after=status, owner=view.owner,
                        outcome_unknown=view.outcome_unknown))
            view.status = status

    def cancel(self, task_id: str, now: float) -> None:
        view = self.views[task_id]
        if view.task.publisher != self.node.node_id or view.result is not None:
            raise ValueError("Only the publisher can cancel an unfinished task")
        self.apply_cancellation(view, now)
        self.advertise(view, now)

    def apply_cancellation(self, view: TaskView, now: float) -> None:
        if view.status != Status.CANCELLED:
            view.result = Status.CANCELLED
            view.owner = None
            view.outcome_unknown = False
            self.transition(view, Status.CANCELLED, now)

    def send(self, kind: Kind, task: Task, epoch: int, now: float, **fields) -> None:
        self.node.send(kind, now, dict(task_id=task.task_id, epoch=epoch, **fields))

    def receive(self, msg: Message, now: float) -> None:
        data = msg.payload
        if msg.msg_type in (Kind.TASK_ANNOUNCE, Kind.TASK_UPDATE):
            task = Task.parse(data)
            if task.publisher not in self.members or (
                msg.msg_type == Kind.TASK_ANNOUNCE and msg.src != task.publisher
            ):
                raise ValueError("Invalid task publisher")
            cancelled = data.get("cancelled", False)
            if type(cancelled) is not bool or (cancelled and msg.src != task.publisher):
                raise ValueError("Invalid cancellation authority")
            self.register(task, now)
            if cancelled:
                self.apply_cancellation(self.views[task.task_id], now)
            return
        task_id, epoch = data.get("task_id"), data.get("epoch")
        if not isinstance(task_id, str) or type(epoch) is not int or epoch < 0:
            raise ValueError("Invalid task reference")
        view = self.views.get(task_id)
        if view is None or epoch > epoch_at(view.task, now, self.settings):
            return
        if msg.msg_type in (Kind.TASK_BID, Kind.TASK_CLAIM):
            if epoch != epoch_at(view.task, now, self.settings):
                return
            score = data.get("score")
            offset = msg.timestamp - epoch_start(view.task, epoch, self.settings)
            bidding = msg.msg_type == Kind.TASK_BID
            start = 0 if bidding else self.settings.bid_window
            end = self.settings.bid_window if bidding else start + self.settings.claim_window
            if not finite(score) or not 0 <= score <= 1 or not start <= offset < end:
                raise ValueError("Invalid bid or claim")
            round_state = view.rounds.setdefault(epoch, Round())
            (round_state.bids if bidding else round_state.claims).setdefault(msg.src, score)
        elif msg.msg_type == Kind.TASK_ACK:
            candidate = data.get("candidate")
            if not isinstance(candidate, str) or candidate not in self.members:
                raise ValueError("Invalid vote")
            view.rounds.setdefault(epoch, Round()).votes.setdefault(msg.src, candidate)
        elif msg.msg_type in (Kind.TASK_COMPLETE, Kind.TASK_RELEASE):
            self.accept_result(view, epoch, data.get("owner", msg.src), data, now)

    def accept_result(self, view: TaskView, epoch: int, owner: str, data: dict, now: float) -> None:
        at, result = data.get("finished_at"), data.get("result")
        if not finite(at) or result not in ("COMPLETED", "FAILED"):
            raise ValueError("Invalid task result")
        start = epoch_start(view.task, epoch, self.settings)
        votes = view.rounds.get(epoch)
        completion = (epoch, at, owner, result)
        execution_start = start + self.settings.bid_window + self.settings.claim_window
        if (view.status != Status.CANCELLED and (view.task.deadline is None or at < view.task.deadline)
                and isinstance(owner, str) and owner in self.members
                and (view.completion is None or completion < view.completion)
                and execution_start <= at < start + self.settings.lease_period and at <= now
                and votes and certified_owner(votes.votes, len(self.members)) == owner):
            view.completion = completion
            view.result = result
            view.outcome_unknown = False
            self.transition(view, Status(result), now)

    def finish(self, task_id: str, now: float, success: bool = True) -> None:
        view = self.views[task_id]
        if (view.status != Status.EXECUTING or view.owner != self.node.node_id
                or view.epoch != epoch_at(view.task, now, self.settings)
                or (view.task.deadline is not None and now >= view.task.deadline)):
            raise ValueError("An active lease is required to report an outcome")
        result = "COMPLETED" if success else "FAILED"
        self.accept_result(view, view.epoch, self.node.node_id,
                           dict(finished_at=now, result=result), now)

    def advertise(self, view: TaskView, now: float) -> None:
        node_id = self.node.node_id
        kind = Kind.TASK_ANNOUNCE if node_id == view.task.publisher else Kind.TASK_UPDATE
        payload = view.task.payload()
        if node_id == view.task.publisher and view.status == Status.CANCELLED:
            payload["cancelled"] = True
        self.node.send(kind, now, payload)
        for epoch, round_state in view.rounds.items():
            candidate = round_state.votes.get(node_id)
            if candidate is not None:
                self.send(Kind.TASK_ACK, view.task, epoch, now, candidate=candidate)
        if view.completion:
            epoch, at, owner, result = view.completion
            kind = Kind.TASK_COMPLETE if result == "COMPLETED" else Kind.TASK_RELEASE
            self.send(kind, view.task, epoch, now, finished_at=at, owner=owner, result=result)

    def step(self, now: float, advertise: bool) -> None:
        node_id = self.node.node_id
        for view in self.views.values():
            if advertise:
                self.advertise(view, now)
            if view.result is not None or now < view.task.starts_at:
                continue
            task = view.task
            if task.deadline is not None and now >= task.deadline:
                view.result = Status.EXPIRED
                view.owner = None
                self.transition(view, Status.EXPIRED, now)
                continue
            epoch = epoch_at(task, now, self.settings)
            if epoch != view.epoch:
                if view.owner:
                    view.previous_owner = view.owner
                view.epoch, view.owner = epoch, None
                self.transition(view, Status.BIDDING if epoch == 0 else Status.REASSIGNING, now)
            round_state = view.rounds.setdefault(epoch, Round())
            offset = now - epoch_start(task, epoch, self.settings)
            claim_end = self.settings.bid_window + self.settings.claim_window
            if offset < self.settings.bid_window:
                if node_id not in round_state.bids:
                    score = score_task(self.node.profile, task, self.node.load_at(now), self.settings.distance_scale)
                    if score is not None:
                        round_state.bids[node_id] = score
                        self.record(now, "task_bid", dict(task_id=task.task_id, epoch=epoch, score=score))
                if node_id in round_state.bids:
                    self.send(Kind.TASK_BID, task, epoch, now, score=round_state.bids[node_id])
                continue
            if offset < claim_end:
                if best_candidate(round_state.bids) == node_id:
                    score = round_state.bids[node_id]
                    if node_id not in round_state.claims:
                        self.record(now, "task_claim", dict(task_id=task.task_id, epoch=epoch, score=score))
                    round_state.claims[node_id] = score
                    self.send(Kind.TASK_CLAIM, task, epoch, now, score=score)
                continue
            # Persist one vote per epoch across simulated power cycles. Majorities intersect.
            candidates = {candidate: score for candidate, score in round_state.claims.items()
                          if round_state.bids.get(candidate) == score}
            candidate = best_candidate(candidates)
            if node_id not in round_state.votes and candidate:
                round_state.votes[node_id] = candidate
                self.record(now, "task_vote", dict(task_id=task.task_id, epoch=epoch, candidate=candidate))
                self.send(Kind.TASK_ACK, task, epoch, now, candidate=candidate)
            owner = certified_owner(round_state.votes, len(self.members))
            if owner is None:
                continue
            if view.owner != owner:
                view.owner = owner
                view.outcome_unknown = False
                self.transition(view, Status.ASSIGNED, now)
                if view.previous_owner and owner != view.previous_owner:
                    self.record(now, "task_reassigned", dict(task_id=task.task_id, epoch=epoch,
                                previous_owner=view.previous_owner, owner=owner))
            if owner == node_id:
                self.transition(view, Status.EXECUTING, now)
            elif self.node.known_nodes[owner].status == NodeStatus.OFFLINE:
                if not view.outcome_unknown:
                    view.outcome_unknown = True
                    self.transition(view, Status.REASSIGNING, now)
                    self.record(now, "task_outcome_unknown", dict(task_id=task.task_id, owner=owner))
            elif view.outcome_unknown and self.node.known_nodes[owner].status == NodeStatus.ONLINE:
                view.outcome_unknown = False
                self.transition(view, Status.ASSIGNED, now)
