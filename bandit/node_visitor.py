#!/usr/bin/env python

import sys
import ast, _ast
import copy
from bandit import tester as b_tester
from bandit import utils as b_utils

class BanditNodeVisitor(ast.NodeVisitor):

    imports = set()
    import_aliases = {}
    qualname = ""
    calldone = False
    callbasenode = None
    logger = None
    results = None
    tester = None
    testset = None
    fname = None
    depth = 0

    context = None
    context_template = {'node': None, 'filename': None, 'lineno': None, 'name': None, 'qualname': None, 'module': None, 'imports': None, 'import_aliases': None}

    def __init__(self, fname, logger, metaast, results, testset):
        self.seen = 0
        self.fname = fname
        self.logger = logger
        self.metaast = metaast
        self.results = results
        self.testset = testset
        self.imports = set()
        self.context_template['imports'] = self.imports
        self.import_aliases = {}
        self.context_template['import_aliases'] = self.import_aliases
        self.tester = b_tester.BanditTester(self.logger, self.results, self.testset)

    def visit_Call(self, node):
        self.tester.test_call(node, name=self.qualname)
        if self.qualname == "":
            self.callbasenode = node
            self.qualname = b_utils.get_call_name(node)
        #nested calls
        if type(node.func) == _ast.Attribute:
            if type(node.func.value) == _ast.Call:
                self.qualname = ".".join([b_utils.get_call_name(node.func.value), self.qualname])
            else:
                self.calldone = True
        else:
            self.calldone = True

        self.context['qualname'] = self.qualname
        self.context['name'] = self.qualname.split('.')[-1]

        #done with nested
        if (self.calldone):
            self.logger.debug("PARSED COMPLETE qualname: %s" % self.qualname)
            self.logger.debug("\tBASENODE: %s" % ast.dump(self.callbasenode))
            file_detail = (self.fname, node.lineno)
            #store details on this obj
            self.tester.test_call_with_name(file_detail, self.qualname, self.callbasenode, self.imports, self.import_aliases)
            self.qualname = ""
            self.calldone = False
        self.tester.run_tests(self.context, 'Call')
        super(BanditNodeVisitor, self).generic_visit(node)

    def visit_Import(self, node):
        self.logger.debug("visit_Import called (%s)" % ast.dump(node))
        for nodename in node.names:
            if nodename.asname:
                self.context['import_aliases'][nodename.asname] = nodename.name
            self.context['imports'].add(nodename.name)
            self.context['module'] = nodename.name
        self.context['lineno'] = node.lineno
        self.tester.run_tests(self.context, 'Import')
        super(BanditNodeVisitor, self).generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module
        for nodename in node.names:
            if nodename.asname:
                self.context['import_aliases'][nodename.asname] = module + "." + nodename.name
            self.context['imports'].add(module + "." + nodename.name)
            self.context['module'] = module
            self.context['name'] = nodename.name
        self.context['lineno'] = node.lineno
        self.tester.run_tests(self.context, 'ImportFrom')
        super(BanditNodeVisitor, self).generic_visit(node)

    def visit(self, node):
        self.logger.debug(ast.dump(node))
        self.metaast.add_node(node, '', self.depth)
        self.context = copy.copy(self.context_template)
        self.context['node'] = node
        self.context['filename'] = self.fname
        self.seen += 1
        self.logger.debug("entering: %s %s [%s]" % (hex(id(node)), type(node), self.depth))
        self.depth += 1
        super(BanditNodeVisitor, self).visit(node)
        self.depth -= 1
        self.logger.debug("%s\texiting : %s" % (self.depth, hex(id(node))))

