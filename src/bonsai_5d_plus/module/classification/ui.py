# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import textwrap
import bpy
from .data import (
    _SYSTEMS, _BY_CODE, _DESCRIPTIONS, _CLASSIFICATIONS_DIR,
    _prop_name, _get_code, _build_summary,
)


class CostClassificationPanel(bpy.types.Panel):
    bl_label = "Cost Item Classification"
    bl_idname = "SCENE_PT_cost_classification"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        if not _SYSTEMS:
            layout.label(text="Nessun sistema di classificazione trovato.", icon="INFO")
            layout.label(text=f"Cartella: {_CLASSIFICATIONS_DIR}")
            return

        try:
            from bonsai import tool
            file = tool.Ifc.get()
        except Exception:
            layout.label(text="Bonsai non disponibile.", icon="ERROR")
            return

        if not file:
            layout.label(text="Nessun file IFC caricato.", icon="INFO")
            return

        props = context.scene.BIMCostProperties
        if props.active_cost_schedule_id == 0:
            layout.label(text="Nessun cost schedule attivo.", icon="INFO")
            return

        cost_item = None
        if props.active_cost_item:
            cost_item = file.by_id(props.active_cost_item.ifc_definition_id)

        for system_key, (ifc_name, label, _, _) in _SYSTEMS.items():
            by_code = _BY_CODE[system_key]
            descs = _DESCRIPTIONS.get(system_key, {})

            box = layout.box()
            row = box.row()
            row.label(text=label, icon="ASSET_MANAGER")

            if cost_item:
                current = _get_code(cost_item, ifc_name)
                if current:
                    row.label(text=current)
                    op = row.operator("cost_classification.clear_code", text="", icon="X")
                    op.system = system_key
                else:
                    row.label(text="—")

                if current and current in by_code:
                    box.label(text=by_code[current])
                    desc = descs.get(current, "")
                    if desc:
                        desc_col = box.column(align=True)
                        desc_col.scale_y = 0.7
                        for line in textwrap.wrap(desc, 60):
                            desc_col.label(text=line)

                row2 = box.row(align=True)
                row2.prop(context.scene, _prop_name(system_key), text="")
                op = row2.operator("cost_classification.set_code", text="", icon="CHECKMARK")
                op.system = system_key
            else:
                box.label(text="Nessuna voce attiva.", icon="INFO")

        layout.separator()
        layout.label(text="Riepilogo schedule:", icon="LINENUMBERS_ON")
        layout.prop(context.scene, "cc_summary_system", text="Sistema")

        summary_key = context.scene.cc_summary_system
        if summary_key not in _SYSTEMS:
            return
        ifc_name, _, _, _ = _SYSTEMS[summary_key]
        by_code = _BY_CODE[summary_key]

        totals = _build_summary(file, props.active_cost_schedule_id, ifc_name)
        if not totals:
            layout.label(text="Nessuna voce trovata.", icon="INFO")
            return

        grand_total = sum(totals.values())
        box = layout.box()

        classified = sorted(k for k in totals if k != "__none__")
        if "__none__" in totals:
            classified.append("__none__")

        for key in classified:
            amount = totals[key]
            pct = (amount / grand_total * 100) if grand_total else 0.0
            split = box.split(factor=0.30)
            if key == "__none__":
                split.label(text="(non classif.)", icon="QUESTION")
            else:
                split.label(text=key)
            split2 = split.split(factor=0.62)
            split2.label(text=f"{amount:,.2f}")
            split2.label(text=f"{pct:.1f}%")

        box.separator()
        split = box.split(factor=0.30)
        split.label(text="TOTALE")
        split2 = split.split(factor=0.62)
        split2.label(text=f"{grand_total:,.2f}")
        split2.label(text="100%")


classes = [CostClassificationPanel]
