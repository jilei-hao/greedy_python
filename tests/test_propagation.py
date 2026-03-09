"""Propagation tests mirroring the C++ ``propagation_basic`` CTest.

The test propagates a reference segmentation (time point 5) to all other
time points in a 4-D brain image using the same parameters as the C++ test:
- Rigid registration (dof=6)
- SSD metric
- 10×10 multi-resolution schedule

Quality is verified by comparing against the pre-computed ground-truth 4-D
segmentation ``propagation/seg4d_resliced.nii.gz`` using Dice ≥ 0.9 per time
point (matching the C++ ``propagation_basic`` acceptance criterion).
"""

import os
import pytest
import SimpleITK as sitk

from picsl_greedy import PropagationWrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dice_per_label(pred: sitk.Image, ref: sitk.Image) -> float:
    """Return the global Dice coefficient between two label images."""
    flt = sitk.LabelOverlapMeasuresImageFilter()
    flt.Execute(sitk.Cast(pred, sitk.sitkInt32), sitk.Cast(ref, sitk.sitkInt32))
    return flt.GetDiceCoefficient()


def _extract_tp(img4d: sitk.Image, tp_index: int) -> sitk.Image:
    """Extract a single 3-D volume from a 4-D SimpleITK image by index."""
    extractor = sitk.ExtractImageFilter()
    size = list(img4d.GetSize())
    size[3] = 0                       # collapse the 4th dimension
    extractor.SetSize(size)
    index = [0, 0, 0, tp_index]
    extractor.SetIndex(index)
    return extractor.Execute(img4d)


# ---------------------------------------------------------------------------
# propagation_basic
# ---------------------------------------------------------------------------

def test_propagation_basic(data_root):
    """Mirrors the C++ ``propagation_basic`` CTest.

    Propagates ``propagation/seg05.nii.gz`` from reference time point 5 to
    target time points [1, 2, 3, 4, 6, 7] using rigid registration and SSD
    metric.  Each propagated segmentation is compared against the
    corresponding slice in ``propagation/seg4d_resliced.nii.gz`` with a
    minimum Dice of 0.9.
    """
    img4d_path = os.path.join(data_root, "propagation", "img4d.nii.gz")
    seg_path   = os.path.join(data_root, "propagation", "seg05.nii.gz")
    ref4d_path = os.path.join(data_root, "propagation", "seg4d_resliced.nii.gz")

    for p in (img4d_path, seg_path, ref4d_path):
        if not os.path.exists(p):
            pytest.skip(f"Required file not found: {p}")

    img4d  = sitk.ReadImage(img4d_path)
    seg_ref = sitk.ReadImage(seg_path)
    ref4d  = sitk.ReadImage(ref4d_path)

    target_tps = [1, 2, 3, 4, 6, 7]

    prop = PropagationWrapper()
    result = prop.run(
        img4d, seg_ref,
        ref_tp=5,
        target_tps=target_tps,
        metric="SSD",
        iterations="10x10",
        dof=6,
    )

    # Verify all expected keys are present and contain valid images
    assert "seg4d" in result, "Missing 'seg4d' in propagation output"
    for tp in target_tps:
        key = f"seg_{tp:02d}"
        assert key in result, f"Missing key '{key}' in propagation output"
        seg_tp = result[key]
        assert isinstance(seg_tp, sitk.Image), f"seg_{tp:02d} is not a sitk.Image"
        assert sitk.GetArrayFromImage(seg_tp).max() > 0, (
            f"seg_{tp:02d} is empty (all zeros)"
        )

    # Compare each propagated segmentation against the ground-truth slice
    # (time points 1-7, 0-based index = tp - 1)
    for tp in target_tps:
        pred = result[f"seg_{tp:02d}"]
        gt   = _extract_tp(ref4d, tp - 1)   # ref4d is 1-indexed in time
        dice = _dice_per_label(pred, gt)
        assert dice >= 0.9, (
            f"Propagation to tp={tp}: Dice {dice:.4f} < 0.9 vs ground truth"
        )
