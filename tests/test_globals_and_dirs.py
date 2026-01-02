import os

from app import globals as G


def test_ensure_instance_dirs_creates(tmp_path):
    inst = str(tmp_path / "instance")
    # ensure dirs do not exist
    assert not os.path.exists(inst)

    G.ensure_instance_dirs(inst)

    assert os.path.isdir(os.path.join(inst, "cache"))
    assert os.path.isdir(os.path.join(inst, "cache", "photos"))
    assert os.path.isdir(os.path.join(inst, "log"))
