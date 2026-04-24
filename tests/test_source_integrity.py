import ast
from pathlib import Path


def test_matcher_has_single_po_box_result_implementation() -> None:
    source = Path("src/ukrposhta_address_matcher/matcher.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    matcher_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AddressMatcher"
    )
    method_names = [node.name for node in matcher_class.body if isinstance(node, ast.FunctionDef)]

    assert method_names.count("_build_po_box_result") == 1
