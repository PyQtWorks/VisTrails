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
""" This file contains classes related to loading and saving a set of
bookmarks in a XML file. 
It defines the following classes:
 - Bookmark
 - BookmarkCollection
 - BookmarkTree
 - BookmarkController 
"""
import os.path
from core.ensemble_pipelines import EnsemblePipelines
from core.interpreter.default import get_default_interpreter
from core.param_explore import InterpolateDiscreteParam, ParameterExploration
from core.utils import VistrailsInternalError, DummyView
from core.utils.uxml import named_elements, XMLWrapper
from core.xml_parser import XMLParser

################################################################################

class Bookmark(object):
    """Stores a Vistrail Bookmark"""
    def __init__(self, parent='', id=-1, vistrailsFile='', pipeline=0, name='', 
                 type=''):
        """__init__(parent: int, id: int, vistrailsFile: str,
                    pipeline: int, name: str, type: str) -> Bookmark
        It creates a vistrail bookmark."""
        self.id = id
        self.parent = parent
        self.filename = vistrailsFile
        self.pipeline = pipeline
        self.name = name
        self.type = type
        if os.path.exists(self.filename):
            self.error = 0
        else:
            self.error = 1 #error = 1: file not found
                           #error = 2: version not found

    def serialize(self, dom, element):
        """serialize(dom, element) -> None
        Convert this object to an XML representation.
        """
        bmark = dom.createElement('bookmark')
        bmark.setAttribute('id', str(self.id))
        bmark.setAttribute('parent', str(self.parent))
        bmark.setAttribute('name', str(self.name))
        bmark.setAttribute('type', str(self.type))
        if self.type == 'item':
            bmark.setAttribute('pipeline', str(self.pipeline))
            node = dom.createElement('filename')
            filename = dom.createTextNode(str(self.filename))
            node.appendChild(filename)
            bmark.appendChild(node)           
        element.appendChild(bmark)

    def __str__(self):
        """ __str__() -> str - Writes itself as a string """ 
        return """<<id= '%s' name='%s' type='%s' parent='%s' 
        filename='%s' pipeline='%s' error='%s'>>""" %  (
            self.id,
            self.name,
            self.type,
            self.parent,
            self.filename,
            self.pipeline,
            self.error)

    @staticmethod
    def parse(element):
        """ parse(element) -> Bookmark
        Parse an XML object representing a bookmark and returns a Bookmark
        object. 
        It checks if the vistrails file exists.
        
        """
        bookmark = Bookmark()
        bookmark.id = int(element.getAttribute('id'))
        bookmark.parent = element.getAttribute('parent')
        bookmark.name = element.getAttribute('name')
        bookmark.type = element.getAttribute('type')
        if bookmark.type == "item":
            for n in element.childNodes:
                if n.localName == "filename":
                    bookmark.filename = str(n.firstChild.nodeValue).strip(" \n\t")
                    if os.path.exists(bookmark.filename):
                        bookmark.error = 0
                    else:
                        bookmark.error = 1
                    break
            bookmark.pipeline = int(element.getAttribute('pipeline'))
        return bookmark

    def __eq__(self, other):
        """ __eq__(other: Bookmark) -> boolean
        Returns True if self and other have the same attributes. Used by == 
        operator. 
        
        """
        if self.id != other.id:
            return False
        if self.name != other.name:
            return False
        if self.type != other.type:
            return False
        if self.parent != other.parent:
            return False
        if self.type == 'item':
            if self.filename != other.filename:
                return False
            if self.pipeline != other.pipeline:
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

