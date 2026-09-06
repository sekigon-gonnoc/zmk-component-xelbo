#!/usr/bin/env python3
"""Convert pin assignments from XIAO mapping to XELBO mapping.

Modes:
- persist: copy source tree to output tree, then convert in output tree.

Conversion rules:
- Keep <&xiao_d n ...> unchanged.
- Replace <&gpioN pin ...> according to mapping table.
- Replace NRF_PSEL(FUNC, port, pin) according to mapping table.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys
from dataclasses import dataclass


Pin = tuple[int, int]
PROFILE_NAME = "xiao_to_xelbo"


PINMAP_XIAO_TO_XELBO: dict[Pin, Pin] = {
    (0, 2): (0, 5),
    (0, 3): (0, 4),
    (0, 28): (0, 29),
    (0, 29): (0, 3),
    (0, 4): (0, 26),
    (0, 5): (0, 27),
    (1, 11): (1, 8),
    (1, 12): (0, 14),
    (1, 13): (0, 17),
    (1, 14): (0, 15),
    (1, 15): (0, 7),
    (0, 9): (1, 3),
    (0, 10): (0, 22),
}

GPIO_RE = re.compile(r"<\s*&gpio([01])\s+(\d+)(\b[^>]*)>")
NRF_PSEL_RE = re.compile(r"NRF_PSEL\(\s*([^,]+?)\s*,\s*([01])\s*,\s*(\d+)\s*\)")


@dataclass
class FileStats:
    path: pathlib.Path
    changed: bool
    gpio_replacements: int = 0
    nrf_psel_replacements: int = 0
    unmapped_refs: int = 0


@dataclass
class ConvertResult:
    files_seen: int = 0
    files_changed: int = 0
    gpio_replacements: int = 0
    nrf_psel_replacements: int = 0
    unmapped_refs: int = 0


def get_profile_map() -> dict[Pin, Pin]:
    return PINMAP_XIAO_TO_XELBO


def convert_text(text: str, pinmap: dict[Pin, Pin]) -> tuple[str, int, int, int]:
    gpio_count = 0
    nrf_count = 0
    unmapped = 0

    def repl_gpio(match: re.Match[str]) -> str:
        nonlocal gpio_count, unmapped
        port = int(match.group(1))
        pin = int(match.group(2))
        rest = match.group(3)
        mapped = pinmap.get((port, pin))
        if mapped is None:
            unmapped += 1
            return match.group(0)
        gpio_count += 1
        return f"<&gpio{mapped[0]} {mapped[1]}{rest}>"

    out = GPIO_RE.sub(repl_gpio, text)

    def repl_nrf(match: re.Match[str]) -> str:
        nonlocal nrf_count, unmapped
        func = match.group(1)
        port = int(match.group(2))
        pin = int(match.group(3))
        mapped = pinmap.get((port, pin))
        if mapped is None:
            unmapped += 1
            return match.group(0)
        nrf_count += 1
        return f"NRF_PSEL({func}, {mapped[0]}, {mapped[1]})"

    out = NRF_PSEL_RE.sub(repl_nrf, out)
    return out, gpio_count, nrf_count, unmapped


def should_process(path: pathlib.Path) -> bool:
    return path.suffix in {".dts", ".dtsi", ".overlay"}


def convert_tree(root: pathlib.Path, pinmap: dict[Pin, Pin], dry_run: bool) -> ConvertResult:
    result = ConvertResult()

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not should_process(path):
            continue

        result.files_seen += 1
        original = path.read_text(encoding="utf-8")
        converted, gpio_count, nrf_count, unmapped = convert_text(original, pinmap)

        changed = converted != original
        if changed and not dry_run:
            path.write_text(converted, encoding="utf-8")

        if changed:
            result.files_changed += 1
            result.gpio_replacements += gpio_count
            result.nrf_psel_replacements += nrf_count

        result.unmapped_refs += unmapped

    return result


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def symbolize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def _rename_entries(root: pathlib.Path, source_base: str, target_base: str, dry_run: bool) -> None:
    # Rename deepest entries first so directory renames do not invalidate child paths.
    entries = sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in entries:
        if source_base not in path.name:
            continue
        new_path = path.with_name(path.name.replace(source_base, target_base))
        if not dry_run:
            path.rename(new_path)


def _rewrite_text_content(path: pathlib.Path, source_base: str, target_base: str, requires_board: str | None, dry_run: bool) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    src_sym = symbolize(source_base)
    dst_sym = symbolize(target_base)

    out = text
    out = out.replace(source_base, target_base)
    out = out.replace(f"SHIELD_{src_sym}", f"SHIELD_{dst_sym}")

    if path.suffix in {".yml", ".yaml"} and path.name.endswith(".zmk.yml"):
        out = re.sub(rf"^id:\s*{re.escape(source_base)}\s*$", f"id: {target_base}", out, flags=re.MULTILINE)
        out = re.sub(rf"^name:\s*{re.escape(source_base)}\s*$", f"name: {target_base}", out, flags=re.MULTILINE)
        if requires_board:
            out = re.sub(r"^requires:.*$", f"requires: [{requires_board}]", out, flags=re.MULTILINE)

    if out != text and not dry_run:
        path.write_text(out, encoding="utf-8")


def rewrite_persist_tree(
    root: pathlib.Path,
    source_base: str,
    target_base: str,
    requires_board: str | None,
    dry_run: bool,
) -> None:
    if source_base != target_base:
        _rename_entries(root=root, source_base=source_base, target_base=target_base, dry_run=dry_run)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        _rewrite_text_content(
            path=path,
            source_base=source_base,
            target_base=target_base,
            requires_board=requires_board,
            dry_run=dry_run,
        )


def run(
    source_root: pathlib.Path,
    output_root: pathlib.Path,
    dry_run: bool,
    persist_source_base: str | None,
    persist_target_base: str | None,
    persist_requires_board: str | None,
) -> int:
    pinmap = get_profile_map()

    if not source_root.exists() or not source_root.is_dir():
        print(f"error: source-root is not a directory: {source_root}", file=sys.stderr)
        return 2

    source_resolved = source_root.resolve()
    output_resolved = output_root.resolve()
    in_place = source_resolved == output_resolved

    marker = output_root / f".pinmap-converted-{PROFILE_NAME}"
    if in_place and marker.exists():
        print(
            "pinmap-convert "
            f"mode=persist profile={PROFILE_NAME} source={source_root} output={output_root} "
            "skipped=already-converted"
        )
        return 0

    if not in_place:
        copy_tree(source_root, output_root)

    result = convert_tree(output_root, pinmap, dry_run=dry_run)

    source_base = persist_source_base or source_root.name
    target_base = persist_target_base or output_root.name
    rewrite_persist_tree(
        root=output_root,
        source_base=source_base,
        target_base=target_base,
        requires_board=persist_requires_board,
        dry_run=dry_run,
    )

    if in_place and not dry_run:
        marker.write_text("converted\n", encoding="utf-8")

    print(
        "pinmap-convert "
        f"mode=persist profile={PROFILE_NAME} "
        f"source={source_root} output={output_root} "
        f"files_seen={result.files_seen} files_changed={result.files_changed} "
        f"gpio_replacements={result.gpio_replacements} "
        f"nrf_psel_replacements={result.nrf_psel_replacements} "
        f"unmapped_refs={result.unmapped_refs}"
    )

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert XIAO pin assignments to XELBO mapping")
    p.add_argument("source_root", nargs="?", type=pathlib.Path, help="Directory to read from")
    p.add_argument("output_root", nargs="?", type=pathlib.Path, help="Directory to write converted files to")
    p.add_argument("--source-root", dest="source_root_opt", type=pathlib.Path, help="Directory to read from (long form)")
    p.add_argument("--output-root", dest="output_root_opt", type=pathlib.Path, help="Directory to write converted files to (long form)")
    p.add_argument("--persist-source-base", default="", help="Original shield base name for persist rename")
    p.add_argument("--persist-target-base", default="", help="Generated shield base name for persist rename")
    p.add_argument("--persist-requires-board", default="", help="Board name to set in generated zmk.yml requires")
    p.add_argument("--dry-run", action="store_true", help="Compute conversion without writing files")
    return p


def main() -> int:
    args = build_parser().parse_args()

    source_root = args.source_root_opt or args.source_root
    if source_root is None:
        print("error: source root is required", file=sys.stderr)
        return 2

    output_root = args.output_root_opt or args.output_root or source_root

    return run(
        source_root=source_root,
        output_root=output_root,
        dry_run=args.dry_run,
        persist_source_base=args.persist_source_base or None,
        persist_target_base=args.persist_target_base or None,
        persist_requires_board=args.persist_requires_board or None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
