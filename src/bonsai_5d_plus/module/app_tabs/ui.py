# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""Bonsai-style horizontal tab bar for the Bonsai5D+ sidebar.

Blender panels can only stack vertically, so the "tabs" are emulated: a single
top panel draws a row of icon toggle buttons backed by ``Scene.bonsai5d_tab``,
and every content panel gates its ``poll()`` on the active tab via
``tab_active``. Sub-panels follow their parent automatically.
"""

import bpy

# (identifier, label, description, Blender icon)
TABS = [
    ("COST",    "Cost",          "Cost item editor and classification",      "PROPERTIES"),
    ("RATES",   "Rates",         "Rate list / Schedule-of-Rates importer",   "LINENUMBERS_ON"),
    ("TENDERS", "Tenders",       "Tender schedules and comparison",          "COMMUNITY"),
    ("REPORTS", "Reports",       "PDF reports (prints manager)",             "FILE_TEXT"),
    ("IO",      "Import/Export", "XPWE import / export",                     "IMPORT"),
    ("SANDBOX", "Sandbox",       "Experimental / work-in-progress tools",    "GHOST_ENABLED"),
]

DEFAULT_TAB = TABS[0][0]


def tab_items():
    """EnumProperty items for ``Scene.bonsai5d_tab`` (with per-item icons)."""
    return [(ident, label, desc, icon, num)
            for num, (ident, label, desc, icon) in enumerate(TABS)]


def tab_active(context, tab):
    """True when ``tab`` is the active addon tab (defaults to the first one)."""
    return getattr(context.scene, "bonsai5d_tab", DEFAULT_TAB) == tab


class BONSAI5D_PT_main(bpy.types.Panel):
    bl_label = "Bonsai5D+"
    bl_idname = "SCENE_PT_bonsai5d_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_order = 0

    def draw(self, context):
        row = self.layout.row(align=True)
        for ident, _label, _desc, _icon in TABS:
            row.prop_enum(context.scene, "bonsai5d_tab", ident, text="")


classes = [BONSAI5D_PT_main]
