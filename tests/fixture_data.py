"""Author-written interface fixtures generated only in temporary directories."""

from pathlib import Path
import json
import tempfile


def dataset(root):
    root = Path(root)
    library = root / "library"
    case = root / "cases/tiny"
    library.mkdir(parents=True)
    case.mkdir(parents=True)
    (library / "u_rca8.v").write_text(
        "module u_rca8(input [7:0] a, input [7:0] b, output [8:0] u_rca8_out);\nendmodule\n"
    )
    (case / "netlist.v").write_text(
        "module tiny(input [7:0] a, input [7:0] b, output [1:0] y);\n"
        "wire [8:0] s;\n"
        "assign y = s[1:0];\n"
        "u_rca8 A0 (.a(a), .b(b), .u_rca8_out(s));\n"
        "endmodule\n"
    )
    for i, y in enumerate((3, 2), 1):
        (case / f"observations_{i:03d}.jsonl").write_text(
            "# "
            + json.dumps(dict(circuit="tiny"))
            + "\n"
            + json.dumps(dict(inputs=dict(a=hex(1), b=hex(2)), outputs=dict(y=hex(y))))
            + "\n"
        )
    return root


def partial_bus_model():
    from arithdiag.model import build_diagnostic_model

    with tempfile.TemporaryDirectory(prefix="arithdiag-fixture-") as directory:
        root = dataset(directory)
        return build_diagnostic_model(
            root / "cases/tiny/netlist.v",
            root / "cases/tiny/observations_001.jsonl",
            root / "library",
        )
