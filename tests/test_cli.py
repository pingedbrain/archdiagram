"""Exit codes are the contract with an agent loop: 0 ok, 1 problems, 2 bad input."""

import json

from archdiagram.cli import main

OVERLAP = ("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0], label: a rather long service name }\n"
           "  b: { icon: ddb, at: [1, 0], label: another long service name }\n")


def write(tmp_path, text, name="s.yaml"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_check_exit_codes(empty_cache, tmp_path, capsys):
    assert main(["check", write(tmp_path, "title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n")]) == 0
    assert main(["check", write(tmp_path, OVERLAP)]) == 1
    assert main(["check", write(tmp_path, "title: [unclosed\n")]) == 2


def test_check_json_shape(empty_cache, tmp_path, capsys):
    main(["check", "--json", write(tmp_path, OVERLAP)])
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert set(out["problems"][0]) == {"kind", "element", "with", "box", "message", "suggestion"}


def test_render_refuses_overlaps_unless_forced(cache, tmp_path):
    spec = write(tmp_path, OVERLAP)
    out = tmp_path / "o.html"
    assert main(["render", spec, "-o", str(out)]) == 1 and not out.exists()
    assert main(["render", spec, "-o", str(out), "--force"]) == 0 and "<figure class=\"arch\">" in out.read_text()