class BookmarkCollection(XMLWrapper):
    """Class to store a collection of bookmarks.

    """
    def __init__(self):
        """ __init__() -> BookmarkCollection """
        root = Bookmark()
        root.id = 0
        root.name = "Bookmarks"
        root.type = "folder"
        root.error = 0
        self.bookmarks = BookmarkTree(root)
        self.bookmark_map = {}
        self.changed = False
        self.updateGUI = True
        self.current_id = 1

    def add_bookmark(self, bookmark):
        """add_bookmark(bookmark: Bookmark) -> None
        Adds a bookmark to the collection """
        
        if self.bookmark_map.has_key(bookmark.id):
            raise VistrailsInternalError("Bookmark with repeated id")
        self.bookmarks.add_bookmark(bookmark)
        self.current_id = max(self.current_id, bookmark.id+1)
        self.bookmark_map[bookmark.id] = bookmark
        self.changed = True
        self.updateGUI = True

    def find_bookmark(self, id, node=None):
        """find_bookmark(id,node=None) -> BookmarkTree
        Finds a bookmark node with a given id starting at node.
        When node = None, it will start from the root.
        
        """
        if node == None:
            node = self.bookmarks
        if node.bookmark.id == id:
            return node
        else:
            for child in node.children:
                result = self.find_bookmark(id,child)
                if result:
                    return result
            else:
                return None

    def remove_bookmark(self, id, node=None):
        """remove_bookmark(id: int, node: BookmarkTree) -> None 
        Remove bookmark and children starting searchin from node
        
        """
        child = self.find_bookmark(id, node)
        if child:
            del self.bookmark_map[id]
            for c in child.children:
                self.remove_bookmark(c.bookmark.id,c)
            if child.parent:
                child.parent.children.remove(child)
            del child
        
    def clear(self):
        """ clear() -> None 
        Remove current bookmarks """
        self.bookmarks.clear()
        self.bookmark_map = {}
        self.changed = True
        self.current_id = 1

    def parse(self, filename):
        """parse(filename: str) -> None  
        Loads a collection of bookmarks from a XML file, appending it to
        self.bookmarks.
        
        """
        self.open_file(filename)
        root = self.dom.documentElement
        for element in named_elements(root, 'bookmark'):    
            self.add_bookmark(Bookmark.parse(element))
        self.refresh_current_id()
        self.changed = False
        self.updateGUI = True

    def serialize(self, filename):
        """serialize(filename:str) -> None 
        Writes bookmark collection to disk under given filename.
          
        """
        dom = self.create_document('bookmarks')
        root = dom.documentElement
        
        for bookmark in self.bookmark_map.values():
            bookmark.serialize(dom, root)

        self.write_document(root, filename)
        self.changed = False

    def refresh_current_id(self):
        """refresh_current_id() -> None
        Recomputes the next unused id from scratch
        
        """
        self.current_id = max([0] + self.bookmark_map.keys()) + 1

    def get_fresh_id(self):
        """get_fresh_id() -> int - Returns an unused id. """
        return self.current_id

###############################################################################

class BookmarkTree(object):
    """BookmarkTree implements an n-ary tree of bookmarks. """
    def __init__(self, bookmark):
        self.bookmark = bookmark
        self.children = []
        self.parent = None

    def add_bookmark(self, bookmark):
        #assert bookmark.parent == self.bookmark.name
        result = BookmarkTree(bookmark)
        result.parent = self
        self.children.append(result)
        return result
    
    def clear(self):
        for node in self.children:
            node.clear()
        self.children = [] 
    
    def as_list(self):
        """as_list() -> list of bookmarks
        Returns all its nodes in a list """
        result = []
        result.append(self.bookmark)
        for node in self.children:
            result.extend(node.as_list())
        return result
        
################################################################################

