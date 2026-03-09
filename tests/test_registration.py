"""Registration tests mirroring the C++ Phantom_* CTest suite.

Each parametrised case runs an affine registration and then verifies quality
by composing the estimated transform with the known ground-truth rigid
transform (``phantom01_rigid.mat``) and measuring the Dice overlap between
the resliced source label image and the original source label image.

The test matrix exactly mirrors the greedy CTest definitions found in
``greedy/CMakeLists.txt``.

An additional deformable registration smoke-test is included, using the 2-D
longitudinal brain phantom data (``t1longi_2d_*``).
"""

import os
import pytest
import SimpleITK as sitk
import numpy as np

from picsl_greedy import GreedyRegistration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dice(img_a: sitk.Image, img_b: sitk.Image) -> float:
    """Compute generalised Dice overlap between two label images."""
    flt = sitk.LabelOverlapMeasuresImageFilter()
    # Cast to the same integer type
    a = sitk.Cast(img_a, sitk.sitkInt32)
    b = sitk.Cast(img_b, sitk.sitkInt32)
    flt.Execute(a, b)
    return flt.GetDiceCoefficient()


# ---------------------------------------------------------------------------
# Phantom affine registration tests
# ---------------------------------------------------------------------------

# Each entry: (test_id, fixed_idx, moving_idx, metric, dof, use_mask)
# Mirrors greedy CMakeLists.txt lines 444-454.
PHANTOM_CASES = [
    ("NMI_Affine_NoMask",  1, 2, "NMI",       12, False),
    ("NCC_Affine_Mask",    1, 3, "NCC 2x2x2", 12, True),
    ("WNCC_Affine_Mask",   1, 3, "WNCC 2x2x2",12, True),
    ("SSD_Rigid_NoMask",   1, 1, "SSD",         6, False),
    ("NMI_Rigid_NoMask",   1, 2, "NMI",         6, False),
    ("NCC_Rigid_NoMask",   1, 3, "NCC 2x2x2",   6, False),
    ("WNCC_Rigid_NoMask",  1, 3, "WNCC 2x2x2",  6, False),
    ("SSD_Sim_NoMask",     1, 1, "SSD",          6, False),
    ("NMI_Sim_NoMask",     1, 2, "NMI",          7, False),
    ("NCC_Sim_NoMask",     1, 3, "NCC 2x2x2",    7, False),
    ("WNCC_Sim_NoMask",    1, 3, "WNCC 2x2x2",   7, False),
]


@pytest.mark.parametrize(
    "test_id,fixed_idx,moving_idx,metric,dof,use_mask",
    PHANTOM_CASES,
    ids=[c[0] for c in PHANTOM_CASES],
)
def test_phantom_affine(data_root, test_id, fixed_idx, moving_idx, metric, dof, use_mask):
    """Affine registration on the greedy block-phantom dataset.

    After registering ``phantom0{fixed_idx}_fixed`` against
    ``phantom0{moving_idx}_moving``, the source label image is resliced
    through [estimated_affine, phantom01_rigid.mat].  The Dice overlap
    between the resliced result and the original source must exceed 0.92,
    matching the C++ ``RunPhantomTest`` threshold.
    """
    fixed_path  = os.path.join(data_root, f"phantom0{fixed_idx}_fixed.nii.gz")
    moving_path = os.path.join(data_root, f"phantom0{moving_idx}_moving.nii.gz")
    source_path = os.path.join(data_root, "phantom01_source.nii.gz")
    rigid_path  = os.path.join(data_root, "phantom01_rigid.mat")
    mask_path   = os.path.join(data_root, "phantom01_mask.nii.gz")

    for p in (fixed_path, moving_path, source_path, rigid_path):
        if not os.path.exists(p):
            pytest.skip(f"Required file not found: {p}")

    fixed  = sitk.ReadImage(fixed_path)
    moving = sitk.ReadImage(moving_path)
    source = sitk.ReadImage(source_path)
    mask   = sitk.ReadImage(mask_path) if use_mask else None

    gr = GreedyRegistration(dim=3)
    aff = gr.affine_register(
        fixed, moving,
        dof=dof,
        metric=metric,
        iterations="100x60x20",
        mask=mask,
    )

    # Reslice: source → (via phantom01_rigid.mat) → moving space →
    #          (via estimated affine) → fixed space.
    # If affine is accurate the result should closely match the source.
    resliced = gr.reslice(
        fixed, source,
        transforms=[aff.matrix, rigid_path],
        interpolation="LABEL 0.1vox",
    )

    dice = _dice(source, resliced)
    assert dice >= 0.92, (
        f"Phantom_{test_id}: Dice {dice:.4f} < 0.92 "
        f"(metric={metric}, dof={dof}, use_mask={use_mask})"
    )


# ---------------------------------------------------------------------------
# Deformable registration smoke test
# ---------------------------------------------------------------------------

def test_deformable_registration(data_root):
    """Deformable registration smoke test on 2-D longitudinal brain data.

    Registers ``t1longi_2d_fu.nii.gz`` onto ``t1longi_2d_bl.nii.gz`` and
    verifies that:
    - The returned warp has the same spatial size as the fixed image.
    - An inverse warp is returned when ``return_inverse=True``.
    - The resliced moving image is spatially consistent with the fixed.
    """
    bl_path = os.path.join(data_root, "t1longi_2d_bl.nii.gz")
    fu_path = os.path.join(data_root, "t1longi_2d_fu.nii.gz")

    for p in (bl_path, fu_path):
        if not os.path.exists(p):
            pytest.skip(f"Required file not found: {p}")

    fixed  = sitk.ReadImage(bl_path)
    moving = sitk.ReadImage(fu_path)

    gr = GreedyRegistration(dim=2)

    # Affine initialisation
    aff = gr.affine_register(
        fixed, moving,
        dof=6,
        metric="NMI",
        iterations="100x50x10",
    )
    assert aff.matrix is not None
    assert aff.matrix.shape == (3, 3)

    # Deformable with inverse
    result = gr.deformable_register(
        fixed, moving,
        metric="NCC 2x2x2",
        iterations="50x20",
        initial=aff.matrix,
        return_inverse=True,
    )
    assert result.warp is not None
    assert result.inverse_warp is not None

    # Warp spatial size should match fixed image
    assert result.warp.GetSize()[:2] == fixed.GetSize()[:2]

    # Resliced image should have the same size as fixed
    resliced = gr.reslice(fixed, moving, transforms=[result.warp, aff.matrix])
    assert resliced.GetSize() == fixed.GetSize()
