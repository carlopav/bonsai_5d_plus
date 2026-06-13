# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""Shared Typst compilation helper for cost documents.

Every document export follows the same pattern: a temp dir receives a copy of
the whole `typst/` template package plus one or more CSV data files at its
root, a generated `main.typ` imports the right template module and renders, and
typst compiles it to PDF.

Templates read CSVs by root-absolute path ("/foo.csv"), so the CSV file name
passed to a template must start with "/".
"""

import os
import shutil
import tempfile

_TYPST_DIR = os.path.join(os.path.dirname(__file__), "typst")


def esc(s):
    """Escape a Python string for embedding inside a Typst string literal."""
    return (s or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ").replace("\r", "")


def typ_value(v):
    """Render a Python value as a Typst literal (bool, number or string)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + esc(str(v)) + '"'


def show_with(module, **kwargs):
    """Build a main.typ body that imports `module` and calls `project.with`.

    `module` is a template file name, e.g. "bill_of_quantities.typ".
    """
    body = f'#import "typst/{module}": *\n#show: project.with(\n'
    for key, value in kwargs.items():
        body += f"  {key}: {typ_value(value)},\n"
    body += ")\n"
    return body


def compile_document(body, csvs, output_path):
    """Compile a generated main.typ body to a PDF.

    `csvs` maps a root file name (e.g. "schedule.csv") to its CSV text; each is
    written at the temp-dir root and referenced from templates as "/<name>".
    """
    import typst

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(_TYPST_DIR, os.path.join(tmp, "typst"))
        for name, text in csvs.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as f:
                f.write(text)
        main_path = os.path.join(tmp, "main.typ")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(body)
        pdf_bytes = typst.compile(main_path)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
