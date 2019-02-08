import inspect
import itertools
import pkg_resources

# Import manticoreclient before we load any actual Manticore classes.
# We don't need it here, but we do rely on it to hook in the Manticore loggers:
from . import manticoreclient
del manticoreclient

from manticore.core.smtlib.operators import AND
from manticore.ethereum import ManticoreEVM, Detector
import manticore.ethereum.detectors

def manticore_version():
    return pkg_resources.get_distribution('manticore').version

def manticore_is_new_enough():
    '''Checks if Manticore is newer than version 0.2.2. Returns True or False if known, or None if uncertain.'''
    try:
        version = manticore_version()
        version = map(int, version.split('.'))
        for v, required in itertools.zip_longest(version, (0, 2, 2), fillvalue=0):
            if v < required:
                return False
    except Exception as e:
        return None
    return True

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

class ManticoreTest(object):
    def __init__(self, state, expression):
        self.state = state
        self.expression = expression
    def __bool__(self):
        return self.can_be_true()
    def can_be_true(self):
        return self.state.can_be_true(self.expression)
    def _solve_one(self, *variables, initial_state):
        with initial_state as state:
            state.constrain(self.expression)
            for v in variables:
                value = state.solve_one(v)
                yield value
                state.constrain(v == value)        
    def solve_one(self, *variables):
        '''Finds a solution to the state and returns all of the variables in that solution'''
        return self._solve_one(*variables, initial_state=self.state)
    def solve_all(self, *variables):
        '''Enumerates all solutions to the state for the given variables'''
        with self.state as state:
            while state.can_be_true(self.expression):
                solution = tuple(self._solve_one(*variables, initial_state=state))
                if len(solution) < len(variables):
                    break
                yield solution
                state.constrain(AND(*(v != s for v, s in zip(variables, solution))))
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

if __name__ == '__main__':
    print('Available Manticore Detectors:')
    for detector in get_detectors():
        print("  %s" % detector)
