#!/usr/bin/env python3
"""Convert JSONL file to JSON file."""

import argparse
import json
import sys


def convert_jsonl_to_json(input_path: str, output_path: str) -> None:
    """Read a JSONL file and write all objects to a JSON array."""
    objects = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                objects.append(json.loads(line))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(objects, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert JSONL to JSON")
    parser.add_argument("input", help="Input JSONL file path")
    args = parser.parse_args()

    input_path = args.input
    output_path = input_path.replace(".jsonl", ".json")
    if output_path == input_path:
        output_path = input_path + ".json"

    print(f"{input_path} -> {output_path}")
    convert_jsonl_to_json(input_path, output_path)


if __name__ == "__main__":
    main()
