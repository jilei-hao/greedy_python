"""LMShoot smoke tests.

The C++ ``lmshoot_test`` binary tests the internal Hamiltonian system
mathematics using a MATLAB regression file and is not directly callable from
Python.  Instead, these tests exercise the Python ``LMShootWrapper.fit``
interface end-to-end by running geodesic shooting on the 2-D point-set data
included in the greedy test suite.

Tests check that the call completes without exception and that the output VTK
file is produced.  They do **not** reproduce the numerical regression
(Hamiltonian derivatives) validated by the C++ binary.
"""

import os
import tempfile
import pytest

from picsl_greedy import LMShootWrapper


# ---------------------------------------------------------------------------
# lmshoot smoke tests
# ---------------------------------------------------------------------------

def test_lmshoot_2d_fit(data_root, tmp_path):
    """Smoke test: ``LMShootWrapper.fit`` on 2-D point-set data.

    Runs geodesic landmark shooting with the 2-D template and target VTK
    meshes included in the greedy test suite.  Verifies that the call
    completes without error and produces a non-empty output file.

    Parameters mirror the C++ ``lmshoot_test`` regression scenario:
    - 2-D problem (``-d 2``)
    - Kernel sigma 10 (``-s 10``)
    - 10 time steps (``-n 10``)
    - 100 gradient-descent iterations (``-i 100 0``)
    """
    template_path = os.path.join(data_root, "lmshoot", "shooting_test_2d_template.vtk")
    target_path   = os.path.join(data_root, "lmshoot", "shooting_test_2d_target.vtk")

    for p in (template_path, target_path):
        if not os.path.isfile(p):
            pytest.skip(f"Required file not found: {p}")

    output_path = str(tmp_path / "lmshoot_2d_result.vtk")

    cmd = (
        f"-d 2 "
        f"-m {template_path} {target_path} "
        f"-o {output_path} "
        f"-s 10 "
        f"-n 10 "
        f"-i 100 0"
    )

    lms = LMShootWrapper(dim=2)
    lms.fit(cmd)

    assert os.path.isfile(output_path), (
        f"lmshoot did not produce output file: {output_path}"
    )
    assert os.path.getsize(output_path) > 0, (
        f"lmshoot output file is empty: {output_path}"
    )


def test_lmshoot_3d_fit(data_root, tmp_path):
    """Smoke test: ``LMShootWrapper.fit`` on 3-D point-set data.

    Uses the 3-D sphere/box dataset from the greedy test suite.  Only checks
    that the call completes without error and produces a non-empty output.
    """
    template_path = os.path.join(data_root, "lmshoot", "shooting_test_3d_sphere_reduced.vtk")
    target_path   = os.path.join(data_root, "lmshoot", "shooting_test_3d_box.vtk")

    for p in (template_path, target_path):
        if not os.path.isfile(p):
            pytest.skip(f"Required file not found: {p}")

    output_path = str(tmp_path / "lmshoot_3d_result.vtk")

    cmd = (
        f"-m {template_path} {target_path} "
        f"-o {output_path} "
        f"-s 10 "
        f"-S 10 "
        f"-n 10 "
        f"-a V "
        f"-i 50 0"
    )

    lms = LMShootWrapper(dim=3)
    lms.fit(cmd)

    assert os.path.isfile(output_path), (
        f"lmshoot did not produce output file: {output_path}"
    )
    assert os.path.getsize(output_path) > 0, (
        f"lmshoot output file is empty: {output_path}"
    )
