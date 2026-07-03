# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import csv
import os
import bpy
from .data import (
    _SYSTEMS, _prop_name, _set_code, _invalidate_summary_cache, _build_summary,
)

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
        _invalidate_summary_cache()


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
        _invalidate_summary_cache()


class CC_OT_ExportExcel(bpy.types.Operator):
    """Export the cost schedule summary to CSV."""
    bl_idname = "cost_classification.export_excel"
    bl_label = "Export to Excel"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        self.filepath = "riepilogo_classificazione.csv"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        if not file:
            self.report({"ERROR"}, "Nessun file IFC caricato.")
            return {"CANCELLED"}

        props = context.scene.BIMCostProperties
        summary_key = context.scene.cc_summary_system
        if summary_key not in _SYSTEMS:
            self.report({"ERROR"}, "Sistema di classificazione non valido.")
            return {"CANCELLED"}

        ifc_name, _, _, _ = _SYSTEMS[summary_key]
        totals = _build_summary(file, props.active_cost_schedule_id, ifc_name)
        if not totals:
            self.report({"ERROR"}, "Nessun dato da esportare.")
            return {"CANCELLED"}

        grand_total = sum(totals.values())

        classified = sorted(k for k in totals if k != "__none__")
        if "__none__" in totals:
            classified.append("__none__")

        filepath = self.filepath
        if not filepath:
            self.report({"ERROR"}, "Nessun file selezionato.")
            return {"CANCELLED"}

        if not filepath.endswith(".csv"):
            filepath += ".csv"

        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Codice", "Importo", "Percentuale"])

                for key in classified:
                    amount = totals[key]
                    pct = (amount / grand_total * 100) if grand_total else 0.0
                    if key == "__none__":
                        code_label = "(non classif.)"
                    else:
                        code_label = key
                    writer.writerow([code_label, f"{amount:,.2f}", f"{pct:.1f}"])

                writer.writerow([])
                writer.writerow(["TOTALE", f"{grand_total:,.2f}", "100.0"])
        except Exception as e:
            self.report({"ERROR"}, f"Errore durante l'esportazione: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Esportazione completata: {filepath}")
        return {"FINISHED"}


classes = [CC_OT_SetCode, CC_OT_ClearCode, CC_OT_ExportExcel]
