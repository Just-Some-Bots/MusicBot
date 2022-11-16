import ast
import builtins


ast_arg_type = ast.arg


def execfile(fn, global_vars=None, local_vars=None):
    with open(fn) as f:
        code = compile(f.read(), fn, "exec")
        exec(code, global_vars or {}, local_vars)


def get_ast_arg_arg(node):
    if isinstance(node, str):  # TODO: G21: Understand the Algorithm (Where it's used?)
        return node
    return node.arg


def get_ast_with_items(node):
    return node.items
