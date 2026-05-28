# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from . import data as _data
from .data import (
    VALID_TYPES, MAX_DISPLAY,
    _collect_leaf_items, _build_unique_items, _collect_sor_items,
    _compare_cost_items, _format_diffs, _copy_cost_values, _replace_cost_values,
)

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class BoQToSoROperator(*_IfcOperatorBase):
    """Create or update a Schedule of Rates from the active Bill of Quantities."""

    bl_idname = "bim.boq_to_schedule_of_rates"
    bl_label = "BoQ → Schedule of Rates"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_schedule_id == 0:
                return False
            from bonsai import tool
            schedule = tool.Ifc.get().by_id(int(props.active_cost_schedule_id))
            return schedule.PredefinedType in VALID_TYPES
        except Exception:
            return False

    def invoke(self, context, event):
        from bonsai import tool

        schedule = tool.Ifc.get().by_id(int(context.scene.BIMCostProperties.active_cost_schedule_id))
        all_items = _collect_leaf_items(schedule)
        unique_items, conflicts = _build_unique_items(all_items)

        mode = context.scene.boq_to_sor_mode
        to_add = unique_items
        already_present = []
        orphaned = []
        mismatched = []
        target_schedule_name = ""

        if mode == "UPDATE":
            target_id = context.scene.boq_to_sor_target_schedule
            if target_id and target_id != "0":
                target_schedule = tool.Ifc.get().by_id(int(target_id))
                target_schedule_name = target_schedule.Name or f"#{target_id}"
                sor_items = _collect_sor_items(target_schedule)
                sor_dict = {}
                for key, item in sor_items:
                    if key not in sor_dict:
                        sor_dict[key] = item
                boq_keys = {(item.Identification or "", item.Name or "") for item in unique_items}
                to_add = []
                already_present = []
                for boq_item in unique_items:
                    key = (boq_item.Identification or "", boq_item.Name or "")
                    if key not in sor_dict:
                        to_add.append(boq_item)
                    else:
                        diffs = _compare_cost_items(boq_item, sor_dict[key])
                        if diffs:
                            mismatched.append({"boq_item": boq_item, "sor_item": sor_dict[key], "diffs": diffs})
                        else:
                            already_present.append(boq_item)
                orphaned = [item for key, item in sor_items if key not in boq_keys]

                sor_by_id = {}
                for (sor_ident, _), sor_item in sor_items:
                    if sor_ident:
                        sor_by_id.setdefault(sor_ident, []).append(sor_item)
                filtered_to_add = []
                for boq_item in to_add:
                    ident = boq_item.Identification or ""
                    matches = sor_by_id.get(ident, []) if ident else []
                    if matches:
                        for sor_item in matches:
                            diffs = [{"field": "Name", "boq": boq_item.Name or "", "sor": sor_item.Name or ""}]
                            diffs.extend(_compare_cost_items(boq_item, sor_item))
                            mismatched.append({"boq_item": boq_item, "sor_item": sor_item, "diffs": diffs})
                    else:
                        filtered_to_add.append(boq_item)
                to_add = filtered_to_add

        _data._state.update({
            "unique_items": unique_items,
            "conflicts": conflicts,
            "to_add": to_add,
            "already_present": already_present,
            "mismatched": mismatched,
            "orphaned": orphaned,
            "schedule_name": schedule.Name or "(unnamed)",
            "total": len(all_items),
            "mode": mode,
            "target_schedule_name": target_schedule_name,
        })

        return context.window_manager.invoke_props_dialog(self, width=580, confirm_text="Proceed")

    def draw(self, context):
        layout = self.layout
        conflicts = _data._state["conflicts"]
        to_add = _data._state["to_add"]
        already_present = _data._state["already_present"]
        mismatched = _data._state["mismatched"]
        orphaned = _data._state["orphaned"]
        unique = _data._state["unique_items"]
        mode = _data._state["mode"]
        duplicates = _data._state["total"] - len(unique) - sum(c["count"] - 1 for c in conflicts)

        layout.label(text=f"Source BoQ: {_data._state['schedule_name']}")
        if mode == "UPDATE":
            layout.label(text=f"Target SoR: {_data._state['target_schedule_name']}")

        row = layout.row()
        row.label(text=f"Total leaf items: {_data._state['total']}")
        row.label(text=f"Unique: {len(unique)}")
        if duplicates:
            row.label(text=f"Duplicates removed: {duplicates}")

        if conflicts:
            layout.separator()
            box = layout.box()
            col = box.column()
            col.alert = True
            col.label(text=f"Conflicts detected ({len(conflicts)}) — operation blocked:", icon="ERROR")
            col.label(text="Items share Identification+Name but differ in Description or value:")
            for c in conflicts:
                row = box.row()
                row.alert = True
                row.label(text=f"[{c['identification']}] {c['name']}  ({c['count']} occurrences)")
                detail = []
                if len(c["descriptions"]) > 1:
                    detail.append("different Description")
                if len(c["values"]) > 1:
                    detail.append(f"different values: {sorted(str(v) for v in c['values'])}")
                if detail:
                    box.label(text="    " + " · ".join(detail))
            return

        layout.separator()

        if mode == "UPDATE":
            row = layout.row()
            row.label(text=f"Rates not present, to be added: {len(to_add)}", icon="ADD")
            row.label(text=f"Rates already present and congruent: {len(already_present)}", icon="CHECKMARK")
            row = layout.row()
            row.label(text=f"Rates present but different: {len(mismatched)}", icon="ERROR" if mismatched else "NONE")
            row.label(text=f"Rates only in Schedule of Rates, not modified: {len(orphaned)}", icon="QUESTION")

            layout.operator(BoQToSoRCopyReportOperator.bl_idname, icon="COPYDOWN")

            if to_add:
                box = layout.box()
                box.label(text="Rates not present, to be added:")
                for item in to_add[:MAX_DISPLAY]:
                    box.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(to_add) > MAX_DISPLAY:
                    box.label(text=f"  … and {len(to_add) - MAX_DISPLAY} more")

            if mismatched:
                box = layout.box()
                col = box.column()
                col.alert = True
                col.label(text="Rates present but different (hover for details):")
                for m in mismatched[:MAX_DISPLAY]:
                    item = m["boq_item"]
                    diff_text = _format_diffs(m["diffs"], _data._state["schedule_name"], _data._state["target_schedule_name"])
                    op = col.operator(
                        BoQToSoRItemInfoOperator.bl_idname,
                        text=f"[{item.Identification or ''}] {item.Name or ''}",
                        icon="ERROR",
                        emboss=False,
                    )
                    op.diff_text = diff_text
                if len(mismatched) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(mismatched) - MAX_DISPLAY} more")
                layout.operator(BoQToSoRResolveOperator.bl_idname, icon="TOOL_SETTINGS")

            if already_present:
                box = layout.box()
                col = box.column()
                col.enabled = False
                col.label(text="Rates already present and congruent, skipped:")
                for item in already_present[:MAX_DISPLAY]:
                    col.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(already_present) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(already_present) - MAX_DISPLAY} more")

            if orphaned:
                box = layout.box()
                col = box.column()
                col.enabled = False
                col.label(text="Rates only in Schedule of Rates, not modified:")
                for item in orphaned[:MAX_DISPLAY]:
                    col.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(orphaned) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(orphaned) - MAX_DISPLAY} more")

            if not to_add and not mismatched:
                layout.label(text="Nothing to add — Schedule of Rates is already up to date.", icon="INFO")
        else:
            layout.label(text=f"Items to create: {len(to_add)}", icon="ADD")
            layout.label(text="Click OK to create the new Schedule of Rates.", icon="CHECKMARK")

    def _execute(self, context):
        if _data._state["conflicts"]:
            self.report({"ERROR"}, f"Operation cancelled: {len(_data._state['conflicts'])} conflict(s) must be resolved first.")
            return

        from bonsai import tool
        import bonsai.bim.module.cost.data

        to_add = _data._state["to_add"]
        if not to_add:
            self.report({"INFO"}, "Nothing to add — Schedule of Rates is already up to date.")
            return

        if _data._state["mode"] == "NEW":
            target_schedule = tool.Ifc.run(
                "cost.add_cost_schedule",
                name=f"SoR - {_data._state['schedule_name']}",
                predefined_type="SCHEDULEOFRATES",
            )
        else:
            target_schedule = tool.Ifc.get().by_id(int(context.scene.boq_to_sor_target_schedule))

        for source_item in to_add:
            new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=target_schedule)
            tool.Ifc.run("cost.edit_cost_item", cost_item=new_item, attributes={
                "Name": source_item.Name or "",
                "Identification": source_item.Identification or "",
                "Description": source_item.Description or "",
            })
            _copy_cost_values(tool, source_item, new_item)

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()
        action = "Created" if _data._state["mode"] == "NEW" else "Updated"
        self.report({"INFO"}, f"{action} '{target_schedule.Name}': {len(to_add)} item(s) added.")


