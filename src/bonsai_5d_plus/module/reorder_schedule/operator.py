# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy

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
        children = [
            obj
            for rel in (item.IsNestedBy or [])
            for obj in (rel.RelatedObjects or [])
            if obj.is_a("IfcCostItem")
        ]
        if children:
            _assign_identifications(tool, children, parent_prefix=ident)


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


classes = [RS_OT_ReorderIdentifications]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
