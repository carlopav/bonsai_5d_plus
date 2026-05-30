# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import re
import bpy

_NUMERIC_ID_RE = re.compile(r"^\d+(\.\d+)*$")

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


def _is_summary(item):
    """True if the item has a SUM cost value (Category='*')."""
    return any(getattr(cv, "Category", None) == "*" for cv in (item.CostValues or []))


def _get_children(item):
    return [
        obj
        for rel in (item.IsNestedBy or [])
        for obj in (rel.RelatedObjects or [])
        if obj.is_a("IfcCostItem")
    ]


def _assign_identifications(tool, items, parent_prefix=""):
    """Recursively assign progressive identifications (1, 1.1, 1.1.1, …)."""
    for i, item in enumerate(items, start=1):
        ident = str(i) if not parent_prefix else f"{parent_prefix}.{i}"
        tool.Ifc.run("cost.edit_cost_item", cost_item=item, attributes={"Identification": ident})
        children = _get_children(item)
        if children:
            _assign_identifications(tool, children, parent_prefix=ident)


def _assign_identifications_skip_root_summary(tool, items, parent_prefix="", is_root=True):
    """Like _assign_identifications but root-level summary items keep their
    existing identification. The prefix used for their children is:
    - the existing identification, if it is already numeric (e.g. "1", "2.3")
    - otherwise the positional counter (i)."""
    for i, item in enumerate(items, start=1):
        ident = str(i) if not parent_prefix else f"{parent_prefix}.{i}"
        if is_root and _is_summary(item):
            existing = (item.Identification or "").strip()
            child_prefix = existing if _NUMERIC_ID_RE.match(existing) else str(i)
        else:
            tool.Ifc.run("cost.edit_cost_item", cost_item=item, attributes={"Identification": ident})
            child_prefix = ident
        children = _get_children(item)
        if children:
            _assign_identifications_skip_root_summary(tool, children, parent_prefix=child_prefix, is_root=False)


class RS_OT_ReorderIdentifications(*_IfcOperatorBase):
    """Assign progressive nested identifications (1, 1.1, 1.2, 2, …) to all
    cost items in the active schedule. Existing identifications are overwritten."""
    bl_idname = "reorder_schedule.reorder_identifications"
    bl_label = "Reorder Identifications"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="WARNING — this action cannot be undone via IFC save.", icon="ERROR")
        col.separator(factor=0.5)
        col.label(text="All Identification fields in the active Cost Schedule")
        col.label(text="will be permanently overwritten with progressive numbers:")
        col.label(text='   1,  1.1,  1.1.1,  1.2,  2,  2.1,  …')
        col.separator(factor=0.5)
        col.label(text="Blender undo (Ctrl+Z) can revert the change within", icon="INFO")
        col.label(text="the current session, but not after saving the IFC file.")

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data
        import ifcopenshell.util.cost

        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        schedule = file.by_id(int(props.active_cost_schedule_id))

        root_items = ifcopenshell.util.cost.get_root_cost_items(schedule)
        _assign_identifications(tool, root_items)

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


class RS_OT_ReorderKeepRootSummary(*_IfcOperatorBase):
    """Assign progressive nested identifications but leave root-level summary
    items (Category='*') unchanged. Their counter position is still used as
    prefix for their children."""
    bl_idname = "reorder_schedule.reorder_keep_root_summary"
    bl_label = "Reorder (keep root summaries)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="WARNING — this action cannot be undone via IFC save.", icon="ERROR")
        col.separator(factor=0.5)
        col.label(text="Identification fields will be overwritten with progressive numbers.")
        col.label(text="Root-level summary items (Category='*') will be left unchanged.")
        col.label(text="Their children will still be numbered using the parent's")
        col.label(text="positional counter as prefix (e.g. 1.1, 1.2, 2.1, …).")
        col.separator(factor=0.5)
        col.label(text="Blender undo (Ctrl+Z) can revert within the current session.", icon="INFO")

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data
        import ifcopenshell.util.cost

        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        schedule = file.by_id(int(props.active_cost_schedule_id))

        root_items = ifcopenshell.util.cost.get_root_cost_items(schedule)
        _assign_identifications_skip_root_summary(tool, root_items)

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


classes = [RS_OT_ReorderIdentifications, RS_OT_ReorderKeepRootSummary]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
