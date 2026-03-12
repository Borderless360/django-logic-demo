import uuid
from typing import TypedDict


class Action():
    name: str = 'Action'
    process: 'Process' | None = None
    next: 'Action' | None = None

    def __init__(self, next: 'Action' | None = None):
        self.next = next

    @property
    def is_available(self) -> bool:
        return True

    def do(self) -> uuid.UUID:
        return uuid.uuid4()

class Transition(Action):
    name = 'Transition'

    sources: list[str]
    target: str
    in_progress_state: str
    failed_state: str

    def is_available(self) -> bool:
        for source in self.sources:
            if source not in self.process.state:
                return False
        return True

    def do(self) -> uuid.UUID:
        return uuid.uuid4()

class MakeReportAction(Action):
    name = 'MakeReport'

    def do(self) -> uuid.UUID:
        action_id = super().do()
        # TODO: make report
        return action_id

class SendReportAction(Action):
    name = 'SendReport'


class Process():
    transitions = [
        MakeReportAction(next=SendReportAction),
        SendReportAction(),
        Transition(
            [B_STATES.B0], B_STATES.B1, 
            failed_state=B_STATES.Err, 
            in_progress_state=B_STATES.B1,
            next=SendReportAction),
    ]
