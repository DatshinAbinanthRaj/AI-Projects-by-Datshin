"""Rule profile: the standard-specific numbers and shape formulas, kept as data.

The profile is a JSON file. Shape formulas are short arithmetic expressions such
as "A + B - 0.5*r - d". They are evaluated by a small, safe evaluator that only
accepts numbers, the names A-E, d and r, and the operators + - * / ( ).
Nothing in a profile file can run arbitrary code.
"""
from __future__ import annotations

import ast
import json
import math
import operator
import re
from dataclasses import dataclass

DIM_NAMES = ("A", "B", "C", "D", "E")
ALLOWED_NAMES = DIM_NAMES + ("d", "r")
_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv}
_COMPARATORS = {">=": operator.ge, "<=": operator.le}


class ProfileError(ValueError):
    """The profile file cannot be used. The message lists every problem found."""


class FormulaError(ValueError):
    pass


def parse_formula(text: str) -> ast.AST:
    """Parse an expression and reject anything that is not plain arithmetic."""
    try:
        tree = ast.parse(str(text), mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"cannot read formula '{text}'") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub)):
            continue
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            continue
        if isinstance(node, ast.Name) and node.id in ALLOWED_NAMES:
            continue
        raise FormulaError(f"formula '{text}' uses something that is not allowed "
                           f"(only numbers, {', '.join(ALLOWED_NAMES)} and + - * / are accepted)")
    return tree


def names_in(tree: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _eval(node: ast.AST, values: dict) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, values)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return float(values[node.id])
    if isinstance(node, ast.UnaryOp):
        return -_eval(node.operand, values)
    return _BIN_OPS[type(node.op)](_eval(node.left, values), _eval(node.right, values))


def evaluate(tree: ast.AST, values: dict) -> float:
    return _eval(tree, values)


@dataclass(frozen=True)
class Constraint:
    text: str
    left: ast.AST
    op: str
    right: ast.AST

    def holds(self, values: dict) -> bool:
        return _COMPARATORS[self.op](evaluate(self.left, values), evaluate(self.right, values))


def parse_constraint(text: str) -> Constraint:
    for op in _COMPARATORS:
        if op in text:
            left, right = text.split(op, 1)
            return Constraint(text, parse_formula(left.strip()), op, parse_formula(right.strip()))
    raise FormulaError(f"constraint '{text}' must contain >= or <=")


@dataclass(frozen=True)
class Shape:
    code: str
    description: str
    dimensions: tuple
    formula_text: str
    formula: ast.AST
    end_legs: tuple
    constraints: tuple


@dataclass(frozen=True)
class Profile:
    name: str
    length_rounding_mm: float
    cut_length_tolerance_mm: float
    max_bar_length_mm: float
    steel_density_kg_m3: float
    summary_weight_tolerance_pct: float
    bar_mark_pattern: str
    required_header_fields: tuple
    diameters: dict          # int diameter -> {"r": mm, "p": mm}
    shapes: dict             # "11" -> Shape

    def unit_weight(self, diameter_mm: float) -> float:
        """Theoretical bar weight in kg per metre from the steel density."""
        area_m2 = math.pi * (diameter_mm / 1000.0) ** 2 / 4.0
        return area_m2 * self.steel_density_kg_m3

    def round_up(self, length_mm: float) -> float:
        step = self.length_rounding_mm
        return math.ceil(round(length_mm / step, 6)) * step


_POSITIVE = ("length_rounding_mm", "max_bar_length_mm", "steel_density_kg_m3")
_NON_NEGATIVE = ("cut_length_tolerance_mm", "summary_weight_tolerance_pct")


def build_profile(raw: dict) -> Profile:
    """Validate a profile dictionary. All problems are reported together."""
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise ProfileError("profile must be a JSON object")

    def number(key, minimum, strict):
        value = raw.get(key)
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) \
            and (value > minimum if strict else value >= minimum)
        if not ok:
            problems.append(f"'{key}' must be a number {'greater than' if strict else 'of at least'} {minimum}")
            return 1.0
        return float(value)

    nums = {k: number(k, 0, True) for k in _POSITIVE}
    nums.update({k: number(k, 0, False) for k in _NON_NEGATIVE})

    pattern = raw.get("bar_mark_pattern", "^.+$")
    try:
        re.compile(pattern)
    except (re.error, TypeError):
        problems.append("'bar_mark_pattern' is not a valid regular expression")

    diameters: dict = {}
    raw_dia = raw.get("diameters")
    if not isinstance(raw_dia, dict) or not raw_dia:
        problems.append("'diameters' must list at least one bar size")
        raw_dia = {}
    for key, entry in raw_dia.items():
        try:
            dia = int(key)
            r = float(entry["min_former_radius_mm"])
            p = float(entry["min_end_projection_mm"])
            if dia <= 0 or r <= 0 or p <= 0:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            problems.append(f"diameter '{key}' needs positive min_former_radius_mm and min_end_projection_mm")
            continue
        diameters[dia] = {"r": r, "p": p}

    shapes: dict = {}
    raw_shapes = raw.get("shapes")
    if not isinstance(raw_shapes, dict) or not raw_shapes:
        problems.append("'shapes' must define at least one shape code")
        raw_shapes = {}
    for code, entry in raw_shapes.items():
        label = f"shape '{code}'"
        if not isinstance(entry, dict):
            problems.append(f"{label} must be an object")
            continue
        dims = entry.get("dimensions")
        if not isinstance(dims, list) or not dims or any(x not in DIM_NAMES for x in dims) \
                or len(set(dims)) != len(dims):
            problems.append(f"{label}: 'dimensions' must be a list of unique names from A-E")
            continue
        try:
            formula = parse_formula(entry.get("formula", ""))
            constraints = tuple(parse_constraint(c) for c in entry.get("constraints", []))
        except FormulaError as exc:
            problems.append(f"{label}: {exc}")
            continue
        used = names_in(formula)
        for con in constraints:
            used |= names_in(con.left) | names_in(con.right)
        undeclared = sorted(n for n in used if n in DIM_NAMES and n not in dims)
        if undeclared:
            problems.append(f"{label}: formula uses {', '.join(undeclared)} which is not in 'dimensions'")
            continue
        legs = entry.get("end_legs", [])
        if any(x not in dims for x in legs):
            problems.append(f"{label}: every end leg must be one of its dimensions")
            continue
        shapes[str(code)] = Shape(str(code), str(entry.get("description", "")), tuple(dims),
                                  str(entry["formula"]), formula, tuple(legs), constraints)

    if problems:
        raise ProfileError("invalid profile: " + "; ".join(problems))
    return Profile(
        name=str(raw.get("name", "unnamed profile")),
        length_rounding_mm=nums["length_rounding_mm"],
        cut_length_tolerance_mm=nums["cut_length_tolerance_mm"],
        max_bar_length_mm=nums["max_bar_length_mm"],
        steel_density_kg_m3=nums["steel_density_kg_m3"],
        summary_weight_tolerance_pct=nums["summary_weight_tolerance_pct"],
        bar_mark_pattern=pattern,
        required_header_fields=tuple(raw.get("required_header_fields", [])),
        diameters=diameters,
        shapes=shapes,
    )


def load_profile(path: str) -> Profile:
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise ProfileError(f"cannot open profile '{path}': {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"profile '{path}' is not valid JSON: {exc.msg}") from exc
    return build_profile(raw)
