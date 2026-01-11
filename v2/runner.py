
class Runner(ABC):
    """"""

    def __init__(self, *args):
        self.steps = args

    def run(self):
        pass
    

class Sync(Runner):
    """"""
    def run(self):
        for step in self.steps:
            step()