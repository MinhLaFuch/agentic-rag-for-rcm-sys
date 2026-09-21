# src/utils/tree.py
from pathlib import Path
from typing import Optional, Union

_IGNORE_LIST = {
    "__pycache__", ".ipynb_checkpoints", ".git", ".venv", "venv", "env",
    "node_modules", ".mypy_cache", ".pytest_cache", "Scripts", "Lib", "Include",
}


def _is_visible(path: Path, exts: Optional[set[str]], show_hidden: bool) -> bool:
    if path.name in _IGNORE_LIST:
        return False
    if not show_hidden and path.name.startswith("."):
        return False
    if path.is_file():
        return exts is None or path.suffix in exts
    # thư mục: nếu có lọc đuôi thì chỉ hiện khi bên trong có file khớp
    return exts is None or any(_is_visible(c, exts, show_hidden) for c in path.iterdir())


def generate_tree(
    dir_path: Union[str, Path],
    prefix: str = "",
    _is_root: bool = True,
    *,
    exts: Optional[set[str]] = None,
    show_hidden: bool = False,
    max_depth: Optional[int] = None,
    _depth: int = 0,
) -> None:
    """
    Print a directory tree.

    Args:
        exts: chỉ hiện file có đuôi trong tập này (vd {".py", ".ipynb"}).
              None = hiện tất cả file.
        show_hidden: hiện cả file/thư mục bắt đầu bằng "." (.gitkeep, .gitignore, ...).
        max_depth: giới hạn độ sâu (1 = chỉ con trực tiếp). None = không giới hạn.

    Usage:
        generate_tree("src")
        generate_tree("src", exts={".py", ".ipynb"}, max_depth=3)
    """
    path = Path(dir_path)
    if _is_root:
        print(".")
    if not path.is_dir():
        return
    if max_depth is not None and _depth >= max_depth:
        return

    items = sorted(
        (x for x in path.iterdir() if _is_visible(x, exts, show_hidden)),
        key=lambda x: (x.is_file(), x.name.lower()),
    )

    for index, item in enumerate(items):
        is_last = index == len(items) - 1
        connector = "└── " if is_last else "├── "
        print(prefix + connector + item.name)

        if item.is_dir():
            generate_tree(
                item,
                prefix + ("    " if is_last else "│   "),
                _is_root=False,
                exts=exts,
                show_hidden=show_hidden,
                max_depth=max_depth,
                _depth=_depth + 1,
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="In cây thư mục.")
    parser.add_argument("path", nargs="?", default=".", help="Thư mục gốc (mặc định: .)")
    parser.add_argument(
        "-e", "--ext", nargs="+", metavar="EXT",
        help="Chỉ hiện các đuôi này, vd: -e .py .ipynb (mặc định: hiện tất cả)",
    )
    parser.add_argument("-a", "--all", action="store_true", help="Hiện cả file/thư mục ẩn")
    parser.add_argument("-d", "--depth", type=int, help="Giới hạn độ sâu")
    args = parser.parse_args()

    exts = {e if e.startswith(".") else f".{e}" for e in args.ext} if args.ext else None
    generate_tree(args.path, exts=exts, show_hidden=args.all, max_depth=args.depth)