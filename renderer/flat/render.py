#!/usr/bin/env python3
"""Render a YAML profile as tab-separated paths and values."""

import argparse
from pathlib import Path
import sys

import yaml


class ProfileLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently losing values."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ValueError("A YAML mezőneveknek szövegnek kell lenniük.")
            if key in result:
                raise ValueError(f"Ismétlődő YAML-kulcs: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def scalar_text(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    # Keep each field on one physical line, suitable for copying into documents.
    return str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")


def flatten(value, path="", ancestors=frozenset()):
    if isinstance(value, (dict, list)):
        if id(value) in ancestors:
            raise ValueError("Ciklikus YAML-hivatkozás nem renderelhető.")
        ancestors = ancestors | {id(value)}
    if isinstance(value, dict):
        if not value and path:
            yield path, "{}"
        for key, child in value.items():
            yield from flatten(child, f"{path}.{key}" if path else key, ancestors)
    elif isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            yield path, ", ".join(scalar_text(item) for item in value)
        else:
            for index, child in enumerate(value):
                yield from flatten(child, f"{path}[{index}]", ancestors)
    else:
        yield path, scalar_text(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="A bemeneti YAML-profil útvonala")
    args = parser.parse_args()
    try:
        with args.input.open(encoding="utf-8") as source:
            profile = yaml.load(source, Loader=ProfileLoader)
        if not isinstance(profile, dict):
            raise ValueError("A bemenet gyökere YAML-objektum legyen.")
        content = "".join(f"{key}\t{value}\n" for key, value in flatten(profile))
        target = Path(__file__).resolve().parents[2] / "target" / "flat"
        target.mkdir(parents=True, exist_ok=True)
        output = target / f"{args.input.stem}.flat.txt"
        output.write_text(content, encoding="utf-8")
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Hiba: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