class BoQToSoRItemInfoOperator(bpy.types.Operator):
    bl_idname = "bim.boq_to_sor_item_info"
    bl_label = ""
    bl_description = ""

    item_label: bpy.props.StringProperty(default="")
    diff_text: bpy.props.StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        return properties.diff_text or ""

    def execute(self, context):
        return {"FINISHED"}


class BoQToSoRCopyReportOperator(bpy.types.Operator):
    """Copy the full comparison report to clipboard (tab-separated for LibreOffice)."""

    bl_idname = "bim.boq_to_sor_copy_report"
    bl_label = "Copy Full Report to Clipboard"

    def execute(self, context):
        lines = []
        lines.append(f"Source BoQ\t{_data._state['schedule_name']}")
        if _data._state["mode"] == "UPDATE":
            lines.append(f"Target SoR\t{_data._state['target_schedule_name']}")
        lines.append("")

        to_add = _data._state["to_add"]
        mismatched = _data._state["mismatched"]
        already_present = _data._state["already_present"]
        orphaned = _data._state["orphaned"]

        if to_add:
            lines.append(f"=== Rates not present, to be added ({len(to_add)}) ===")
            lines.append("Identification\tName")
            for item in to_add:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")
            lines.append("")

        if mismatched:
            lines.append(f"=== Rates present but different ({len(mismatched)}) ===")
            lines.append("Identification\tName\tField\tBoQ\tSoR")
            for m in mismatched:
                item = m["boq_item"]
                for d in m["diffs"]:
                    lines.append(f"{item.Identification or ''}\t{item.Name or ''}\t{d['field']}\t{d['boq']}\t{d['sor']}")
            lines.append("")

        if already_present:
            lines.append(f"=== Rates already present and congruent ({len(already_present)}) ===")
            lines.append("Identification\tName")
            for item in already_present:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")
            lines.append("")

        if orphaned:
            lines.append(f"=== Rates only in Schedule of Rates, not modified ({len(orphaned)}) ===")
            lines.append("Identification\tName")
            for item in orphaned:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")

        context.window_manager.clipboard = "\n".join(lines)
        self.report({"INFO"}, "Report copied to clipboard.")
        return {"FINISHED"}


