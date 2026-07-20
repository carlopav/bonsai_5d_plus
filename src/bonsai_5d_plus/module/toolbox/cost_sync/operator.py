# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""Operators that keep CME/BoQ items in sync with their EPU/Schedule-of-Rates
rate (one-way EPU -> CME). See tool.cost for the underlying logic."""

import bpy

from ....tool.cost import (
    refresh_cost_ui,
    get_rate_dependents,
    group_dependents_by_schedule,
    rate_dependent_diffs,
    resync_rate_values,
    propagate_rate_to_dependents,
    align_item_to_rate,
)

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


def _resolve_item(context, item_id):
    """Resolve an IfcCostItem from an explicit id, else the editor target, else
    the Bonsai active cost item. Returns (item, file) — item may be None."""
    from bonsai import tool
    file = tool.Ifc.get()
    if file is None:
        return None, None
    if not item_id:
        editor = getattr(context.scene, "bonsai5d_cost_editor", None)
        item_id = getattr(editor, "rate_analysis_target_ifc_id", 0)
    if not item_id:
        props = context.scene.BIMCostProperties
        if props.active_cost_item is not None:
            item_id = props.active_cost_item.ifc_definition_id
    if not item_id:
        return None, file
    try:
        return file.by_id(int(item_id)), file
    except Exception:
        return None, file


def _diff_label(diffs):
    order = [("name", "Name"), ("description", "Description"), ("value", "Cost value")]
    return ", ".join(label for key, label in order if key in diffs)


def schedule_propagate_popup(rate_id):
    """Pop the propagation dialog right after the current operator finishes.

    Using a 0-delay timer avoids invoking a UI operator from inside another
    operator's IFC transaction. The dialog cancels itself silently if the rate
    has no out-of-sync dependents.
    """
    def _cb():
        try:
            bpy.ops.bonsai5d.propagate_rate("INVOKE_DEFAULT", rate_id=rate_id)
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_cb, first_interval=0.01)
    except Exception:
        pass


class CostSync_OT_PropagateRate(*_IfcOperatorBase):
    """Propagate this rate's Name/Description (and optionally Identification) to
    the cost items it controls, and re-share its cost values."""
    bl_idname = "bonsai5d.propagate_rate"
    bl_label = "Propagate rate changes to linked items"
    bl_options = {"REGISTER", "UNDO"}

    rate_id: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    should_update_identification: bpy.props.BoolProperty(
        name="Should update Identification",
        default=False,
        description="Also overwrite each linked item's Identification with the rate's",
    )

    def invoke(self, context, event):
        rate, _file = _resolve_item(context, self.rate_id)
        if rate is None:
            self.report({"ERROR"}, "No rate cost item resolved")
            return {"CANCELLED"}
        self.rate_id = rate.id()
        if not get_rate_dependents(rate):
            self.report({"INFO"}, "This cost item controls no linked items")
            return {"CANCELLED"}
        if not rate_dependent_diffs(rate):
            self.report({"INFO"}, "Linked items already in sync")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        rate, _file = _resolve_item(context, self.rate_id)
        if rate is None:
            layout.label(text="Rate not found", icon="ERROR")
            return
        changed = _diff_label(rate_dependent_diffs(rate)) or "—"
        groups = group_dependents_by_schedule(rate)
        total = sum(len(items) for _s, items in groups)
        layout.label(text=f"Changed: {changed}")
        layout.label(text=f"{total} linked cost item(s) will be updated:")
        box = layout.box()
        for schedule, items in groups:
            name = (schedule.Name if schedule is not None else None) or "(no schedule)"
            n = len(items)
            box.label(text=f"• {name}:  {n} item{'s' if n != 1 else ''}")
        layout.prop(self, "should_update_identification")

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        rate = file.by_id(self.rate_id)
        n = propagate_rate_to_dependents(
            tool, rate, with_identification=self.should_update_identification)
        refresh_cost_ui(tool)
        self.report({"INFO"}, f"Updated {n} linked cost item(s)")


class CostSync_OT_ResyncValues(*_IfcOperatorBase):
    """Re-share the rate's cost values onto its linked items (silent)."""
    bl_idname = "bonsai5d.resync_rate_values"
    bl_label = "Resync cost values to linked items"
    bl_options = {"REGISTER", "UNDO"}

    rate_id: bpy.props.IntProperty(default=0, options={"HIDDEN"})

    def _execute(self, context):
        from bonsai import tool
        rate, _file = _resolve_item(context, self.rate_id)
        if rate is None:
            self.report({"ERROR"}, "No rate cost item resolved")
            return
        n = resync_rate_values(tool, rate)
        refresh_cost_ui(tool)
        self.report({"INFO"}, f"Re-synced cost values to {n} linked item(s)")


class CostSync_OT_ResyncFromRate(*_IfcOperatorBase):
    """Pull this CME item back in line with its controlling rate."""
    bl_idname = "bonsai5d.resync_from_rate"
    bl_label = "Resync this item from its rate"
    bl_options = {"REGISTER", "UNDO"}

    item_id: bpy.props.IntProperty(default=0, options={"HIDDEN"})

    def _execute(self, context):
        from bonsai import tool
        item, _file = _resolve_item(context, self.item_id)
        if item is None:
            self.report({"ERROR"}, "No cost item resolved")
            return
        if align_item_to_rate(tool, item):
            refresh_cost_ui(tool)
            self.report({"INFO"}, "Item re-synced from its rate")
        else:
            self.report({"INFO"}, "Item has no linked rate")


classes = [
    CostSync_OT_PropagateRate,
    CostSync_OT_ResyncValues,
    CostSync_OT_ResyncFromRate,
]
