# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import _SYSTEMS, _ENUM_ITEMS, _prop_name


def register():
    for key, (ifc_name, label, _, _) in _SYSTEMS.items():
        setattr(
            bpy.types.Scene,
            _prop_name(key),
            bpy.props.EnumProperty(
                name=f"Categoria {label}",
                description=ifc_name,
                items=_ENUM_ITEMS[key],
                default="",
            ),
        )

    if _SYSTEMS:
        bpy.types.Scene.cc_summary_system = bpy.props.EnumProperty(
            name="Sistema di classificazione",
            items=[(key, f"{key} – {ifc_name}", ifc_name) for key, (ifc_name, _, _, _) in _SYSTEMS.items()],
            default=next(iter(_SYSTEMS)),
        )


def unregister():
    for key in _SYSTEMS:
        prop = _prop_name(key)
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    if hasattr(bpy.types.Scene, "cc_summary_system"):
        del bpy.types.Scene.cc_summary_system
