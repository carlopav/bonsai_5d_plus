# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""Schedule-wide rate sync audit/repair. See tool.cost for the underlying logic."""

import bpy

from ....tool.cost import (
    refresh_cost_ui,
    is_item_in_sync,
    align_item_to_rate,
    get_cost_item_children,
)

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


def _iter_schedule_items(file, schedule):
    import ifcopenshell.util.cost as cost_util
    out = []

    def rec(item):
        out.append(item)
        for child in get_cost_item_children(item):
            rec(child)

    for root in cost_util.get_root_cost_items(schedule):
        rec(root)
    return out


class CostSync_OT_AuditSchedule(bpy.types.Operator):
    """Report how many items in the active schedule are out of sync with their rate."""
    bl_idname = "bonsai5d.audit_schedule"
    bl_label = "Audit schedule sync"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        sid = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = file.by_id(int(sid))
        items = _iter_schedule_items(file, schedule)
        linked = [it for it in items if is_item_in_sync(it) is not None]
        out_of_sync = [it for it in linked if is_item_in_sync(it) is False]
        self.report(
            {"INFO"},
            f"{len(out_of_sync)} of {len(linked)} linked item(s) out of sync with their rate",
        )
        return {"FINISHED"}


class CostSync_OT_ResyncSchedule(*_IfcOperatorBase):
    """Re-align every linked item in the active schedule with its rate."""
    bl_idname = "bonsai5d.resync_schedule"
    bl_label = "Resync all rates in schedule"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        sid = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = file.by_id(int(sid))
        n = 0
        for item in _iter_schedule_items(file, schedule):
            if is_item_in_sync(item) is False:
                align_item_to_rate(tool, item)
                n += 1
        refresh_cost_ui(tool)
        self.report({"INFO"}, f"Re-synced {n} linked item(s)")


classes = [
    CostSync_OT_AuditSchedule,
    CostSync_OT_ResyncSchedule,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