class BoQToSoRSetResolutionOperator(bpy.types.Operator):
    bl_idname = "bim.boq_to_sor_set_resolution"
    bl_label = ""
    bl_options = {"INTERNAL"}

    identification: bpy.props.StringProperty()
    rate_name: bpy.props.StringProperty()
    direction: bpy.props.StringProperty()

    def execute(self, context):
        _data._state["resolutions"][(self.identification, self.rate_name)] = self.direction
        return {"FINISHED"}


class BoQToSoRResolveOperator(*_IfcOperatorBase):
    """Open a scrollable dialog to resolve each mismatched rate individually."""

    bl_idname = "bim.boq_to_sor_resolve"
    bl_label = "Resolve Mismatched Rates"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        col = context.scene.boq_to_sor_mismatched_rates
        col.clear()
        _data._state["resolutions"] = {}
        _data._state["mismatched_tooltips"] = {}
        for m in _data._state["mismatched"]:
            boq_item = m["boq_item"]
            entry = col.add()
            entry.identification = boq_item.Identification or ""
            entry.rate_name = boq_item.Name or ""
            entry.diff_fields = " · ".join(d["field"] for d in m["diffs"])
            key = (entry.identification, entry.rate_name)
            _data._state["resolutions"][key] = "SKIP"
            _data._state["mismatched_tooltips"][key] = _format_diffs(
                m["diffs"], _data._state["schedule_name"], _data._state["target_schedule_name"]
            )
        return context.window_manager.invoke_props_dialog(self, width=720, confirm_text="Apply")

    def draw(self, context):
        layout = self.layout
        n = len(_data._state["mismatched"])
        layout.label(text=f"Resolve {n} mismatched rate(s) — hover each row for diff details:")
        layout.template_list(
            "COST_UL_MismatchedRates", "",
            context.scene, "boq_to_sor_mismatched_rates",
            context.scene, "boq_to_sor_mismatched_index",
            rows=min(n, 12),
        )
        idx = context.scene.boq_to_sor_mismatched_index
        rates = context.scene.boq_to_sor_mismatched_rates
        if 0 <= idx < len(rates):
            selected = rates[idx]
            key = (selected.identification, selected.rate_name)
            diff = _data._state["mismatched_tooltips"].get(key, "")
            if diff:
                box = layout.box()
                for line in diff.split("\n"):
                    box.label(text=line if line else " ")

        boq = _data._state.get("schedule_name") or "BoQ"
        sor = _data._state.get("target_schedule_name") or "SoR"
        layout.label(
            text=f"{boq}→{sor} updates the SoR rate.  {sor}→{boq} updates the BoQ item.",
            icon="INFO",
        )

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        lookup = {
            (m["boq_item"].Identification or "", m["boq_item"].Name or ""): m
            for m in _data._state["mismatched"]
        }

        modified = 0
        for (identification, rate_name), resolution in _data._state["resolutions"].items():
            if resolution == "SKIP":
                continue
            m = lookup.get((identification, rate_name))
            if not m:
                continue

            boq_item, sor_item = m["boq_item"], m["sor_item"]
            source, target = (boq_item, sor_item) if resolution == "BOQ_TO_SOR" else (sor_item, boq_item)

            item_attrs = {}
            for d in m["diffs"]:
                if d["field"] == "Name":
                    item_attrs["Name"] = source.Name or ""
                elif d["field"] == "Description":
                    item_attrs["Description"] = source.Description or ""
            if item_attrs:
                tool.Ifc.run("cost.edit_cost_item", cost_item=target, attributes=item_attrs)

            if any(d["field"] == "Value" for d in m["diffs"]):
                _replace_cost_values(tool, source, target)

            modified += 1

        if modified:
            bonsai.bim.module.cost.data.refresh()
            tool.Cost.load_cost_schedule_tree()

        self.report({"INFO"}, f"Resolved {modified} rate(s).")
        return {"FINISHED"}


classes = [
    BoQToSoROperator,
    BoQToSoRItemInfoOperator,
    BoQToSoRCopyReportOperator,
    BoQToSoRSetResolutionOperator,
    BoQToSoRResolveOperator,
]
