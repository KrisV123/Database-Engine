from evaluator.interpreter.stages import ( #type:ignore
    Lexer, Parser, ConstantFolder
)

def build_ast(expr: str):
    """
    Custom pipeline from safe_evaluator to build AST without type checking
    """

    tokens = Lexer(expr).tokenize()
    ast = Parser(tokens).parse()

    if isinstance(ast, Parser.Failure):
        raise RuntimeError(ast)

    folded_ast = ConstantFolder().fold(ast)

    return folded_ast
