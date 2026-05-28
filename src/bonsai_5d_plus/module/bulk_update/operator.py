# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from . import data as _data

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class BulkUpdateCostSchedule(*_IfcOperatorBase):
    """Update cost item values in the active schedule from the loaded rate list."""

    bl_idname = "bim.bulk_update_cost_schedule"
    bl_label = "Preview & Update from Rate List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            has_rates = len(getattr(context.scene, 'xml_rate_list', [])) > 0
            props = context.scene.BIMCostProperties
            return has_rates and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        _data._preview = _data.compute_diff(context)
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        layout = self.layout
        ordered = _data._preview["ordered"]
        to_update = _data._preview["to_update"]

        n_update = sum(1 for e in ordered if e["status"] == "to_update")
        n_unchanged = sum(1 for e in ordered if e["status"] == "unchanged")
        n_not_found = sum(1 for e in ordered if e["status"] == "not_found")

        layout.row().label(
            text=f"Da aggiornare: {n_update}   Non modificati: {n_unchanged}   Non trovati: {n_not_found}"
        )

        if not to_update:
            layout.label(text="Nessuna modifica da applicare.", icon="INFO")

        box = layout.box()
        for entry in ordered:
            split = box.split(factor=0.28)
            col_id = split.row()
            split2 = split.split(factor=0.52)
            col_name = split2.row()
            col_val = split2.row()

            status = entry["status"]
            col_id.label(text=entry["identification"][:24])
            col_name.label(text=entry["name"][:38])

            if status == "to_update":
                col_val.label(text=f"{entry['old_value']:.2f} → {entry['new_value']:.2f}")
            elif status == "unchanged":
                col_id.enabled = False
                col_name.enabled = False
                col_val.enabled = False
                col_val.label(text="non modificato")
            else:
                col_val.alert = True
                col_val.label(text="non trovato")

    def _execute(self, context):
        from bonsai import tool

        def remove_deep(parent, cost_value):
            for component in list(cost_value.Components or []):
                remove_deep(cost_value, component)
            tool.Ifc.run("cost.remove_cost_value", parent=parent, cost_value=cost_value)

        count = 0
        for entry in _data._preview["to_update"]:
            ifc_item = entry["ifc_item"]
            rate = entry["rate"]

            for cv in list(ifc_item.CostValues or []):
                remove_deep(ifc_item, cv)

            cost_value = tool.Ifc.run("cost.add_cost_value", parent=ifc_item)

            if float(rate["labor"]) != 0.0:
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={
                    "AppliedValue": rate["value"],
                    "ArithmeticOperator": "ADD",
                })
                sub1 = tool.Ifc.run("cost.add_cost_value", parent=cost_value)
                sub2 = tool.Ifc.run("cost.add_cost_value", parent=cost_value)
                tool.Ifc.run("cost.edit_cost_value", cost_value=sub1,
                    attributes={"AppliedValue": rate["value"] - rate["labor"]})
                tool.Ifc.run("cost.edit_cost_value", cost_value=sub2,
                    attributes={"Category": "Labor", "AppliedValue": rate["labor"]})
            else:
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value,
                    attributes={"AppliedValue": rate["value"]})

            count += 1

        tool.Cost.load_cost_schedule_tree()
        self.report({'INFO'}, f"Updated {count} cost items.")


classes = [BulkUpdateCostSchedule]
