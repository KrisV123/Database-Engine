from evaluator import (
    Lexer, Parser, ConstantFolder, Evaluator,
    diagnose, nodes, EvaluatorError, atom_types
)
from database.core.types import AcceptTypes

def build_ast(expr: str) -> nodes:
    """
    Custom pipeline from safe_evaluator to build AST without type checking

    database engine does not have information about types
    """

    tokens = Lexer(expr).tokenize()

    if isinstance(tokens, Lexer.Failure):
        error_msg = diagnose(expr, tokens)
        raise EvaluatorError(error_msg)

    ast = Parser(tokens).parse()

    if isinstance(ast, Parser.Failure):
        error_msg = diagnose(expr, ast)
        raise EvaluatorError(error_msg)

    folded_ast = ConstantFolder().fold(ast)

    if isinstance(folded_ast, ConstantFolder.Failure):
        error_msg = diagnose(expr, folded_ast)
        raise EvaluatorError(error_msg)

    return folded_ast

def eval_ast(expr: str, ast: nodes, vars: dict[str, AcceptTypes]) -> atom_types:
    ans = Evaluator(vars).eval(ast)

    if isinstance(ans, Evaluator.Failure):
        error_msg = diagnose(expr, ans)
        raise EvaluatorError(error_msg)

    return ans
