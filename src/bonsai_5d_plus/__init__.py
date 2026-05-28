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

bl_info = {
    "name": "Bonsai5D+",
    "author": "carlopav",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Rate List",
    "description": (
        "IFC cost management tools for Bonsai BIM: "
        "regional price list importer, rate analysis, BoQ-to-SoR conversion, bulk rate update."
    ),
    "category": "BIM",
}

import traceback

from .module import (
    rate_list,
    rate_analysis,
    boq_to_sor,
    bulk_update,
    classification,
    tender,
    svg_to_pdf,
    import_export,
)

_MODULES = [
    rate_list,
    rate_analysis,
    boq_to_sor,
    bulk_update,
    classification,
    tender,
    svg_to_pdf,
    import_export,
]


def register():
    for mod in _MODULES:
        try:
            mod.register()
            print(f"[Bonsai5D+] registered: {mod.__name__}")
        except Exception:
            print(f"[Bonsai5D+] FAILED to register: {mod.__name__}")
            traceback.print_exc()


def unregister():
    for mod in reversed(_MODULES):
        try:
            mod.unregister()
        except Exception:
            print(f"[Bonsai5D+] FAILED to unregister: {mod.__name__}")
            traceback.print_exc()
