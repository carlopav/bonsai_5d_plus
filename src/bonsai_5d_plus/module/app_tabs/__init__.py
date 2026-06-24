# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .ui import classes, tab_items, DEFAULT_TAB

_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    bpy.types.Scene.bonsai5d_tab = bpy.props.EnumProperty(
        name="Bonsai5D+ Section",
        description="Active Bonsai5D+ section",
        items=tab_items(),
        default=DEFAULT_TAB,
    )
    _register()


def unregister():
    _unregister()
    del bpy.types.Scene.bonsai5d_tab
