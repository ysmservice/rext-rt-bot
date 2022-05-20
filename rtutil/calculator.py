# RT - Calculator

from typing import NoReturn

import ast
import operator

from jishaku.functools import executor_function


__all__ = (
    "OPERATORS", "NotSupported", "NotSupportedOperator", "NotSupportedValue",
    "CalculatorNodeVisitor", "calculate", "aiocalculate"
)


OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv
}
"対応している演算子の辞書です。"



class NotSupported(Exception):
    "対応していない演算子または文字が出てきた際に発生するエラーの基底クラスです。"
class NotSupportedOperator(NotSupported):
    "対応していない演算子があった場合に発生するエラーです。"
class NotSupportedValue(NotSupported):
    "対応していない値があった場合に発生するエラーです。"


class CalculatorNodeVisitor(ast.NodeVisitor):
    "危ないことされないように安全にした文字列から計算をするためのクラスです。"

    def visit_BinOp(self, node: ast.BinOp) -> int | float:
        try:
            return OPERATORS[type(node.op)](*( # type: ignore
                self.visit(self.validate_operator(operator))
                for operator in (node.left, node.right)
            ))
        except KeyError:
            raise NotSupportedOperator(node.op)

    def validate_operator(self, operator: ast.AST) -> ast.AST | NoReturn:
        if isinstance(operator, ast.BinOp | ast.Constant):
            return operator
        raise NotSupportedOperator(operator)

    def visit_Constant(self, node: ast.Constant) -> int | float:
        if isinstance(node.value, int | float):
            return node.value
        raise NotSupportedValue(node.value)

    def visit_Expr(self, node: ast.Expr) -> ast.BinOp | NoReturn:
        return self.visit(node.value)


def calculate(expression: str) -> int | float:
    "計算を行います。"
    return CalculatorNodeVisitor().visit(ast.parse(expression.strip()).body[0]) or 0


@executor_function
def aiocalculate(expression: str) -> int | float:
    "非同期で計算を行います。"
    return calculate(expression)


if __name__ == "__main__":
    print(calculate(input(">>> ")))