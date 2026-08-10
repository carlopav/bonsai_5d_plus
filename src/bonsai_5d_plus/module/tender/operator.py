# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from . import data as _data
from .data import _get_ifc, _get_schedules, _get_applied_value, _get_quantity, _iter_leaves, _copy_items, _build_comparison, _invalidate_tender_enum_caches
from ...tool.cost import refresh_cost_ui

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class CreateTenderScheduleOperator(*_IfcOperatorBase):
    """Duplicate the source BoQ as a TENDER schedule for a bidding company."""

    bl_idname = "bim.create_tender_schedule"
    bl_label = "Create Tender Schedule"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            return (
                context.scene.tender_source_boq != "0"
                and bool(context.scene.tender_company_name.strip())
                and _get_ifc() is not None
            )
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        source = file.by_id(int(context.scene.tender_source_boq))
        company = context.scene.tender_company_name.strip()

        tender = tool.Ifc.run("cost.add_cost_schedule", name=company, predefined_type="TENDER")
        mode = context.scene.tender_price_mode
        discount = context.scene.tender_discount_pct if mode == "DISCOUNT" else 0.0
        safety = context.scene.tender_safety_item_id if mode == "DISCOUNT" else "NONE"
        _copy_items(tool, source, tender, discount_pct=discount, safety_item_id=safety)

        refresh_cost_ui(tool)
        _invalidate_tender_enum_caches()
        self.report({"INFO"}, f"Created '{company}'.")


class EditTenderPricesOperator(*_IfcOperatorBase):
    """Open a dialog to enter the unit prices offered by the bidding company."""

    bl_idname = "bim.edit_tender_prices"
    bl_label = "Enter Offered Prices..."
    bl_options = {"REGISTER", "UNDO"}

    _schedule_name: str = ""

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.tender_active_schedule != "0" and _get_ifc() is not None
        except Exception:
            return False

    def invoke(self, context, event):
        file = _get_ifc()
        schedule = file.by_id(int(context.scene.tender_active_schedule))
        self._schedule_name = schedule.Name or f"#{schedule.id()}"

        col = context.window_manager.tender_price_items
        col.clear()
        for item in _iter_leaves(schedule):
            unit, qty = _get_quantity(item)
            e = col.add()
            e.ifc_id = item.id()
            e.identification = item.Identification or ""
            e.item_name = item.Name or ""
            e.unit_label = unit
            e.quantity = qty
            e.unit_price = _get_applied_value(item)

        return context.window_manager.invoke_props_dialog(self, width=720, confirm_text="Apply")

    def draw(self, context):
        layout = self.layout
        col = context.window_manager.tender_price_items
        n = len(col)

        layout.label(text=f"Offered prices: {self._schedule_name}", icon="GREASEPENCIL")

        header = layout.row()
        header.label(text="Code")
        header.label(text="Description")
        header.label(text="UoM")
        header.label(text="Qty")
        header.label(text="Unit Price")
        header.label(text="Total")

        layout.template_list(
            "TENDER_UL_PriceItems", "",
            context.window_manager, "tender_price_items",
            context.window_manager, "tender_price_index",
            rows=min(n, 22),
        )

        total = sum(e.quantity * e.unit_price for e in col)
        row = layout.row()
        row.separator()
        row.label(text=f"TOTAL BID:  € {total:,.2f}")

    def _execute(self, context):
        from bonsai import tool

        file = _get_ifc()
        count = 0
        for entry in context.window_manager.tender_price_items:
            try:
                item = file.by_id(entry.ifc_id)
            except Exception:
                continue
            for cv in list(item.CostValues or []):
                tool.Ifc.run("cost.remove_cost_value", parent=item, cost_value=cv)
            if entry.unit_price > 0.0:
                cv = tool.Ifc.run("cost.add_cost_value", parent=item)
                tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                             attributes={"AppliedValue": entry.unit_price})
            count += 1

        refresh_cost_ui(tool)
        self.report({"INFO"}, f"Updated {count} prices in '{self._schedule_name}'.")


