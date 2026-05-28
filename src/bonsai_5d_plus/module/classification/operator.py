# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import _SYSTEMS, _prop_name, _set_code

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class CC_OT_SetCode(*_IfcOperatorBase):
    """Assign the selected classification code to the active cost item."""
    bl_idname = "cost_classification.set_code"
    bl_label = "Assign Classification"
    bl_options = {"REGISTER", "UNDO"}

    system: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        ifc_name, _, cats, _ = _SYSTEMS[self.system]
        code = getattr(context.scene, _prop_name(self.system), "")
        _set_code(file, cost_item, ifc_name, code, {c: n for c, n in cats})


class CC_OT_ClearCode(*_IfcOperatorBase):
    """Remove the classification from the active cost item."""
    bl_idname = "cost_classification.clear_code"
    bl_label = "Clear Classification"
    bl_options = {"REGISTER", "UNDO"}

    system: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        ifc_name, _, cats, _ = _SYSTEMS[self.system]
        _set_code(file, cost_item, ifc_name, "", {c: n for c, n in cats})


classes = [CC_OT_SetCode, CC_OT_ClearCode]
