# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.
#
# Bonsai5D+ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai5D+ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai5D+.  If not, see <http://www.gnu.org/licenses/>.

"""Shared helpers for decomposing an IFC quantity Formula ("n × l × w × h")
into up to 4 numeric factors. Pure functions (no bpy, no ifcopenshell), used
by both the XPWE exporter and the ODS schedule renderer.
"""

import re


def _num(v, places=6):
    """Format a number the PriMus way: plain decimal, trailing zeros trimmed."""
    try:
        f = round(float(v), places)
    except (TypeError, ValueError):
        return "0"
    if f == int(f):
        return str(int(f))
    return ("%.*f" % (places, f)).rstrip("0").rstrip(".")


def safe_eval(expr):
    """Evaluate a simple arithmetic expression (digits and + - * / . ( ) only).

    Returns a float, or None when the text isn't a safe numeric expression. '×'
    and ',' are normalised to '*' and '.' first.
    """
    e = (expr or "").replace("×", "*").replace(",", ".").strip()
    if not e or re.fullmatch(r"[\d\s+\-*/().]+", e) is None:
        return None
    try:
        return float(eval(e))  # safe: only the numeric charset above is allowed
    except Exception:
        return None


def split_formula(formula, value):
    """Map an IFC quantity Formula onto XPWE's 4 RGItem factors.

    Returns (PartiUguali, Lunghezza, Larghezza, HPeso, faithful). The standard
    case is the importer's "n × l × w × h" product of 1–4 factors: each goes in a
    column ('1'/empty → "", an expression keeps its text without the importer's
    protective parentheses) and ``faithful`` is True.

    For anything that can't be represented as ≤4 factors whose product equals the
    quantity value — more than four factors, a non-arithmetic formula, or a
    product that doesn't reconcile — we put the authoritative numeric value in
    PartiUguali (the row total is then always exact) and return faithful=False so
    the caller can keep the original formula visible in the row description.
    """
    f = (formula or "").strip()
    if f:
        parts = [p.strip() for p in f.split("×")]
        if 1 <= len(parts) <= 4:
            cells = []
            for p in parts:
                if p in ("", "1"):
                    cells.append("")
                else:
                    if p.startswith("(") and p.endswith(")"):
                        p = p[1:-1].strip()
                    cells.append(p)
            cells += [""] * (4 - len(cells))
            if any(cells):
                product = 1.0
                ok = True
                for c in cells:
                    if c == "":
                        continue
                    v = safe_eval(c)
                    if v is None:
                        ok = False
                        break
                    product *= v
                tol = max(1e-4, abs(float(value)) * 1e-6)
                if ok and abs(product - float(value)) <= tol:
                    return (cells[0], cells[1], cells[2], cells[3], True)
    return (_num(value), "", "", "", False)
