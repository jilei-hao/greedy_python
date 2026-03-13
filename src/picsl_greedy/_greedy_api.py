"""
High-level, Python-friendly wrappers around the picsl_greedy C++ bindings.

Each method call is **stateless**: a fresh internal C++ instance is created
per call and all outputs are returned directly.  No image data is cached
between calls, which keeps memory usage predictable.

Examples
--------
Affine registration::

    from picsl_greedy import GreedyRegistration
    import SimpleITK as sitk

    g = GreedyRegistration(dim=3)
    fixed  = sitk.ReadImage("fixed.nii.gz")
    moving = sitk.ReadImage("moving.nii.gz")

    result = g.affine_register(fixed, moving, dof=6, metric="NMI")
    print("Affine matrix:\\n", result.matrix)

    warp, log = g.deformable_register(fixed, moving, initial=result.matrix)
    resliced   = g.reslice(fixed, moving, [warp, result.matrix])
    sitk.WriteImage(resliced, "resliced.nii.gz")

Propagation::

    from picsl_greedy import PropagationWrapper
    prop = PropagationWrapper()
    out  = prop.run(img4d, seg3d, ref_tp=5, target_tps=[1, 2, 3, 4])
    sitk.WriteImage(out["seg4d"], "seg4d.nii.gz")
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _as_arg(obj: Any, kwargs: dict) -> str:
    """Return a CLI token for *obj* and, if needed, register it in *kwargs*.

    - ``str``  → returned unchanged (treated as a file path by greedy).
    - anything else  → assigned a unique label that is stored in *kwargs*
      so the underlying C++ wrapper can map it to the in-memory object.
      Works for ``sitk.Image``, ``np.ndarray`` (affine matrices), and
      ``None`` (output placeholder).
    """
    if isinstance(obj, str):
        return obj
    label = f"_arg_{uuid.uuid4().hex[:8]}"
    kwargs[label] = obj
    return label


# ---------------------------------------------------------------------------
# Named-tuple result types
# ---------------------------------------------------------------------------

try:
    from typing import NamedTuple
except ImportError:  # Python < 3.6 fallback (unlikely given requires-python ≥ 3.8)
    from typing_extensions import NamedTuple  # type: ignore[assignment]


class AffineResult(NamedTuple):
    """Return value of :meth:`GreedyRegistration.affine_register`.

    Attributes
    ----------
    matrix : np.ndarray
        RAS-space affine transform as a ``(dim+1) × (dim+1)`` matrix.
    metric_log : list of dict
        Optimisation metric values, one dict per resolution level.  Each
        dict has keys ``TotalPerPixelMetric``, ``ComponentPerPixelMetrics``,
        and ``MaskVolume`` (each a 1-D numpy array over iterations).
    """
    matrix: Any
    metric_log: List


class DeformableResult(NamedTuple):
    """Return value of :meth:`GreedyRegistration.deformable_register`.

    Attributes
    ----------
    warp : sitk.Image
        Displacement field mapping fixed → moving.
    metric_log : list of dict
        Same structure as :attr:`AffineResult.metric_log`.
    inverse_warp : sitk.Image or None
        Inverse displacement field (moving → fixed), only present when
        ``return_inverse=True`` was passed to :meth:`~GreedyRegistration.deformable_register`.
    """
    warp: Any
    metric_log: List
    inverse_warp: Optional[Any] = None


# ---------------------------------------------------------------------------
# GreedyRegistration
# ---------------------------------------------------------------------------

class GreedyRegistration:
    """Pythonic interface to the Greedy deformable image registration tool.

    Each public method creates a **fresh** internal Greedy instance, runs the
    requested operation, and returns all outputs directly.  Nothing is cached
    across calls.

    Parameters
    ----------
    dim : {2, 3}
        Image dimensionality.
    float_precision : bool
        Use single-precision (float32) internally instead of double.
    threads : int, optional
        Number of CPU threads; ``None`` lets Greedy use its own default.
    """

    def __init__(
        self,
        dim: int = 3,
        float_precision: bool = False,
        threads: Optional[int] = None,
    ) -> None:
        if dim not in (2, 3):
            raise ValueError(f"dim must be 2 or 3, got {dim!r}")
        self._dim = dim
        self._float = float_precision
        self._threads = threads

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_api(self):
        from . import _picsl_greedy as _pg
        table = {
            (2, False): _pg.Greedy2D,
            (3, False): _pg.Greedy3D,
            (2, True):  _pg.GreedyFloat2D,
            (3, True):  _pg.GreedyFloat3D,
        }
        return table[(self._dim, self._float)]()

    def _thread_flag(self) -> str:
        return f"-threads {self._threads}" if self._threads is not None else ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def affine_register(
        self,
        fixed,
        moving,
        *,
        dof: int = 12,
        metric: str = "NMI",
        iterations: str = "100x50x10",
        mask=None,
        initial=None,
    ) -> AffineResult:
        """Affine (or rigid) registration of *moving* into *fixed*.

        Parameters
        ----------
        fixed, moving : str or sitk.Image
            Fixed and moving images.  Strings are treated as file paths.
        dof : {6, 7, 12}
            Degrees of freedom: 6 = rigid, 7 = similarity, 12 = full affine.
        metric : str
            Similarity metric, e.g. ``'NMI'``, ``'NCC 2x2x2'``, ``'SSD'``.
        iterations : str
            Multi-resolution iteration schedule, e.g. ``'100x50x10'``.
        mask : str or sitk.Image, optional
            Fixed-space mask image (passed via ``-gm``).
        initial : str or np.ndarray, optional
            Initial transform (file path or ``(dim+1)×(dim+1)`` numpy matrix).

        Returns
        -------
        AffineResult
            Named tuple with ``matrix`` (np.ndarray) and ``metric_log`` (list).
        """
        kw: Dict[str, Any] = {}
        fixed_arg  = _as_arg(fixed,  kw)
        moving_arg = _as_arg(moving, kw)
        out_label  = "_affine_out"
        kw[out_label] = None

        parts = [
            f"-i {fixed_arg} {moving_arg}",
            f"-a -dof {dof}",
            f"-n {iterations}",
            f"-m {metric}",
            f"-o {out_label}",
        ]
        if mask is not None:
            parts.append(f"-gm {_as_arg(mask, kw)}")
        if initial is not None:
            parts.append(f"-it {_as_arg(initial, kw)}")
        parts.append(self._thread_flag())

        cmd = " ".join(p for p in parts if p)
        api = self._make_api()
        api.execute(cmd, **kw)
        return AffineResult(matrix=api[out_label], metric_log=api.metric_log())

    def deformable_register(
        self,
        fixed,
        moving,
        *,
        metric: str = "NCC 2x2x2",
        iterations: str = "100x50x10",
        smooth_pre: str = "2vox",
        smooth_post: str = "0.5vox",
        initial=None,
        return_inverse: bool = False,
    ) -> DeformableResult:
        """Deformable (greedy / LDDMM) registration of *moving* into *fixed*.

        Parameters
        ----------
        fixed, moving : str or sitk.Image
            Fixed and moving images.  Strings are treated as file paths.
        metric : str
            Similarity metric, e.g. ``'NCC 2x2x2'``, ``'NMI'``, ``'SSD'``.
        iterations : str
            Multi-resolution iteration schedule, e.g. ``'100x50x10'``.
        smooth_pre : str
            Pre-smoothing sigma, e.g. ``'2vox'`` or ``'2.0mm'``.
        smooth_post : str
            Post-smoothing sigma, e.g. ``'0.5vox'`` or ``'0.5mm'``.
        initial : str or np.ndarray, optional
            Initial affine transform used as the starting point.
        return_inverse : bool
            When ``True``, also compute and return the inverse warp field.

        Returns
        -------
        DeformableResult
            Named tuple with ``warp`` (sitk.Image), ``metric_log`` (list), and
            ``inverse_warp`` (sitk.Image or ``None``).
        """
        kw: Dict[str, Any] = {}
        fixed_arg  = _as_arg(fixed,  kw)
        moving_arg = _as_arg(moving, kw)
        warp_label = "_warp_out"
        kw[warp_label] = None

        inv_label: Optional[str] = None
        parts = [
            f"-i {fixed_arg} {moving_arg}",
            f"-n {iterations}",
            f"-m {metric}",
            f"-s {smooth_pre} {smooth_post}",
            f"-o {warp_label}",
        ]
        if initial is not None:
            parts.append(f"-it {_as_arg(initial, kw)}")
        if return_inverse:
            inv_label = "_inv_out"
            kw[inv_label] = None
            parts.append(f"-oinv {inv_label}")
        parts.append(self._thread_flag())

        cmd = " ".join(p for p in parts if p)
        api = self._make_api()
        api.execute(cmd, **kw)
        return DeformableResult(
            warp=api[warp_label],
            metric_log=api.metric_log(),
            inverse_warp=api[inv_label] if inv_label is not None else None,
        )

    def reslice(
        self,
        fixed,
        moving,
        transforms: Sequence = (),
        *,
        interpolation: str = "LINEAR",
    ):
        """Reslice *moving* into the space of *fixed* using a chain of transforms.

        Parameters
        ----------
        fixed : str or sitk.Image
            Reference image defining the output space.
        moving : str or sitk.Image
            Image to be resliced.
        transforms : sequence of (str, np.ndarray, or sitk.Image)
            Transforms applied in order from first to last (left-to-right
            composition), e.g. ``[warp_field, affine_matrix]``.  Strings are
            file paths; numpy arrays are affine matrices; SimpleITK images are
            displacement fields.  Pass an empty sequence (the default) to
            reslice with the identity transform.
        interpolation : str
            Interpolation mode: ``'LINEAR'``, ``'NN'``, ``'SINC'``, or
            ``'LABEL <sigma>'``.

        Returns
        -------
        sitk.Image
            The resliced image.
        """
        kw: Dict[str, Any] = {}
        fixed_arg  = _as_arg(fixed,  kw)
        moving_arg = _as_arg(moving, kw)
        out_label  = "_resliced_out"
        kw[out_label] = None

        parts = [
            f"-rf {fixed_arg}",
            f"-ri {interpolation}",
            f"-rm {moving_arg} {out_label}",
        ]
        if transforms:
            transform_args = [_as_arg(t, kw) for t in transforms]
            parts.append(f"-r {' '.join(transform_args)}")
        parts.append(self._thread_flag())

        cmd = " ".join(p for p in parts if p)
        api = self._make_api()
        api.execute(cmd, **kw)
        return api[out_label]


# ---------------------------------------------------------------------------
# PropagationWrapper
# ---------------------------------------------------------------------------

class PropagationWrapper:
    """Pythonic interface to the Greedy Propagation tool.

    Propagates a 3D segmentation from a reference time point to all target
    time points in a 4D image.

    Parameters
    ----------
    float_precision : bool
        Use single-precision (float32) computation.
    """

    def __init__(self, float_precision: bool = False) -> None:
        self._float = float_precision

    def _make_api(self):
        from . import _picsl_greedy as _pg
        return _pg.PropagationFloat() if self._float else _pg.Propagation()

    def run(
        self,
        img4d,
        seg_ref,
        ref_tp: int,
        target_tps: Sequence[int],
        *,
        seg_is_4d: bool = False,
        output_dir: Optional[str] = None,
        metric: str = "SSD",
        iterations: str = "100x100",
        smooth_pre: str = "3mm",
        smooth_post: str = "1.5mm",
        dof: int = 12,
        threads: Optional[int] = None,
        verbosity: int = 1,
    ) -> Dict[str, Any]:
        """Run segmentation propagation and return results in memory.

        Parameters
        ----------
        img4d : str or sitk.Image
            4D input image.
        seg_ref : str or sitk.Image
            Reference segmentation.  Treated as 3D (``-sr3``) by default;
            set *seg_is_4d* to use a 4D segmentation (``-sr4``).
        ref_tp : int
            Index of the reference time point (1-based).
        target_tps : sequence of int
            Target time point indices to propagate to.
        seg_is_4d : bool
            When ``True``, *seg_ref* is a 4D image and ``-sr4`` is used.
        output_dir : str, optional
            If given, write output segmentations to this directory as well.
        metric : str
            Similarity metric: ``'SSD'``, ``'NCC'``, or ``'NMI'``.
        iterations : str
            Multi-resolution iteration schedule, e.g. ``'100x100'``.
        smooth_pre : str
            Pre-smoothing sigma, e.g. ``'3mm'``.
        smooth_post : str
            Post-smoothing sigma, e.g. ``'1.5mm'``.
        dof : int
            Affine degrees of freedom used during internal registration.
        threads : int, optional
            Number of CPU threads.
        verbosity : int
            Verbosity level (0 = silent, 1 = normal, 2 = verbose).

        Returns
        -------
        dict
            Keys: ``'seg4d'`` (full 4D segmentation as ``sitk.Image``) and
            ``'seg_NN'`` for each propagated time point NN (zero-padded to
            two digits), e.g. ``'seg_01'``, ``'seg_03'``.
        """
        kw: Dict[str, Any] = {}
        img4d_arg = _as_arg(img4d,   kw)
        seg_arg   = _as_arg(seg_ref, kw)

        tps_str  = ",".join(str(t) for t in target_tps)
        sr_flag  = "-sr4" if seg_is_4d else "-sr3"

        parts = [
            f"-i {img4d_arg}",
            f"{sr_flag} {seg_arg}",
            f"-tpr {ref_tp}",
            f"-tpt {tps_str}",
            f"-n {iterations}",
            f"-m {metric}",
            f"-s {smooth_pre} {smooth_post}",
            f"-dof {dof}",
            f"-verbose {verbosity}",
        ]
        if output_dir is not None:
            parts.append(f"-o {output_dir}")
        if threads is not None:
            parts.append(f"-threads {threads}")

        cmd = " ".join(parts)
        api = self._make_api()
        api.run(cmd, **kw)

        result: Dict[str, Any] = {}
        seg4d = api["seg4d"]
        if seg4d is not None:
            result["seg4d"] = seg4d
        for tp in api.get_time_points():
            key = f"seg_{tp:02d}"
            seg = api[key]
            if seg is not None:
                result[key] = seg
        return result


# ---------------------------------------------------------------------------
# LMShootWrapper
# ---------------------------------------------------------------------------

class LMShootWrapper:
    """Pythonic interface to the PICSL lmshoot landmark geodesic shooting tool.

    This is a thin stateless delegate — each call creates a fresh internal
    instance.  Because the lmshoot CLI has many specialised options, the
    full command string is still accepted here.

    Parameters
    ----------
    dim : {2, 3}
        Image / point-set dimensionality.
    float_precision : bool
        Use single-precision (float32) computation.
    """

    def __init__(self, dim: int = 3, float_precision: bool = False) -> None:
        if dim not in (2, 3):
            raise ValueError(f"dim must be 2 or 3, got {dim!r}")
        self._dim = dim
        self._float = float_precision

    def _make_api(self):
        from . import _picsl_greedy as _pg
        table = {
            (2, False): _pg.LMShoot2D,
            (3, False): _pg.LMShoot3D,
            (2, True):  _pg.LMShootFloat2D,
            (3, True):  _pg.LMShootFloat3D,
        }
        return table[(self._dim, self._float)]()

    def fit(self, command: str, **kwargs) -> None:
        """Fit a geodesic trajectory via landmark shooting.

        Parameters
        ----------
        command : str
            Full ``lmshoot`` command-line argument string.
        **kwargs
            In-memory objects (``sitk.Image`` or ``np.ndarray``) substituted
            for filename tokens in *command*.
        """
        self._make_api().fit(command, **kwargs)

    def apply(self, command: str, **kwargs) -> None:
        """Apply a fitted geodesic to generate a warp field.

        Parameters
        ----------
        command : str
            Full ``lmtowarp`` command-line argument string.
        **kwargs
            In-memory objects substituted for filename tokens in *command*.
        """
        self._make_api().apply(command, **kwargs)


# ---------------------------------------------------------------------------
# MultiChunkGreedyWrapper
# ---------------------------------------------------------------------------

class MultiChunkGreedyWrapper:
    """Pythonic interface to the PICSL multi-chunk greedy registration tool.

    This is a thin stateless delegate — each call creates a fresh internal
    instance.

    Parameters
    ----------
    dim : {2, 3}
        Image dimensionality.
    """

    def __init__(self, dim: int = 3) -> None:
        if dim not in (2, 3):
            raise ValueError(f"dim must be 2 or 3, got {dim!r}")
        self._dim = dim

    def _make_api(self):
        from . import _picsl_greedy as _pg
        return _pg.MultiChunkGreedy3D() if self._dim == 3 else _pg.MultiChunkGreedy2D()

    def run(self, command: str, **kwargs) -> None:
        """Run multi-chunk greedy registration.

        Parameters
        ----------
        command : str
            Full multi-chunk greedy command-line argument string.
        **kwargs
            In-memory objects substituted for filename tokens in *command*.
        """
        self._make_api().run(command, **kwargs)
