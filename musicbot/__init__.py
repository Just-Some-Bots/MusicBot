import argparse
import pathlib
import sys
from typing import Any, Dict, NoReturn, Union

BASE_WRITE_PATH: str = ""


def parse_write_base_arg() -> None:
    """
    Handles command line arguments for base directory early.
    """
    arg39: Dict[str, Any] = {}
    if sys.version_info >= (3, 9):
        arg39 = {"exit_on_error": False}

    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="",
        epilog="",
        usage="",
        add_help=False,
        allow_abbrev=False,
        **arg39,
    )

    # Make sure argparser does not exit or print.
    def _error(message: str) -> NoReturn:  # type: ignore[misc]
        print("Write Base Argument Error:  %s", message)

    ap.error = _error  # type: ignore[method-assign]

    ap.add_argument(
        "--write-dir",
        dest="global_writes_basedir",
        type=str,
        help="",
        default="",
    )

    args, _ = ap.parse_known_args()

    if args.global_writes_basedir:
        basedir = pathlib.Path(args.global_writes_basedir).resolve()
        basedir.mkdir(parents=True, exist_ok=True)
        set_write_base(basedir)


def set_write_base(base_path: Union[str, pathlib.Path]) -> None:
    """Update the base write path for musicbot"""
    global BASE_WRITE_PATH  # pylint: disable=global-statement
    BASE_WRITE_PATH = str(base_path)


def get_write_base() -> str:
    """Get the string version of the base write path."""
    return BASE_WRITE_PATH


def write_path(path: Union[str, pathlib.Path]) -> pathlib.Path:
    """
    Get a pathlib.Path object for path, with the global write base path if one was set.
    """
    if BASE_WRITE_PATH:
        return pathlib.Path(BASE_WRITE_PATH).resolve().joinpath(path)
    return pathlib.Path(path).resolve()
