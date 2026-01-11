from abc import ABC


class Command(ABC):
    """"""
    def execute(self, instance: any, **kwargs):
        raise NotImplementedError

    def rollback(self, instance: any, **kwargs):
        raise NotImplementedError
