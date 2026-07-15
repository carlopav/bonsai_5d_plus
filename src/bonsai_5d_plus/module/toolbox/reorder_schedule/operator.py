# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy

from ....tool.cost import (
    refresh_cost_ui,
    get_cost_item_children,
    iter_hierarchy_codes,
    max_hierarchy_level,
)

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


def _assign_identifications(tool, items, parent_prefix=""):
    """Recursively assign progressive identifications (1, 1.1, 1.1.1, …)."""
    for i, item in enumerate(items, start=1):
        ident = str(i) if not parent_prefix else f"{parent_prefix}.{i}"
        tool.Ifc.run("cost.edit_cost_item", cost_item=item, attributes={"Identification": ident})
        children = get_cost_item_children(item)
        if children:
            _assign_identifications(tool, children, parent_prefix=ident)


def _assign_identifications_from_level(tool, schedule, start_level):
    """Renumber schedule using the shared iter_hierarchy_codes rule (also used
    by the Prints Manager PDF export): levels above start_level keep their
    existing Identification untouched; from start_level down, existing
    numeric Identifications are kept and continued rather than reset."""
    for item, level, code in iter_hierarchy_codes(schedule, start_level):
        if level < start_level:
            continue
        if (item.Identification or "") != code:
            tool.Ifc.run("cost.edit_cost_item", cost_item=item, attributes={"Identification": code})


class _ReorderBase(*_IfcOperatorBase):
    """Shared base for reorder operators: poll, invoke, and _execute skeleton."""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def _draw_warning(self, col):
        col.label(text="WARNING — this action cannot be undone via IFC save.", icon="ERROR")
        col.separator(factor=0.5)

    def _draw_footer(self, col):
        col.separator(factor=0.5)
        col.label(text="Blender undo (Ctrl+Z) can revert within the current session.", icon="INFO")

    def _active_schedule(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        return file.by_id(int(props.active_cost_schedule_id))

    def _do_reorder(self, tool, schedule):
        raise NotImplementedError

    def _execute(self, context):
        from bonsai import tool

        schedule = self._active_schedule(context)
        self._do_reorder(tool, schedule)
        refresh_cost_ui(tool)


class RS_OT_ReorderIdentifications(_ReorderBase):
    """Assign progressive nested identifications (1, 1.1, 1.2, 2, …) to all
    cost items in the active schedule. Existing identifications are overwritten."""
    bl_idname = "reorder_schedule.reorder_identifications"
    bl_label = "Reorder Identifications"

    def draw(self, context):
        col = self.layout.column(align=True)
        self._draw_warning(col)
        col.label(text="All Identification fields in the active Cost Schedule")
        col.label(text="will be permanently overwritten with progressive numbers:")
        col.label(text="   1,  1.1,  1.1.1,  1.2,  2,  2.1,  …")
        self._draw_footer(col)

    def _do_reorder(self, tool, schedule):
        import ifcopenshell.util.cost
        _assign_identifications(tool, ifcopenshell.util.cost.get_root_cost_items(schedule))


class RS_OT_ReorderKeepRootSummary(_ReorderBase):
    """Assign progressive nested identifications from a chosen hierarchy
    level down, leaving the levels above it untouched (same rule as the
    Prints Manager PDF export's Hierarchy Renumbering: existing numeric
    Identifications are kept and continued rather than reset)."""
    bl_idname = "reorder_schedule.reorder_keep_root_summary"
    bl_label = "Reorder (keep levels above)"

    start_level: bpy.props.IntProperty(
        name="Renumber From Level",
        description=(
            "Cost hierarchy level (0 = root) from which items are renumbered. "
            "Levels above it keep their existing Identification as-is; from "
            "this level down, existing numeric Identifications are kept and "
            "continued rather than reset. 0 renumbers the whole hierarchy"
        ),
        default=1, min=0,
    )

    def draw(self, context):
        col = self.layout.column(align=True)
        self._draw_warning(col)
        col.label(text="Identification fields from the chosen level down will be")
        col.label(text="overwritten with progressive numbers; existing numeric")
        col.label(text="Identifications are kept and continued where present.")
        col.label(text="Levels above it are left unchanged.")
        col.separator(factor=0.5)
        col.prop(self, "start_level")
        try:
            schedule = self._active_schedule(context)
            col.label(text=f"Deepest level in this schedule: {max_hierarchy_level(schedule)}")
        except Exception:
            pass
        self._draw_footer(col)

    def _do_reorder(self, tool, schedule):
        _assign_identifications_from_level(tool, schedule, self.start_level)


classes = [RS_OT_ReorderIdentifications, RS_OT_ReorderKeepRootSummary]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
