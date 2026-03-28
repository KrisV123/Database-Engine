"""
This file is dedicated for parsers and interpret for mathematical exprations.
This was implemented for educational purposes, motivation behind the project
(trying to use only necessary modules), and security reasons (eval function
is unsafe and there is not known parser for me, that is safe and can interpret
more complex expretions)

RULES:
1, expretion must be written inside a string
2, between every terminal and nonterminal must be empty space except brackets
3, unary operator (-) must be written as (u-)
4, lists needs to have spaces after ',' character. For example
    [1,2,3] is wrong
    [1, 2, 3] is good
5, rest is same as in Python
6, every operator that can be used is written inside a op_order or assoc_side
   dictionary
"""

# TREBA ZMENIT TOKENIZER ZA LEXER!!!

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

op_order = {
    'or': 0,
    'and': 1,
    'in': 2,
    '==': 2,
    '!=': 2,
    '<': 2,
    '>': 2,
    '<=': 2,
    '>=': 2,
    'not': 3,
    '+': 4,
    '-': 4,
    '*': 5,
    '/': 5,
    '%': 5,
    '**': 6,
    'u-': 7
}

assoc_side = {
    'or': 'l',
    'and': 'l',
    'in': 'l',
    '==': 'l',
    '!=': 'l',
    '<': 'l',
    '>': 'l',
    '<=': 'l',
    '>=': 'l',
    'not': 'r',
    '+': 'l',
    '-': 'l',
    '*': 'l',
    '/': 'l',
    '%': 'l',
    '**': 'r',
    'u-': 'r'
}

op_funct: dict[str, Callable] = {
    'or': lambda x, y: x or y,
    'and': lambda x, y: x and y,
    'in': lambda x, y: x in y,
    '==': lambda x, y: x == y,
    '!=': lambda x, y: x != y,
    '<': lambda x, y: x < y,
    '>': lambda x, y: x > y,
    '<=': lambda x, y: x <= y,
    '>=': lambda x, y: x >= y,
    'not': lambda x: not x,
    '+': lambda x, y: x + y,
    '-': lambda x, y: x - y,
    '*': lambda x, y: x * y,
    '/': lambda x, y: x / y,
    '%': lambda x, y: x % y,
    '**': lambda x, y: x ** y,
    'u-': lambda x: -x,
}

def tokenize(string: str) -> list[str]:
    stack = list()
    indx = 0
    for ord, char in enumerate(string):
        if char in ['(', ')']:
            substr = string[indx:ord]
            stack.append(substr)
            stack.append(string[ord])
            indx = ord + 1

    stack.append(string[indx:len(string)])
    expr = [i for i in stack if i != '']

    tokens = list()
    for i in expr:
        if isinstance(i, str):
            words = i.split()
            tokens += words

    return tokens

def SJ_alg(tokens: list[str]) -> list[str]:
    op_stack: list[str] = list()
    output: list[str] = list()

    for token in tokens:
        if token in op_order.keys() or token in ('(', ')'):
            if token == '(' or len(op_stack) == 0:
                op_stack.append(token)
            elif token == ')':
                while op_stack[-1] != '(':
                    lst_op = op_stack.pop()
                    output.append(lst_op)
                if op_stack and op_stack[-1] == '(':
                    op_stack.pop()
            else:
                while op_stack and\
                      op_stack[-1] in op_order and\
                      (op_order[op_stack[-1]] > op_order[token] or\
                      (op_order[op_stack[-1]] == op_order[token] and\
                      assoc_side[token] == 'l')):
                    if not op_stack:
                        break
                    lst_op = op_stack.pop()
                    output.append(lst_op)
                op_stack.append(token)
        else:
            output.append(token)

    while len(op_stack) != 0:
        op = op_stack.pop()
        output.append(op)

    return output


@dataclass(slots=True, frozen=True)
class AST:
    pass


@dataclass(slots=True, frozen=True)
class BiOperator(AST):
    operator: str
    l_child: AST
    r_child: AST


@dataclass(slots=True, frozen=True)
class UnOperator(AST):
    operator: str
    child: AST


@dataclass(slots=True, frozen=True)
class Value(AST):
    value: str


def build_AST(prefix: list[str]) -> AST:
    stack: list[AST] = list()
    for i in prefix:
        if i not in op_order:
            stack.append(Value(i))
        elif assoc_side[i] == 'r':
            un_node = UnOperator(i, stack.pop())
            stack.append(un_node)
        else:
            lst1, lst2 = stack.pop(), stack.pop()
            bi_node = BiOperator(i, lst2, lst1)
            stack.append(bi_node)

    if len(stack) != 1:
        print(stack)
        raise SyntaxError('something went wrong during building AST')
    return stack[0]


@dataclass(slots=True, frozen=True)
class Evaluator:
    variables: dict[str, Any]

    def interpret(self, node: AST) -> int | float | str | bool | list | AST | None:
        if isinstance(node, Value):
            if node.value.isdigit():
                return int(node.value)
            elif is_float(node.value):
                return float(node.value)
            elif node.value.lower() == 'true':
                return True
            elif node.value.lower() == 'false':
                return False
            elif node.value[0] == '[' and node.value[-1] == ']':
                return [elem for elem in node.value if elem not in ['[', ']', ',', ' ']]
            elif node.value[0] == "'" and node.value[-1] == "'":
                return node.value[1:-1]
            elif node.value == 'None':
                return None
                """elif node.value in self.variables:
                return self.variables[node.value]"""
            else:
                return self.variables[node.value]

            raise AttributeError("leaf in AST want't recognized")

        elif isinstance(node, UnOperator):
            un_funct: Callable = op_funct[node.operator]
            return un_funct(self.interpret(node.child))

        elif isinstance(node, BiOperator):
            bi_funct: Callable = op_funct[node.operator]
            return bi_funct(
                self.interpret(node.l_child),
                self.interpret(node.r_child)
            )

        raise AssertionError(f"State {node} wasnt't catch")

def is_float(string: str) -> bool:
    try:
        float(string)
        return True
    except:
        return False

def interpret_expr(expr: str, variables: dict[str, Any]):
    llist = tokenize(expr)
    postfix = SJ_alg(llist)
    tree = build_AST(postfix)
    return Evaluator(variables).interpret(tree)


def _get_ast_values(ast: AST, acc: list[str]) -> list[str]:
    if isinstance(ast, BiOperator):
        acc = _get_ast_values(ast.l_child, acc)
        acc = _get_ast_values(ast.r_child, acc)

    if isinstance(ast, UnOperator):
        acc = _get_ast_values(ast.child, acc)

    if isinstance(ast, Value):
        acc.append(ast.value)
        return acc

    return acc

def get_values(ast: AST) -> list[str]:
    stack: list[str] = []
    _get_ast_values(ast, stack)
    return stack
