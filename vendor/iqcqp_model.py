"""Parse the benchmark Verilog into a solver-neutral integer quadratic model.

This module reads circuit wiring and observations and builds weak-fault
component constraints with AB(c)=1 for faulty components. It does not solve them.
Unsupported Verilog is rejected rather than guessed.

Use build_diagnostic_model(netlist, observation, library_dir) from Python.
The registry specifies arithmetic semantics; gate logic is not reverse-engineered.
render_lp() returns LP text and an in-memory variable map.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


BENCHMARK = Path(os.environ.get("ARITHDIAG_DATASET_ROOT", str(Path(__file__).resolve().parents[1] / "data/benchmark"))).expanduser().resolve()
OPERATIONS = {
    "u_arrmul4": "multiply",
    "u_arrmul8": "multiply",
    "u_arrmul16": "multiply",
    "u_arrmul32": "multiply",
    "u_dadda_cla4": "multiply",
    "u_rca8": "add",
    "u_rca16": "add",
    "u_rca32": "add",
    "u_rca64": "add",
}
PORT_DECL = re.compile(r"(input|output)\s+\[(\d+):(\d+)\]\s+(\w+)\Z")
WIRE_DECL = re.compile(r"wire\s+\[(\d+):(\d+)\]\s+(\w+)\s*;\Z")
PART = re.compile(r"(\w+)\[(\d+)(?::(\d+))?\]\Z")
INSTANCE = re.compile(r"(u_\w+)\s+([MA]\w+)\s*\((.*)\)\s*;\Z")
CONNECTION = re.compile(r"\.(\w+)\(([^()]*)\)")
ZERO = re.compile(r"(\d+)'b0+\Z")


@dataclass(frozen=True)
class Signal:
    name: str
    width: int
    role: str


@dataclass(frozen=True)
class Ref:
    name: str
    low: int
    high: int

    @property
    def width(self) -> int:
        return self.high - self.low + 1


@dataclass(frozen=True)
class Expr:
    # A concatenation of (width, optional signal reference), most significant first.
    parts: tuple[tuple[int, Ref | None], ...]

    @property
    def width(self) -> int:
        return sum(width for width, _ in self.parts)


@dataclass(frozen=True)
class Assignment:
    target: Ref
    source: Expr
    line: int


@dataclass(frozen=True)
class Component:
    name: str
    module: str
    operation: str
    a: Expr
    b: Expr
    output: Ref
    line: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_comment(line: str) -> str:
    return line.partition("//")[0].strip()


def _parse_library(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"\bmodule\s+(\w+)\s*\((.*?)\)\s*;", text, re.S)
    if not match or match[1] != path.stem or match[1] not in OPERATIONS:
        raise ValueError(f"Unsupported library module: {path}")
    ports = {}
    for item in match[2].split(","):
        m = PORT_DECL.fullmatch(item.strip())
        if not m or int(m[3]) != 0:
            raise ValueError(f"Unsupported library port in {path}: {item}")
        ports[m[4]] = {"direction": m[1], "width": int(m[2]) + 1}
    output = path.stem + "_out"
    if set(ports) != {"a", "b", output} or [ports[n]["direction"] for n in ("a", "b", output)] != ["input", "input", "output"]:
        raise ValueError(f"Unexpected component ports: {path}")
    operation = OPERATIONS[path.stem]
    expected = max(ports["a"]["width"], ports["b"]["width"]) + 1 if operation == "add" else ports["a"]["width"] + ports["b"]["width"]
    if ports[output]["width"] != expected:
        raise ValueError(f"Unexpected result width: {path}")
    source = f"library/{path.name}" if path.parent.resolve() == (BENCHMARK / "library").resolve() else str(path)
    return {"name": path.stem, "operation": operation, "ports": ports,
            "source": source, "sha256": _sha256(path)}


def _parse_ref(text: str, signals: dict[str, Signal]) -> Ref:
    text = text.strip()
    match = PART.fullmatch(text)
    if match:
        name, high, low = match[1], int(match[2]), int(match[3] or match[2])
    elif re.fullmatch(r"\w+", text) and text in signals:
        name, high, low = text, signals[text].width - 1, 0
    else:
        raise ValueError(f"Unsupported signal reference: {text}")
    if name not in signals or low < 0 or high < low or high >= signals[name].width:
        raise ValueError(f"Out-of-range signal reference: {text}")
    return Ref(name, low, high)


def _parse_expr(text: str, signals: dict[str, Signal]) -> Expr:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        parts = []
        for item in text[1:-1].split(","):
            item = item.strip()
            zero = ZERO.fullmatch(item)
            if zero:
                parts.append((int(zero[1]), None))
            else:
                ref = _parse_ref(item, signals)
                parts.append((ref.width, ref))
        if not parts or any(width < 1 for width, _ in parts):
            raise ValueError(f"Invalid concatenation: {text}")
        return Expr(tuple(parts))
    ref = _parse_ref(text, signals)
    return Expr(((ref.width, ref),))


def _split_connections(text: str) -> dict[str, str]:
    matches = list(CONNECTION.finditer(text))
    rest = CONNECTION.sub("", text)
    if not matches or rest.strip(" ,\t") or len({m[1] for m in matches}) != len(matches):
        raise ValueError(f"Unsupported instance port list: {text}")
    return {m[1]: m[2].strip() for m in matches}


def _parse_top(path: Path, library: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Signal], list[Assignment], list[Component]]:
    text = path.read_text(encoding="utf-8")
    module = re.search(r"\bmodule\s+(\w+)\s*\((.*?)\)\s*;", text, re.S)
    if not module:
        raise ValueError(f"No module header: {path}")
    signals: dict[str, Signal] = {}
    for item in module[2].split(","):
        m = PORT_DECL.fullmatch(item.strip())
        if not m or int(m[3]) != 0 or m[4] in signals:
            raise ValueError(f"Unsupported top-level port: {item}")
        signals[m[4]] = Signal(m[4], int(m[2]) + 1, m[1])
    statements = text[module.end():]
    wires = []
    for number, raw in enumerate(statements.splitlines(), text[:module.end()].count("\n") + 1):
        line = _strip_comment(raw)
        if line.startswith("wire "):
            m = WIRE_DECL.fullmatch(line)
            if not m or int(m[2]) != 0 or m[3] in signals:
                raise ValueError(f"Unsupported wire on {path}:{number}: {line}")
            signals[m[3]] = Signal(m[3], int(m[1]) + 1, "wire")
            wires.append((number, line))
    assignments: list[Assignment] = []
    components: list[Component] = []
    for number, raw in enumerate(statements.splitlines(), text[:module.end()].count("\n") + 1):
        line = _strip_comment(raw)
        if not line or line == "endmodule" or (number, line) in wires:
            continue
        if line.startswith("assign "):
            match = re.fullmatch(r"assign\s+(.+?)\s*=\s*(.+?)\s*;", line)
            if not match:
                raise ValueError(f"Unsupported assign on {path}:{number}")
            target = _parse_ref(match[1], signals)
            source = _parse_expr(match[2], signals)
            if target.width != source.width:
                raise ValueError(f"Width mismatch on {path}:{number}")
            assignments.append(Assignment(target, source, number))
            continue
        match = INSTANCE.fullmatch(line)
        if match:
            module_name, name, raw_ports = match.groups()
            if module_name not in library or any(c.name == name for c in components):
                raise ValueError(f"Unknown or repeated component on {path}:{number}: {line}")
            ports = _split_connections(raw_ports)
            module_ports = library[module_name]["ports"]
            if set(ports) != set(module_ports):
                raise ValueError(f"Port mismatch on {path}:{number}: {line}")
            a, b = (_parse_expr(ports[n], signals) for n in ("a", "b"))
            output = _parse_ref(ports[module_name + "_out"], signals)
            if a.width > module_ports["a"]["width"] or b.width > module_ports["b"]["width"] or output.width != module_ports[module_name + "_out"]["width"]:
                raise ValueError(f"Component width mismatch on {path}:{number}")
            components.append(Component(name, module_name, library[module_name]["operation"], a, b, output, number))
            continue
        raise ValueError(f"Unsupported Verilog on {path}:{number}: {line}")
    if not components:
        raise ValueError(f"No components found in {path}")
    driven: dict[str, set[int]] = defaultdict(set)
    for ref in [a.target for a in assignments] + [c.output for c in components]:
        if signals[ref.name].role == "input":
            raise ValueError(f"Input driven by circuit: {ref.name}")
        bits = set(range(ref.low, ref.high + 1))
        if driven[ref.name] & bits:
            raise ValueError(f"Multiple drivers for {ref.name}")
        driven[ref.name].update(bits)
    for signal in signals.values():
        if signal.role != "input" and driven[signal.name] != set(range(signal.width)):
            raise ValueError(f"Undriven bits in {signal.name}")
    return module[1], signals, assignments, components


def _ref_json(ref: Ref) -> dict[str, Any]:
    return {"signal": ref.name, "low": ref.low, "high": ref.high}


def _expr_json(expr: Expr) -> dict[str, Any]:
    return {"width": expr.width, "parts": [{"width": width, "ref": _ref_json(ref) if ref else None} for width, ref in expr.parts]}


def _affine_ref(ref: Ref, segments: dict[str, list[tuple[int, int, str]]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for low, high, name in segments[ref.name]:
        if low >= ref.low and high <= ref.high:
            result[name] = 1 << (low - ref.low)
        elif high >= ref.low and low <= ref.high:
            raise ValueError(f"Slice does not align with segment: {ref}")
    if sum(high - low + 1 for low, high, _ in segments[ref.name] if low >= ref.low and high <= ref.high) != ref.width:
        raise ValueError(f"Incomplete reference: {ref}")
    return result


def _affine_expr(expr: Expr, segments: dict[str, list[tuple[int, int, str]]]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    offset = 0
    for width, ref in reversed(expr.parts):
        if ref:
            for name, coefficient in _affine_ref(ref, segments).items():
                result[name] += coefficient << offset
        offset += width
    return dict(result)


def _polynomial(*affine: tuple[int, dict[str, int]], product: tuple[dict[str, int], dict[str, int]] | None = None) -> dict[str, Any]:
    linear: dict[str, int] = defaultdict(int)
    quadratic: dict[tuple[str, str], int] = defaultdict(int)
    for sign, terms in affine:
        for name, coefficient in terms.items():
            linear[name] += sign * coefficient
    if product:
        left, right = product
        for a, ac in left.items():
            for b, bc in right.items():
                quadratic[tuple(sorted((a, b)))] -= ac * bc
    return {"sense": "eq", "rhs": 0,
            "linear": [{"var": name, "coef": coefficient} for name, coefficient in sorted(linear.items()) if coefficient],
            "quadratic": [{"vars": list(pair), "coef": coefficient} for pair, coefficient in sorted(quadratic.items()) if coefficient]}


def build_model(netlist: Path, library_dir: Path | None = None) -> dict[str, Any]:
    """Build an exact healthy arithmetic model from a supported top-level netlist.

    Variables are bounded integer slices. Each constraint is a polynomial
    equality with linear and optional quadratic terms. Outputs are symbolic;
    observations can be attached by a later diagnostic layer.
    """
    netlist = Path(netlist).resolve()
    library_dir = Path(library_dir or BENCHMARK / "library").resolve()
    library = {path.stem: _parse_library(path) for path in sorted(library_dir.glob("*.v"))}
    if not library:
        raise ValueError(f"No library modules in {library_dir}")
    module, signals, assignments, components = _parse_top(netlist, library)
    cuts = {name: {0, signal.width} for name, signal in signals.items()}
    for ref in [a.target for a in assignments] + [c.output for c in components]:
        cuts[ref.name].update((ref.low, ref.high + 1))
    for expr in [a.source for a in assignments] + [e for c in components for e in (c.a, c.b)]:
        for _, ref in expr.parts:
            if ref:
                cuts[ref.name].update((ref.low, ref.high + 1))
    segments: dict[str, list[tuple[int, int, str]]] = {}
    variables = []
    for signal in signals.values():
        bounds = sorted(cuts[signal.name])
        pieces = []
        for low, end in zip(bounds, bounds[1:]):
            high = end - 1
            name = signal.name if len(bounds) == 2 else f"{signal.name}[{high}:{low}]"
            pieces.append((low, high, name))
            width = end - low
            variables.append({"name": name, "signal": signal.name, "bits": [high, low],
                              "role": signal.role, "type": "binary" if width == 1 else "integer",
                              "lb": 0, "ub": (1 << width) - 1})
        segments[signal.name] = pieces
    constraints = []
    for assignment in assignments:
        target = _affine_ref(assignment.target, segments)
        source = _affine_expr(assignment.source, segments)
        constraints.append({"name": f"wire_line_{assignment.line}", "kind": "wiring",
                            "line": assignment.line, "target": _ref_json(assignment.target),
                            "source": _expr_json(assignment.source),
                            **_polynomial((1, target), (-1, source))})
    for component in components:
        out = _affine_ref(component.output, segments)
        a = _affine_expr(component.a, segments)
        b = _affine_expr(component.b, segments)
        poly = _polynomial((1, out), product=(a, b)) if component.operation == "multiply" else _polynomial((1, out), (-1, a), (-1, b))
        constraints.append({"name": f"healthy_{component.name}", "kind": "healthy_component",
                            "component": component.name, "line": component.line, **poly})
    try:
        netlist_label = netlist.relative_to(BENCHMARK).as_posix()
    except ValueError:
        netlist_label = str(netlist)
    used_library = {name: library[name] for name in sorted({component.module for component in components})}
    return {
        "schema": "mbd-iqcqp-healthy-model-v1", "circuit": netlist.parent.name,
        "top_module": module, "netlist": netlist_label, "netlist_sha256": _sha256(netlist),
        "library": used_library,
        "ports": [{"name": s.name, "direction": s.role, "width": s.width,
                   "segments": [{"name": n, "high": h, "low": l} for l, h, n in segments[s.name]]}
                  for s in signals.values() if s.role in {"input", "output"}],
        "variables": variables,
        "components": [{"name": c.name, "module": c.module, "operation": c.operation,
                        "a": _expr_json(c.a), "b": _expr_json(c.b),
                        "output": _ref_json(c.output), "line": c.line} for c in components],
        "constraints": constraints,
    }


def _observation_values(path: Path, model: dict[str, Any]) -> dict[str, int]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if len(lines) != 2 or not lines[0].startswith("# "):
        raise ValueError(f"Expected one fault header and one observation: {path}")
    header, row = json.loads(lines[0][2:]), json.loads(lines[1])
    if header.get("circuit") != model["circuit"] or set(row) != {"inputs", "outputs"}:
        raise ValueError(f"Observation does not match circuit: {path}")
    values = {}
    for direction, key in (("input", "inputs"), ("output", "outputs")):
        ports = [port for port in model["ports"] if port["direction"] == direction]
        data = row[key]
        if set(data) == {port["name"] for port in ports}:
            for port in ports:
                value = data[port["name"]]
                if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
                    raise ValueError(f"Invalid hexadecimal observation: {path}:{port['name']}")
                values[port["name"]] = int(value, 16)
        else:
            expected = {f"{port['name']}[{bit}]" for port in ports for bit in range(port["width"])}
            if set(data) != expected:
                raise ValueError(f"Observation port bits do not match: {path}")
            for port in ports:
                bits = [data[f"{port['name']}[{bit}]"] for bit in range(port["width"])]
                if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
                    raise ValueError(f"Invalid bit observation: {path}:{port['name']}")
                values[port["name"]] = sum(bit << index for index, bit in enumerate(bits))
        for port in ports:
            if not 0 <= values[port["name"]] < 1 << port["width"]:
                raise ValueError(f"Observation outside port width: {path}:{port['name']}")
    return values


def _polynomial_bounds(constraint: dict[str, Any], variables: dict[str, dict[str, Any]]) -> tuple[int, int]:
    lower = upper = 0
    for item in constraint["linear"]:
        variable = variables[item["var"]]
        coefficient = item["coef"]
        lower += coefficient * (variable["lb"] if coefficient >= 0 else variable["ub"])
        upper += coefficient * (variable["ub"] if coefficient >= 0 else variable["lb"])
    for item in constraint["quadratic"]:
        a, b = (variables[name] for name in item["vars"])
        coefficient = item["coef"]
        low_product, high_product = a["lb"] * b["lb"], a["ub"] * b["ub"]
        lower += coefficient * (low_product if coefficient >= 0 else high_product)
        upper += coefficient * (high_product if coefficient >= 0 else low_product)
    return lower, upper


def build_observation_model(healthy_model: dict[str, Any], observation: Path) -> dict[str, Any]:
    """Attach one observation and weak faults, with AB(c)=1 meaning faulty."""
    model = copy.deepcopy(healthy_model)
    port_values = _observation_values(observation, model)
    model["schema"] = "mbd-iqcqp-observation-model-v1"
    model["observation"] = Path(observation).name
    model["observed_ports"] = port_values
    model["fault_header_used_as_constraints"] = False
    variables = {variable["name"]: variable for variable in model["variables"]}
    observed_segments = {}
    for port in model["ports"]:
        whole = port_values[port["name"]]
        for segment in port["segments"]:
            name, low, high = segment["name"], segment["low"], segment["high"]
            value = (whole >> low) & ((1 << (high - low + 1)) - 1)
            observed_segments[name] = value
            variables[name]["lb"] = variables[name]["ub"] = value
    new_constraints = []
    for constraint in model["constraints"]:
        if constraint["kind"] == "wiring":
            new_constraints.append(constraint)
            continue
        if constraint["kind"] != "healthy_component":
            raise ValueError(f"Unexpected base constraint: {constraint['name']}")
        component = constraint["component"]
        abnormal = f"AB_{component}"
        lower, upper = _polynomial_bounds(constraint, variables)
        m_positive, m_negative = max(0, upper), max(0, -lower)
        for side, sign, big_m in (("pos", 1, m_positive), ("neg", -1, m_negative)):
            linear = [{"var": term["var"], "coef": sign * term["coef"]} for term in constraint["linear"]]
            if big_m:
                linear.append({"var": abnormal, "coef": -big_m})
            quadratic = [{"vars": term["vars"], "coef": sign * term["coef"]} for term in constraint["quadratic"]]
            new_constraints.append({"name": f"guard_{side}_{component}", "kind": "guarded_component",
                                    "component": component, "abnormal": abnormal, "big_m": big_m,
                                    "sense": "le", "rhs": 0, "linear": linear, "quadratic": quadratic})
    for component in model["components"]:
        abnormal = f"AB_{component['name']}"
        if abnormal in variables:
            raise ValueError(f"Duplicate abnormality variable: {abnormal}")
        variable = {"name": abnormal, "signal": component["name"], "bits": [0, 0],
                    "role": "abnormal", "type": "binary", "lb": 0, "ub": 1}
        model["variables"].append(variable)
        variables[abnormal] = variable
    for name, value in observed_segments.items():
        new_constraints.append({"name": f"observe_{name}", "kind": "observation",
                                "sense": "eq", "rhs": value,
                                "linear": [{"var": name, "coef": 1}], "quadratic": []})
    model["constraints"] = new_constraints
    model["objective"] = {"sense": "min", "linear": [{"var": f"AB_{c['name']}", "coef": 1}
                                                   for c in model["components"]]}
    return model


def build_diagnostic_model(netlist: Path, observation: Path, library_dir: Path | None = None) -> dict[str, Any]:
    """Public interface: parse a circuit and one observation into an IQCQP."""
    return build_observation_model(build_model(netlist, library_dir), observation)


def _lp_terms(terms: list[tuple[int, str]]) -> str:
    if not terms:
        return "0"
    pieces = []
    for index, (coefficient, expression) in enumerate(terms):
        sign = "-" if coefficient < 0 else "+"
        magnitude = abs(coefficient)
        value = expression if magnitude == 1 else f"{magnitude} {expression}"
        pieces.append(("- " if coefficient < 0 else "") + value if index == 0 else f" {sign} {value}")
    return "".join(pieces)


def render_lp(model: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Render an observed component-level IQCQP as an LP file.

    Returns LP text and a stable map from LP-safe names to model signal slices.
    The model already contains its objective and observation constraints.
    """
    producer = {c["output"]["signal"]: (c["operation"], c["name"]) for c in model["components"]}
    variable_names = {}
    used_lp_names = set()
    for variable in model["variables"]:
        if variable["role"] == "abnormal":
            lp_name = variable["name"]
        else:
            signal = variable["signal"]
            if variable["role"] == "input":
                prefix = "i"
            elif variable["role"] == "output":
                prefix = "o"
            elif signal in producer:
                operation, component = producer[signal]
                prefix = f"{'m' if operation == 'multiply' else 'a'}_{component}"
            else:
                prefix = "w"
            high, low = variable["bits"]
            segment = "" if variable["name"] == signal else f"_{high}_{low}"
            lp_name = f"{prefix}_{signal}{segment}"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", lp_name):
            raise ValueError(f"Invalid LP variable name: {lp_name}")
        if lp_name in used_lp_names:
            raise ValueError(f"Duplicate LP variable name: {lp_name}")
        used_lp_names.add(lp_name)
        variable_names[variable["name"]] = lp_name
    label_names = {c["name"]: "c_" + re.sub(r"[^A-Za-z0-9_]", "_", c["name"])
                   for c in model["constraints"]}
    if len(variable_names) != len(model["variables"]) or len(label_names) != len(model["constraints"]) or len(set(label_names.values())) != len(label_names):
        raise ValueError("Duplicate model variable or constraint name")
    objective = model.get("objective")
    objective_terms = [(item["coef"], variable_names[item["var"]]) for item in objective["linear"]] if objective else []
    objective_sense = objective["sense"] if objective else "min"
    if objective_sense not in ("min", "max"):
        raise ValueError(f"Unknown objective sense: {objective_sense}")
    lines = ["\\ Component-level IQCQP model", "Maximize" if objective_sense == "max" else "Minimize",
             f"  obj: {_lp_terms(objective_terms)}", "Subject To"]
    for constraint in model["constraints"]:
        linear = [(item["coef"], variable_names[item["var"]]) for item in constraint["linear"]]
        quadratic = []
        for item in constraint["quadratic"]:
            left, right = (variable_names[name] for name in item["vars"])
            quadratic.append((item["coef"], f"{left} * {right}"))
        lhs = _lp_terms(linear)
        if quadratic:
            lhs += f" + [ {_lp_terms(quadratic)} ]"
        sense = {"eq": "=", "le": "<=", "ge": ">="}[constraint["sense"]]
        lines.append(f"  {label_names[constraint['name']]}: {lhs} {sense} {constraint['rhs']}")
    lines.append("Bounds")
    for variable in model["variables"]:
        lines.append(f"  {variable['lb']} <= {variable_names[variable['name']]} <= {variable['ub']}")
    binaries = [v for v in model["variables"] if v["type"] == "binary"]
    generals = [v for v in model["variables"] if v["type"] == "integer"]
    if binaries:
        lines.append("Binaries")
        lines.extend(f"  {variable_names[v['name']]}" for v in binaries)
    if generals:
        lines.append("Generals")
        lines.extend(f"  {variable_names[v['name']]}" for v in generals)
    lines.append("End")
    mapping = {"schema": "mbd-iqcqp-lp-map-v1", "circuit": model["circuit"],
               "netlist_sha256": model["netlist_sha256"],
               "observation": model.get("observation"),
               "variables": [{"lp_name": variable_names[v["name"]], **v} for v in model["variables"]],
               "constraints": [{"lp_name": label_names[c["name"]], "name": c["name"],
                                "kind": c["kind"]} for c in model["constraints"]],
               "ports": model["ports"], "objective": objective}
    return "\n".join(lines) + "\n", mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a circuit and observation into a component-level IQCQP")
    parser.add_argument("netlist", type=Path, nargs="?", help="path to a case netlist.v")
    parser.add_argument("--library", type=Path, default=BENCHMARK / "library")
    parser.add_argument("--output", type=Path, help="output path; default is stdout")
    parser.add_argument("--observation", type=Path, help="one observation JSONL file")
    parser.add_argument("--all", action="store_true", help="generate an IQCQP LP for every case observation")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "results" / "models" / "iqcqp")
    parser.add_argument("--format", choices=("json", "lp"), help="default: infer .lp output, otherwise JSON")
    args = parser.parse_args()
    if args.all:
        if args.netlist or args.observation or args.output or args.format:
            parser.error("--all cannot be combined with a single netlist, observation, output, or format")
        count = 0
        for netlist in sorted((BENCHMARK / "cases").glob("*/netlist.v")):
            healthy = build_model(netlist, args.library)
            observations = sorted(netlist.parent.glob("observations_*.jsonl"))
            if not observations:
                raise ValueError(f"No observations found for {netlist.parent.name}")
            for observation in observations:
                model = build_observation_model(healthy, observation)
                data, _ = render_lp(model)
                target = args.output_dir / netlist.parent.name / (observation.stem + ".lp")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(data, encoding="utf-8")
                count += 1
        if not count:
            raise ValueError("No observation models found")
        print(f"Generated {count} observed IQCQP LP files in {args.output_dir}")
        return
    if not args.netlist:
        parser.error("netlist is required unless --all is used")
    model = build_diagnostic_model(args.netlist, args.observation, args.library) if args.observation else build_model(args.netlist, args.library)
    output_format = args.format or ("lp" if args.output and args.output.suffix.lower() == ".lp" else "json")
    if output_format == "lp" and not args.observation:
        parser.error("LP output requires --observation; use --all for the full dataset")
    if output_format == "lp":
        data, _ = render_lp(model)
    else:
        data = json.dumps(model, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
