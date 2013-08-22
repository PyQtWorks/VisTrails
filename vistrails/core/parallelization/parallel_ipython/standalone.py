from IPython.parallel.error import RemoteError

from vistrails.core.log.machine import Machine
from vistrails.core.modules.vistrails_module import ModuleError
from vistrails.core.parallelization import SchemeType, Parallelization, \
    ParallelizationScheme
from vistrails.core.parallelization.common import get_module_inputs_with_defaults

from .engine_manager import EngineManager
from .utils import print_remoteerror


def make_fake_module_and_execute(compute_code, inputs):
    global IPythonFakeModule

    import platform
    import socket
    import traceback

    machine_dict = {
            'name': socket.getfqdn(),
            'os': platform.system(),
            'architecture':
                    64 if platform.architecture()[0] == '64bit' else 32,
            'processor': platform.processor() or 'n/a',
            'ram': 0, # This is difficult to get...
        }

    from types import FunctionType

    try:
        IPythonFakeModule
    except NameError:
        # Inject a fake Module class
        class IPythonFakeModule(object):
            def __init__(self, i):
                self.inputPorts = i
                self.outputPorts = {}

            def getInputFromPort(self, inputPort, allowDefault=True):
                try:
                    value, is_default = self.inputPorts[inputPort]
                    if allowDefault or not is_default:
                        return value[0]
                except KeyError:
                    pass
                raise ValueError("Missing value from port %s" % inputPort)

            def hasInputFromPort(self, inputPort):
                try:
                    value, is_default = self.inputPorts[inputPort]
                    return not is_default
                except KeyError:
                    return False

            def checkInputFromPort(self, inputPort):
                if not self.hasInputFromPort(inputPort):
                    raise ValueError("'%s' is a mandatory port" % inputPort)

            def forceGetInputFromPort(self, inputPort, defaultValue=None):
                try:
                    value, is_default = self.inputPorts[inputPort]
                    if not is_default:
                        return value[0]
                except KeyError:
                    pass
                return defaultValue

            def getInputListFromPort(self, inputPort):
                try:
                    value, is_default = self.inputPorts[inputPort]
                    if not is_default:
                        return value
                except KeyError:
                    pass
                raise ValueError("Missing value from port %s" % inputPort)

            def forceGetInputListFromPort(self, inputPort):
                try:
                    value, is_default = self.inputPorts[inputPort]
                    if not is_default:
                        return value
                except KeyError:
                    pass
                return []

            def setResult(self, port, value):
                self.outputPorts[port] = value

    IPythonFakeModule.compute = FunctionType(
            compute_code,   # code
            globals(),      # globals
            'compute')      # name

    m = IPythonFakeModule(inputs)
    try:
        m.compute()
    except Exception, e:
        # Return the formatted exception, plus the machine info
        exc = (e.__class__.__name__,) + e.args, traceback.format_exc()
        return False, exc, machine_dict
    else:
        # Returns the results to be set on the port, plus the machine info
        return True, m.outputPorts, machine_dict


@apply
class IPythonStandaloneScheme(ParallelizationScheme):
    def __init__(self):
        ParallelizationScheme.__init__(self,
                40, # higher than regular IPython
                SchemeType.REMOTE_NO_VISTRAILS,
                'ipython-standalone')

    def do_compute(self, target, module):
        if target.scheme != 'ipython-standalone':
            raise ValueError
        profile = target.get_annotation('ipython-profile')
        if profile is not None:
            profile = profile.value
        if not profile:
            raise ValueError

        profmngr = EngineManager(profile)

        # Connect to cluster
        rc = profmngr.ensure_client(connect_only=True)
        if rc is None:
            raise ModuleError(
                    module,
                    "Couldn't connect to IPython profile %s")
        engines = rc.ids

        if not engines:
            raise ModuleError(
                    module,
                    "No IPython engines detected!")

        # Get inputs
        inputs = get_module_inputs_with_defaults(module)

        # Execute
        with rc.load_balanced_view() as ldview:
            func_module = make_fake_module_and_execute.__module__
            make_fake_module_and_execute.__module__ = '__main__'
            try:
                future = ldview.apply_async(
                        make_fake_module_and_execute,
                        module.compute.im_func.func_code,
                        inputs)
            finally:
                make_fake_module_and_execute.__module__ = func_module
        async_task = module._runner.make_async_task()

        def callback(res):
            def get_results(runner):
                def compute():
                    try:
                        success, results, machine_dict = res.get()
                    except RemoteError, e:
                        print_remoteerror(e)
                        raise
                    else:
                        if success:
                            module.outputPorts.update(results)

                        module_exec = module.module_exec.do_copy(
                                new_ids=True,
                                id_scope=module.logging.log.log.id_scope,
                                id_remap={})
                        machine_id = module.logging.log.log.id_scope.getNewId(
                                Machine.vtType)
                        machine = Machine(id=machine_id,
                                          **machine_dict)
                        module.logging.log.workflow_exec.add_machine(machine)
                        module_exec.machine_id = machine.id
                        if not success:
                            module_exec.error = '%s: %s' % (
                                    results[0][0], results[0][1])
                            module_exec.completed = -1
                        else:
                            module_exec.completed = 1
                        module.logging.log_remote_execution(
                                module, 'ipython-standalone',
                                [('ipython-profile', profile)],
                                module_execs=[module_exec])
                        if not success:
                            raise RemoteError(
                                    results[0][0],  # name
                                    results[0][1],  # message
                                    results[1])     # traceback
                module.do_compute(compute=compute)
            async_task.callback(get_results)
        rc.add_callback(future, callback)

    def finalize(self):
        EngineManager.finalize()


# IPython has some logic in pickleutil (class CannedFunction) to send the
# function's bytecode to the engines
Parallelization.register_parallelization_scheme(IPythonStandaloneScheme)
