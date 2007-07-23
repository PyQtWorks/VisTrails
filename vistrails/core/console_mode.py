############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################
""" Module used when running  vistrails uninteractively """
from core import xml_parser
import core.interpreter.default
from core.utils import (VistrailsInternalError, expression, \
                        VistrailLocator, DummyView)
import db
from core.vistrail.vistrail import Vistrail

################################################################################

def open_vistrail(locator):
    if locator.origin == VistrailLocator.ORIGIN.FILE:
        v = db.services.io.openVistrailFromXML(locator.name)
        Vistrail.convert(v)
    elif locator.origin == VistrailLocator.ORIGIN.DB:
        config = {}
        config['host'] = locator.host
        config['port'] = locator.port
        config['db'] = locator.db
        config['user'] = locator.user
        config['passwd'] = locator.db
        v = db.services.io.open_from_db(config, locator.vt_id)
        Vistrail.convert(v)
    return v
    
def run_and_get_results(locator, workflow, parameters=''):
    """run_and_get_results(locator: VistrailLocator, workflow: int or
    str) Run the workflow 'workflow' for the given locator, and
    returns an interpreterresult object. workflow can be a tag name or
    a version.
    
    """
    elements = parameters.split(",")
    aliases = {}
    v = open_vistrail(locator)
    
    if type(workflow) == type("str"):
        version = v.tagMap[workflow]
    elif type(workflow) == type(1):
        version = workflow
    else:
        msg = "Invalid version tag or number: %s" % workflow
        raise VistrailsInternalError(msg)

    pip = v.getPipeline(workflow)
    for e in elements:
        pos = e.find("=")
        if pos != -1:
            key = e[:pos].strip()
            value = e[pos+1:].strip()
            
            if pip.hasAlias(key):
                ptype = pip.aliases[key][0]
                aliases[key] = (ptype,expression.parse_expression(value))
    view = DummyView()
    interpreter = core.interpreter.default.get_default_interpreter()
    
    return interpreter.execute(None, pip, locator, version, view, aliases)
    
def run(locator, workflow, parameters=''):
    """run(locator: VistrailLocator, workflow: int or str) -> boolean
    Run the workflow 'workflow' for the given locator.  Returns False
    in case of error. workflow can be a tag name or a version.

    """
    result = run_and_get_results(locator, workflow, parameters)
    (objs, errors, executed) = (result.objects,
                                result.errors, result.executed)
    for i in objs.iterkeys():
        if errors.has_key(i):
            return False
    return True

def cleanup():
    core.interpreter.cached.CachedInterpreter.cleanup()

################################################################################
#Testing

import core.packagemanager
import core.system
import sys
import unittest
import core.vistrail
import random
from core.vistrail.module import Module

class TestConsoleMode(unittest.TestCase):

    def setUp(self, *args, **kwargs):
        manager = core.packagemanager.get_package_manager()
        if manager.has_package('console_mode_test'):
            return
        old_path = sys.path
        sys.path.append(core.system.vistrails_root_directory() +
                        '/tests/resources')
        m = __import__('console_mode_test')
        sys.path = old_path
        d = {'console_mode_test': m}
        manager.add_package('console_mode_test')
        manager.initialize_packages(d)

    def test1(self):
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() +
                                  '/tests/resources/dummy.xml')
        result = run(locator, "int chain")
        self.assertEquals(result, True)

    def test_tuple(self):
        from core.vistrail.module_param import ModuleParam
        from core.vistrail.module_function import ModuleFunction
        from core.vistrail.module import Module
        interpreter = core.interpreter.default.get_default_interpreter()
        v = DummyView()
        p = core.vistrail.pipeline.Pipeline()
        params = [ModuleParam(type='Float',
                              val='2.0',
                              ),
                  ModuleParam(type='Float',
                              val='2.0',
                              )]
        p.addModule(Module(id=0,
                           name='TestTupleExecution',
                           functions=[ModuleFunction(name='input',
                                                     parameters=params)],
                           ))
        interpreter.execute(None, p, 'foo', 1, v, None)

    def test_python_source(self):
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() +
                                  '/tests/resources/pythonsource.xml')
        result = run(locator,"testPortsAndFail")
        self.assertEquals(result, True)

    def test_python_source_2(self):
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() +
                                  '/tests/resources/pythonsource.xml')
        result = run_and_get_results(locator, "test_simple_success")
        self.assertEquals(len(result.executed), 1)

    def test_dynamic_module_error(self):
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() + 
                                  '/tests/resources/dynamic_module_error.xml')
        result = run(locator, "test")
        self.assertEquals(result, False)

    def test_change_parameter(self):
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() + 
                                  '/tests/resources/test_change_vistrail.xml')
        result = run(locator, "v1")
        self.assertEquals(result, True)

        result = run(locator, "v2")
        self.assertEquals(result, True)

    def test_ticket_73(self):
        # Tests serializing a custom-named module to disk
        locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                  core.system.vistrails_root_directory() + 
                                  '/tests/resources/test_ticket_73.xml')
        v = open_vistrail(locator)

        import tempfile
        import os
        (fd, filename) = tempfile.mkstemp()
        os.close(fd)
        save_locator = VistrailLocator(VistrailLocator.ORIGIN.FILE,
                                       filename)
        try:
            v.serialize(save_locator.name)
        finally:
            os.remove(filename)

if __name__ == '__main__':
    unittest.main()
