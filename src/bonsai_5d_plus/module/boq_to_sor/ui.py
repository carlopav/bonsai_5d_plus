# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from . import data as _data
from .data import VALID_TYPES


class COST_UL_MismatchedRates(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        key = (item.identification, item.rate_name)
        resolution = _data._state["resolutions"].get(key, "SKIP")
        boq = _data._state.get("schedule_name") or "BoQ"
        sor = _data._state.get("target_schedule_name") or "SoR"
        row = layout.row(align=True)
        op = row.operator(
            "bim.boq_to_sor_item_info",
            text=f"[{item.identification}] {item.rate_name}  ({item.diff_fields})",
            icon="CHECKMARK" if resolution != "SKIP" else "ERROR",
            emboss=False,
        )
        op.diff_text = _data._state["mismatched_tooltips"].get(key, "")
        for label, direction in (("Skip", "SKIP"), (f"{boq}→{sor}", "BOQ_TO_SOR"), (f"{sor}→{boq}", "SOR_TO_BOQ")):
            op = row.operator("bim.boq_to_sor_set_resolution", text=label, depress=(resolution == direction))
            op.identification = item.identification
            op.rate_name = item.rate_name
            op.direction = direction


class SandboxPanel(bpy.types.Panel):
    bl_label = "Sandbox"
    bl_idname = "SCENE_PT_bonsai5d_sandbox"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


class BoQToSoRPanel(bpy.types.Panel):
    bl_label = "BoQ to Schedule of Rates"
    bl_idname = "SCENE_PT_boq_to_schedule_of_rates"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_bonsai5d_sandbox"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_schedule_id != 0:
                from bonsai import tool
                schedule = tool.Ifc.get().by_id(int(props.active_cost_schedule_id))
                if schedule.PredefinedType not in VALID_TYPES:
                    layout.label(text="Active schedule is not a Bill of Quantities.", icon="INFO")
                    return
        except Exception:
            layout.label(text="No IFC file loaded.", icon="INFO")
            return

        layout.prop(context.scene, "boq_to_sor_mode", expand=True)

        if context.scene.boq_to_sor_mode == "UPDATE":
            layout.prop(context.scene, "boq_to_sor_target_schedule", text="Target SoR")

        layout.operator("bim.boq_to_schedule_of_rates", icon="LINENUMBERS_ON")


classes = [COST_UL_MismatchedRates, SandboxPanel, BoQToSoRPanel]
