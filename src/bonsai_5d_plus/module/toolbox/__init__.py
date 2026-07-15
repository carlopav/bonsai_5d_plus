# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .ui import classes as _ui_classes
from . import boq_to_sor, bulk_update, reorder_schedule, rate_sync, cost_sync

classes = _ui_classes
class_register, class_unregister = bpy.utils.register_classes_factory(classes)

# cost_sync has no panel of its own (its operators are consumed by the Cost
# Item Editor and by rate_sync's Audit/Resync buttons) but lives here since
# it's a sync utility, same family as the rest of the toolbox.
_SUBMODULES = [boq_to_sor, bulk_update, reorder_schedule, rate_sync, cost_sync]


def register():
    class_register()  # ToolboxPanel first, so bl_parent_id resolves for its children
    for mod in _SUBMODULES:
        mod.register()


def unregister():
    for mod in reversed(_SUBMODULES):
        mod.unregister()
    class_unregister()
