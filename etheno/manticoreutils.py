import inspect

from manticore.ethereum import ManticoreEVM, Detector
import manticore.ethereum.detectors

def get_detectors():
    for name, obj in inspect.getmembers(manticore.ethereum.detectors):
        if inspect.isclass(obj) and issubclass(obj, manticore.ethereum.detectors.Detector) and obj != manticore.ethereum.detectors.Detector:
            yield obj

def register_all_detectors(manticore):
    for detector in get_detectors():
        manticore.register_detector(detector())

class StopAtDepth(Detector):
    ''' This just aborts explorations that are too deep '''

    def __init__(self, max_depth):
        super().__init__()
        self.max_depth = max_depth

    def will_start_run_callback(self, *args):
        with self.manticore.locked_context('seen_rep', dict) as reps:
            reps.clear()

    def will_decode_instruction_callback(self, state, pc):
        world = state.platform
        with self.manticore.locked_context('seen_rep', dict) as reps:
            item = (world.current_transaction.sort == 'CREATE', world.current_transaction.address, pc)
            if not item in reps:
                reps[item] = 0
            reps[item] += 1
            if reps[item] > self.max_depth:
                state.abandon()

if __name__ == '__main__':
    print('Available Manticore Detectors:')
    for detector in get_detectors():
        print("  %s" % detector)
