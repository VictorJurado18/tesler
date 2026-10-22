"""Batch rename."""
import os
from pathlib import Path

import pytest

from dragshift import renamer
from dragshift.util import UserError


def files(tmp_path: Path, names):
    out = []
    for i, n in enumerate(names):
        p = tmp_path / n
        p.write_text(n)
        os.utime(p, (1_700_000_000 + i * 86400,) * 2)
        out.append(p)
    return out


def test_plan_numbering_and_order(tmp_path):
    fs = files(tmp_path, ["b.jpg", "a.jpg", "c.png"])
    pairs = renamer.plan(fs, "Viagem {n}", start=1, order="name")
    assert [(o.name, n.name) for o, n in pairs] == [("a.jpg", "Viagem 01.jpg"), ("b.jpg", "Viagem 02.jpg"),
                                                    ("c.png", "Viagem 03.png")]
    pairs = renamer.plan(fs, "{date} {name}", order="date")
    assert pairs[0][1].name.endswith(" b.jpg") and pairs[0][1].name[:4] == "2023"


def test_problems(tmp_path):
    fs = files(tmp_path, ["a.txt", "b.txt", "taken.txt"])
    pairs = [(fs[0], tmp_path / "x.txt"), (fs[1], tmp_path / "x.txt")]
    assert set(renamer.problems(pairs).values()) == {"duplicate name"}
    assert renamer.problems([(fs[0], tmp_path / "a?.txt")])
    assert renamer.problems([(fs[0], tmp_path / "taken.txt")]) == {0: "a file with this name already exists"}
    assert renamer.problems([(fs[0], tmp_path / "CON.txt")])


def test_apply_swap_and_undo(tmp_path):
    a, b = files(tmp_path, ["a.txt", "b.txt"])
    done = renamer.apply([(a, b), (b, a)])            # swap names
    assert (tmp_path / "a.txt").read_text() == "b.txt" and (tmp_path / "b.txt").read_text() == "a.txt"
    renamer.undo(done)
    assert (tmp_path / "a.txt").read_text() == "a.txt"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt", "b.txt"]


def test_apply_refuses_problems(tmp_path):
    a, b = files(tmp_path, ["a.txt", "b.txt"])
    with pytest.raises(UserError):
        renamer.apply([(a, tmp_path / "x.txt"), (b, tmp_path / "x.txt")])
    assert a.exists() and b.exists()
