import warnings
from importlib.metadata import PackageNotFoundError, version

__all__ = ("__version__", "VersionInfo", "version_info")

from typing import Literal, NamedTuple

try:
    __version__ = version("py-cord")
    print("Set version")
except PackageNotFoundError:
    # Package is not installed
    try:
        from setuptools_scm import get_version  # type: ignore[import]

        __version__ = get_version()
        print("set version")
    except ImportError:
        # setuptools_scm is not installed
        __version__ = "0.0.0"
        warnings.warn(
            "Package is not installed, and setuptools_scm is not installed. "
            f"As a fallback, {__name__}.__version__ will be set to {__version__}",
            RuntimeWarning,
            stacklevel=2,
        )


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal["development", "alpha", "beta", "candidate", "final"]
    serial: int


version_info: VersionInfo = VersionInfo(
    major=2, minor=2, micro=0, releaselevel="final", serial=0
)
