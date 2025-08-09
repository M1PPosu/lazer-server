#!/usr/bin/env python3
"""
Script to remove ANSI escape codes from log files
"""

from __future__ import annotations

import re
import sys


def remove_ansi_codes(text):
    """
    Remove ANSI escape codes from text
    """
    # Regular expression to match ANSI escape codes
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def process_log_file(input_file, output_file=None):
    """
    Process log file and remove ANSI escape codes
    """
    if output_file is None:
        output_file = (
            input_file.replace(".log", "_clean.log")
            if ".log" in input_file
            else input_file + "_clean"
        )

    with open(input_file, "r", encoding="utf-8") as infile:
        content = infile.read()

    # Remove ANSI escape codes
    clean_content = remove_ansi_codes(content)

    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write(clean_content)

    print(f"Processed {input_file} -> {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remove_ansi.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    process_log_file(input_file, output_file)