class ShowTenderComparisonOperator(bpy.types.Operator):
    """Show the summary Bid Comparison table across all tender schedules."""

    bl_idname = "bim.show_tender_comparison"
    bl_label = "Bid Comparison"

    @classmethod
    def poll(cls, context):
        try:
            return (
                context.scene.tender_source_boq != "0"
                and bool(_get_schedules("TENDER"))
                and _get_ifc() is not None
            )
        except Exception:
            return False

    def invoke(self, context, event):
        file = _get_ifc()
        source = file.by_id(int(context.scene.tender_source_boq))
        tenders = _get_schedules("TENDER")
        rows, sg, tg, names = _build_comparison(source, tenders)
        _data._cmp.update({
            "source_name": source.Name or f"#{source.id()}",
            "rows": rows,
            "source_grand": sg,
            "tender_names": names,
            "tender_grands": tg,
        })
        return context.window_manager.invoke_props_dialog(self, width=620)

    def draw(self, context):
        layout = self.layout
        sg = _data._cmp["source_grand"]

        layout.label(text=f"Base estimate: {_data._cmp['source_name']}", icon="SPREADSHEET")
        layout.separator()

        box = layout.box()
        header = box.row()
        header.label(text="Bidder")
        header.label(text="Total bid")
        header.label(text="Difference")
        header.label(text="Discount %")

        r = box.row()
        r.label(text="Base estimate")
        r.label(text=f"{sg:,.2f}")
        r.label(text="—")
        r.label(text="—")

        best_total = None
        best_name = ""
        for name, total in zip(_data._cmp["tender_names"], _data._cmp["tender_grands"]):
            delta = total - sg
            pct = (delta / sg * 100) if sg else 0.0
            row = box.row()
            row.label(text=name)
            row.label(text=f"{total:,.2f}")
            c_delta = row.column()
            c_delta.alert = delta > 0
            c_delta.label(text=f"{delta:+,.2f}")
            c_pct = row.column()
            c_pct.alert = delta > 0
            c_pct.label(text=f"{pct:+.2f}%")
            if best_total is None or total < best_total:
                best_total = total
                best_name = name

        if best_name and len(_data._cmp["tender_grands"]) > 0:
            layout.separator()
            layout.label(
                text=f"Lowest bid: {best_name}  —  € {best_total:,.2f}",
                icon="CHECKMARK",
            )

        layout.separator()
        layout.label(text="Per-item detail → export to clipboard:", icon="INFO")
        layout.operator(CopyTenderComparisonOperator.bl_idname, icon="COPYDOWN")

    def execute(self, context):
        return {"FINISHED"}


class CopyTenderComparisonOperator(bpy.types.Operator):
    """Copy the detailed Bid Comparison to clipboard as TSV."""

    bl_idname = "bim.copy_tender_comparison"
    bl_label = "Copy Detail TSV"

    @classmethod
    def poll(cls, context):
        try:
            return (
                context.scene.tender_source_boq != "0"
                and bool(_get_schedules("TENDER"))
                and _get_ifc() is not None
            )
        except Exception:
            return False

    def execute(self, context):
        if not _data._cmp["rows"]:
            file = _get_ifc()
            source = file.by_id(int(context.scene.tender_source_boq))
            tenders = _get_schedules("TENDER")
            rows, sg, tg, names = _build_comparison(source, tenders)
            _data._cmp.update({"source_name": source.Name or "", "rows": rows,
                                "source_grand": sg, "tender_names": names, "tender_grands": tg})

        lines = []
        lines.append("BID COMPARISON TABLE")
        lines.append(f"Base estimate:\t{_data._cmp['source_name']}")
        lines.append("")

        short_names = _data._cmp["tender_names"]
        h = ["Code", "Description", "UoM", "Qty", "Base Unit Price", "Base Total"]
        for sn in short_names:
            h += [f"{sn}\nP.U.", f"{sn}\nTotale", f"{sn}\nΔ%"]
        lines.append("\t".join(h))

        for r in _data._cmp["rows"]:
            base_total = r["base_total"]
            cols = [
                r["identification"], r["name"], r["unit"],
                f"{r['qty']:.3f}", f"{r['base_pu']:.2f}", f"{base_total:.2f}",
            ]
            for t in r["tenders"]:
                pct = ((t["total"] - base_total) / base_total * 100) if base_total else 0.0
                cols += [f"{t['pu']:.2f}", f"{t['total']:.2f}", f"{pct:+.2f}%"]
            lines.append("\t".join(cols))

        sg = _data._cmp["source_grand"]
        foot = ["", "TOTAL", "", "", "", f"{sg:.2f}"]
        for total in _data._cmp["tender_grands"]:
            pct = ((total - sg) / sg * 100) if sg else 0.0
            foot += ["", f"{total:.2f}", f"{pct:+.2f}%"]
        lines.append("\t".join(foot))

        context.window_manager.clipboard = "\n".join(lines)
        self.report({"INFO"}, "Bid Comparison copied to clipboard.")
        return {"FINISHED"}


classes = [
    CreateTenderScheduleOperator,
    EditTenderPricesOperator,
    ShowTenderComparisonOperator,
    CopyTenderComparisonOperator,
]