class BookmarkController(object):
    def __init__(self):
        """__init__() -> BookmarkController
        Creates Bookmark Controller
        
        """
        self.collection = BookmarkCollection()
        self.filename = ''
        self.pipelines = {}
        self.active_pipelines = []
        self.ensemble = EnsemblePipelines()

    def load_bookmarks(self):
        """load_bookmarks() -> None
        Load Bookmark collection and instantiate all pipelines

        """

        if os.path.exists(self.filename):
            self.collection.parse(self.filename)
            self.load_all_pipelines()
    
    def add_bookmark(self, parent, vistrailsFile, pipeline, name=''):
        """add_bookmark(parent: int, vistrailsFile: str, pipeline: int,
                       name: str) -> None
        creates a bookmark with the given information and adds it to the 
        collection

        """
        id = self.collection.get_fresh_id()
        bookmark = Bookmark(parent, id, vistrailsFile,pipeline,name,"item")
        self.collection.add_bookmark(bookmark)
        self.collection.serialize(self.filename)
        if not bookmark.error:
            self.load_pipeline(id)

    def remove_bookmark(self, id):
        """remove_bookmark(id: int) -> None 
        Remove bookmark with id from the collection 
        
        """
        bookmark = self.collection.bookmark_map[id]
        self.collection.remove_bookmark(id)
        if not bookmark.error:
            del self.pipelines[id]
            del self.ensemble.pipelines[id]
            if id in self.active_pipelines:
                del self.active_pipelines[id]
            if id in self.ensemble.active_pipelines:
                del self.ensemble.active_pipelines[id]
            self.ensemble.assembleAliases()
        self.collection.serialize(self.filename)
    
    def update_alias(self, alias, value):
        """update_alias(alias: str, value: str) -> None
        Change the value of an alias and propagate changes in the pipelines
        
        """
        self.ensemble.update(alias,value)
    
    def reload_pipeline(self, id):
        """reload_pipeline(id: int) -> None
        Given a bookmark id, loads its original pipeline in the ensemble 

        """
        if self.pipelines.has_key(id):
            self.ensemble.addPipeline(id, self.pipelines[id])
            self.ensemble.assembleAliases()

    def load_pipeline(self, id):
        """load_pipeline(id: int) -> None
        Given a bookmark id, loads its correspondent pipeline and include it in
        the ensemble 

        """
        parser = XMLParser()
        bookmark = self.collection.bookmark_map[id]
        parser.openVistrail(bookmark.filename)
        v = parser.getVistrail()
        if v.hasVersion(bookmark.pipeline):
            self.pipelines[id] = v.getPipeline(bookmark.pipeline)
            self.ensemble.addPipeline(id, self.pipelines[id])
            self.ensemble.assembleAliases()
        else:
            bookmark.error = 2
        parser.closeVistrail()

    def load_all_pipelines(self):
        """load_all_pipelines() -> None
        Load all bookmarks' pipelines and sets an ensemble

        """
        parser = XMLParser()
        self.pipelines = {}
        vistrails = {}
        for id, bookmark in self.collection.bookmark_map.iteritems():
            if os.path.exists(bookmark.filename):
                if vistrails.has_key(bookmark.filename):
                    v = vistrails[bookmark.filename]
                else:
                    parser.openVistrail(bookmark.filename)
                    v = parser.getVistrail()
                    parser.closeVistrail()
                    vistrails[bookmark.filename] = v
                    
                if v.hasVersion(bookmark.pipeline):
                    self.pipelines[id] = v.getPipeline(bookmark.pipeline)
                    bookmark.error = 0
                else:
                    bookmark.error = 2
            else:
                bookmark.error = 1

        self.ensemble = EnsemblePipelines(self.pipelines)
        self.ensemble.assembleAliases()

    def set_active_pipelines(self, ids):
        """ set_active_pipelines(ids: list) -> None
        updates the list of active pipelines 
        
        """
        self.active_pipelines = ids
        self.ensemble.active_pipelines = ids
        self.ensemble.assembleAliases()

    def write_bookmarks(self):
        """write_bookmarks() -> None - Write collection to disk."""
        self.collection.serialize(self.filename)

    def execute_workflows(self, ids):
        """execute_workflows(ids:list of Bookmark.id) -> None
        Execute the workflows bookmarked with the ids

        """
        view = DummyView()
        w_list = []
        for id in ids:
            bookmark = self.collection.bookmark_map[id]
            w_list.append((bookmark.filename,
                          bookmark.pipeline,
                          self.ensemble.pipelines[id],
                          view))
            
        self.execute_workflow_list(w_list)
    
    def execute_workflow_list(self, vistrails):
        """execute_workflow_list(vistrails: [(name, version, 
                                            pipeline, view]) -> None
        Executes a list of pipelines, where:
         - name: str is the vistrails filename
         - version: int is the version number
         - pipeline: Pipeline object
         - view: interface to a QPipelineScene
        
        """
        interpreter = get_default_interpreter()
        for vis in vistrails:
            (name, version, pipeline, view) = vis
            (objs, errors, executed) = interpreter.execute(None,
                                                           pipeline, 
                                                           name, 
                                                           version, 
                                                           view)

    def parameter_exploration(self, ids, specs):
        """parameter_exploration(ids: list, specs: list) -> None
        Build parameter exploration in original format for each bookmark id.
        
        """
        view = DummyView()
        for id in ids:
            new_specs = []
            bookmark = self.collection.bookmark_map[id]
            new_specs = self.merge_parameters(id, specs)
            p = ParameterExploration(new_specs)
            pipeline_list = p.explore(self.ensemble.pipelines[id])
            vistrails = ()
            for pipeline in pipeline_list:
                vistrails += ((bookmark.filename,
                               bookmark.pipeline,
                               pipeline,
                               view),)
            self.execute_workflow_list(vistrails)
    
    def merge_parameters(self, id, specs):
        """merge_parameters(id: int, specs: list) -> list
        Identifies aliases in a common function and generates only one tuple
        for them 
        
        """
        aliases = {}
        a_list = []
        for dim in range(len(specs)):
            specs_per_dim = specs[dim]
            for interpolator in specs_per_dim:
                #build alias dictionary
                 alias = interpolator[0]
                 info = self.ensemble.getSource(id,alias)
                 if info:
                     if aliases.has_key(alias):
                         aliases[alias].append((info, 
                                                interpolator[2],
                                                interpolator[3],
                                                dim))
                     else:
                         aliases[alias] = [(info, 
                                            interpolator[2],
                                            interpolator[3],
                                            dim)]
                     a_list.append((alias,info, 
                                   interpolator[2],
                                   interpolator[3],
                                   dim))
        new_specs = [] 
        repeated = []
        new_specs_per_dim = {}
        for data in a_list:
            alias = data[0]
            if alias not in repeated:
                mId = data[1][0]
                fId = data[1][1]
                pId = data[1][2]
                common = {}
                common[pId] = alias
                for d in a_list:
                    a = d[0]
                    if a != alias:
                        if mId == d[1][0] and fId == d[1][1]:
                            #assuming that we cannot set the same parameter
                            #across the dimensions
                            common[d[1][2]] = a
                            repeated.append(a)
                pip = self.ensemble.pipelines[id]
                m = pip.getModuleById(mId)
                f = m.functions[fId]
                pCount = len(f.params)
                new_range = []
                for i in range(pCount):
                    if i not in common.keys():
                        p = f.params[i]
                        new_range.append((p.value(),p.value()))
                    else:
                        d_list = aliases[common[i]]
                        r = None
                        for d in d_list:
                            if d[0][2] == i:
                                r = d[1][0]
                        new_range.append(r)
                interpolator = InterpolateDiscreteParam(m,
                                                        f.name,
                                                        new_range,
                                                        data[3])
                if new_specs_per_dim.has_key(data[4]):
                    new_specs_per_dim[data[4]].append(interpolator)
                else:
                    new_specs_per_dim[data[4]] = [interpolator]
        for dim in sorted(new_specs_per_dim.keys()):
            l_inter = new_specs_per_dim[dim]
            l = []
            for inter in l_inter:
                l.append(inter)
            new_specs.append(l)
        return new_specs


###############################################################################

import unittest
import core.system
import os
class TestBookmarkCollection(unittest.TestCase):
    def test1(self):
        """ Exercising writing and reading a file """
        collection = BookmarkCollection()
        bookmark = Bookmark()
        bookmark.id = 1
        bookmark.parent = ''
        bookmark.name = 'contour 4'
        bookmark.type = 'item'
        bookmark.filename = 'brain_vistrail.xml'
        bookmark.pipeline = 126
        
        collection.add_bookmark(bookmark)

        #writing
        collection.serialize('bookmarks.xml')

        #reading it again
        collection.clear()
        collection.parse('bookmarks.xml')
        newbookmark = collection.bookmarks.as_list()[1]
        assert bookmark == newbookmark
    
        #remove created file
        os. unlink('bookmarks.xml')

    def test_empty_bookmark(self):
        """ Exercises doing things on an empty bookmark. """
        collection = BookmarkCollection()
        collection.parse(core.system.vistrails_root_directory() +
                         'tests/resources/empty_bookmarks.xml')

if __name__ == '__main__':
    unittest.main()
