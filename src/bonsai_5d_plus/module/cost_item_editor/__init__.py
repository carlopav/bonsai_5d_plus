# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .prop import classes as _prop_classes
from .operator import (
    classes as _op_classes,
    _auto_load_handler,
    _resync_auto_load_on_undo,
    _remove_description_text,
)
from .ui import classes as _ui_classes
from . import prop

# RateAnalysisComponent must be registered before rate_analysis_components CollectionProperty
classes = _prop_classes + _op_classes + _ui_classes
class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    prop.register()
    if _auto_load_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_auto_load_handler)
    for hook in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _resync_auto_load_on_undo not in hook:
            hook.append(_resync_auto_load_on_undo)


def unregister():
    for hook in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _resync_auto_load_on_undo in hook:
            hook.remove(_resync_auto_load_on_undo)
    if _auto_load_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_auto_load_handler)
    _remove_description_text()
    prop.unregister()
    class_unregister()
