# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.
#
# Bonsai5D+ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai5D+ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai5D+.  If not, see <http://www.gnu.org/licenses/>.
#
# This file was modified with the assistance of an AI coding tool.

import bpy

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)

SOURCE_TYPES = {"PRICEDBILLOFQUANTITIES", "UNPRICEDBILLOFQUANTITIES"}


# ---------------------------------------------------------------------------
# IFC helpers
# ---------------------------------------------------------------------------

def _get_ifc():
    try:
        from bonsai import tool
        return tool.Ifc.get()
    except Exception:
        return None


def _get_schedules(predefined_type):
    file = _get_ifc()
    if file is None:
        return []
    types = {predefined_type} if isinstance(predefined_type, str) else set(predefined_type)
    return [s for s in file.by_type("IfcCostSchedule") if s.PredefinedType in types]


def _get_applied_value(cost_item):
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                return float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    return 0.0


def _get_quantity(cost_item):
    """Returns (unit_label, quantity_value) from the first CostQuantity found."""
    for q in (cost_item.CostQuantities or []):
        for attr in ("AreaValue", "LengthValue", "VolumeValue", "WeightValue", "CountValue", "TimeValue"):
            val = getattr(q, attr, None)
            if val is not None:
                return getattr(q, "Name", None) or attr.replace("Value", ""), float(val)
    return "", 1.0


def _iter_leaves(schedule):
    """Yield leaf IfcCostItem objects (items with no children)."""
    import ifcopenshell.util.cost

    def _walk(item):
        children = [c for rel in (item.IsNestedBy or []) for c in rel.RelatedObjects]
        if not children:
            yield item
        for ch in children:
            yield from _walk(ch)

    for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
        yield from _walk(root)


def _copy_cost_value(tool_module, src_cv, dst_parent):
    """Recursively copy a CostValue (and its Components) to dst_parent."""
    dst_cv = tool_module.Ifc.run("cost.add_cost_value", parent=dst_parent)
    attrs = {}
    if src_cv.AppliedValue is not None:
        try:
            attrs["AppliedValue"] = float(
                src_cv.AppliedValue.wrappedValue
                if hasattr(src_cv.AppliedValue, "wrappedValue")
                else src_cv.AppliedValue
            )
        except Exception:
            pass
    if src_cv.Category:
        attrs["Category"] = src_cv.Category
    if src_cv.ArithmeticOperator:
        attrs["ArithmeticOperator"] = src_cv.ArithmeticOperator
    if attrs:
        tool_module.Ifc.run("cost.edit_cost_value", cost_value=dst_cv, attributes=attrs)
    for component in (src_cv.Components or []):
        _copy_cost_value(tool_module, component, dst_cv)


def _copy_items(tool_module, source_schedule, target_schedule,
                discount_pct=0.0, safety_item_id="NONE"):
    """Recursively duplicate all cost items from source to target.

    Non-leaf (SUM) items always keep their cost values.
    Leaf items:
      - discount_pct == 0  → prices start at 0 (filled manually by the company)
      - discount_pct  > 0  → price = base * (1 - discount_pct/100), except descendants
                             of the summary item with Identification == safety_item_id,
                             which keep the base price unchanged.
    """
    import ifcopenshell.util.cost
    ifc = tool_module.Ifc.get()
    factor = 1.0 - discount_pct / 100.0
    exclude_id = safety_item_id if safety_item_id != "NONE" else ""

    def _copy_one(src, parent_schedule=None, parent_item=None, inside_safety=False):
        kwargs = {"cost_item": parent_item} if parent_item else {"cost_schedule": parent_schedule}
        dst = tool_module.Ifc.run("cost.add_cost_item", **kwargs)

        attrs = {}
        if src.Name:
            attrs["Name"] = src.Name
        if src.Identification:
            attrs["Identification"] = src.Identification
        if src.Description:
            attrs["Description"] = src.Description
        if attrs:
            tool_module.Ifc.run("cost.edit_cost_item", cost_item=dst, attributes=attrs)

        # Copy physical quantities directly (preserves UoM and amounts)
        quantities = []
        for q in (src.CostQuantities or []):
            info = {k: v for k, v in q.get_info().items() if k not in ("id", "type")}
            quantities.append(ifc.create_entity(q.is_a(), **info))
        if quantities:
            dst.CostQuantities = quantities

        children = [c for rel in (src.IsNestedBy or []) for c in rel.RelatedObjects]
        is_leaf = not children

        now_safety = inside_safety or (bool(exclude_id) and (src.Identification or "") == exclude_id)

        if not is_leaf:
            for cv in (src.CostValues or []):
                _copy_cost_value(tool_module, cv, dst)
        elif discount_pct > 0.0:
            base = _get_applied_value(src)
            if base != 0.0:
                price = base if now_safety else base * factor
                cv = tool_module.Ifc.run("cost.add_cost_value", parent=dst)
                tool_module.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                    attributes={"AppliedValue": price})

        for child in children:
            _copy_one(child, parent_item=dst, inside_safety=now_safety)

    for root in ifcopenshell.util.cost.get_root_cost_items(source_schedule):
        _copy_one(root, parent_schedule=target_schedule)


# ---------------------------------------------------------------------------
# Dynamic enums
# ---------------------------------------------------------------------------

_safety_enum_cache = [("NONE", "(none)", "Do not exclude any subtree from the discount")]


def _safety_item_enum(self, context):
    """Non-leaf cost items of the selected source BoQ, as discount-exclusion candidates.
    The list is kept in a module-level variable to prevent Blender GC from dropping it."""
    global _safety_enum_cache
    items = [("NONE", "(none)", "Do not exclude any subtree from the discount")]
    try:
        sid = getattr(context.scene, "tender_source_boq", "0")
        if sid == "0":
            _safety_enum_cache = items
            return _safety_enum_cache
        file = _get_ifc()
        if file is None:
            _safety_enum_cache = items
            return _safety_enum_cache
        import ifcopenshell.util.cost
        schedule = file.by_id(int(sid))

        def _walk(item):
            children = [c for rel in (item.IsNestedBy or []) for c in rel.RelatedObjects]
            if children:
                ident = item.Identification or ""
                label = f"[{ident}]  {item.Name or ''}" if ident else (item.Name or f"#{item.id()}")
                items.append((ident, label, ""))
            for ch in children:
                _walk(ch)

        for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
            _walk(root)
    except Exception:
        pass
    _safety_enum_cache = items
    return _safety_enum_cache


def _boq_items(self, context):
    try:
        schedules = _get_schedules(SOURCE_TYPES)
        if not schedules:
            return [("0", "No BoQ found", "")]
        return [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules]
    except Exception:
        return [("0", "Error reading IFC", "")]


def _tender_items(self, context):
    try:
        schedules = _get_schedules("TENDER")
        if not schedules:
            return [("0", "No Tender schedules found", "")]
        return [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules]
    except Exception:
        return [("0", "Error reading IFC", "")]


# ---------------------------------------------------------------------------
# PropertyGroups
# ---------------------------------------------------------------------------

class TenderPriceItem(bpy.types.PropertyGroup):
    ifc_id: bpy.props.IntProperty()
    identification: bpy.props.StringProperty()
    item_name: bpy.props.StringProperty()
    unit_label: bpy.props.StringProperty()
    quantity: bpy.props.FloatProperty(precision=3)
    unit_price: bpy.props.FloatProperty(name="P.U.", min=0.0, precision=2)


# ---------------------------------------------------------------------------
# UIList for price editor
# ---------------------------------------------------------------------------

class TENDER_UL_PriceItems(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        s = layout.split(factor=0.13)
        s.label(text=(item.identification or "")[:14])
        s2 = s.split(factor=0.48)
        s2.label(text=(item.item_name or "")[:40])
        s3 = s2.split(factor=0.12)
        s3.label(text=(item.unit_label or "")[:8])
        s4 = s3.split(factor=0.22)
        s4.label(text=f"{item.quantity:.2f}")
        s5 = s4.split(factor=0.52)
        s5.prop(item, "unit_price", text="")
        s5.label(text=f"{item.quantity * item.unit_price:,.2f}")


# ---------------------------------------------------------------------------
# Comparison builder
# ---------------------------------------------------------------------------

_cmp = {
    "source_name": "",
    "rows": [],
    "source_grand": 0.0,
    "tender_names": [],
    "tender_grands": [],
}


def _build_comparison(source_schedule, tender_schedules):
    src_index = {}
    src_order = []
    for item in _iter_leaves(source_schedule):
        ident = item.Identification or item.Name or ""
        if ident not in src_index:
            src_order.append(ident)
        unit, qty = _get_quantity(item)
        pu = _get_applied_value(item)
        src_index[ident] = {"name": item.Name or "", "unit": unit, "qty": qty,
                             "base_pu": pu, "base_total": qty * pu}

    tender_indices = []
    for ts in tender_schedules:
        idx = {}
        for item in _iter_leaves(ts):
            ident = item.Identification or item.Name or ""
            _, qty = _get_quantity(item)
            pu = _get_applied_value(item)
            idx[ident] = {"pu": pu, "total": qty * pu}
        tender_indices.append({"name": ts.Name or f"#{ts.id()}", "index": idx})

    rows = []
    source_grand = 0.0
    tender_grands = [0.0] * len(tender_schedules)

    for ident in src_order:
        src = src_index[ident]
        row = {"identification": ident, **src, "tenders": []}
        source_grand += src["base_total"]
        for i, td in enumerate(tender_indices):
            t = td["index"].get(ident, {"pu": 0.0, "total": 0.0})
            tender_grands[i] += t["total"]
            row["tenders"].append({"name": td["name"], **t})
        rows.append(row)

    return rows, source_grand, tender_grands, [td["name"] for td in tender_indices]


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class CreateTenderScheduleOperator(*_IfcOperatorBase):
    """Duplicate the source BoQ as a TENDER schedule for a bidding company.
    Unit prices start at 0 and are entered via 'Enter Offered Prices'."""

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
        import bonsai.bim.module.cost.data

        file = tool.Ifc.get()
        source = file.by_id(int(context.scene.tender_source_boq))
        company = context.scene.tender_company_name.strip()
        name = company

        tender = tool.Ifc.run("cost.add_cost_schedule", name=name, predefined_type="TENDER")
        mode = context.scene.tender_price_mode
        discount = context.scene.tender_discount_pct if mode == "DISCOUNT" else 0.0
        safety = context.scene.tender_safety_item_id if mode == "DISCOUNT" else "NONE"
        _copy_items(tool, source, tender, discount_pct=discount, safety_item_id=safety)

        bonsai.bim.module.cost.data.refresh()
        try:
            tool.Cost.load_cost_schedule_tree()
        except Exception:
            pass
        self.report({"INFO"}, f"Created '{name}'.")


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

        col = context.scene.tender_price_items
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
        col = context.scene.tender_price_items
        n = len(col)

        layout.label(text=f"Offered prices: {self._schedule_name}", icon="GREASEPENCIL")

        # Column headers
        header = layout.row()
        header.label(text="Code")
        header.label(text="Description")
        header.label(text="UoM")
        header.label(text="Qty")
        header.label(text="Unit Price")
        header.label(text="Total")

        layout.template_list(
            "TENDER_UL_PriceItems", "",
            context.scene, "tender_price_items",
            context.scene, "tender_price_index",
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
        for entry in context.scene.tender_price_items:
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

        try:
            tool.Cost.load_cost_schedule_tree()
        except Exception:
            pass
        self.report({"INFO"}, f"Updated {count} prices in '{self._schedule_name}'.")


class ShowTenderComparisonOperator(bpy.types.Operator):
    """Show the summary Bid Comparison table across all tender schedules vs. the base estimate.
    Use 'Copy TSV' for the per-item detail to paste into LibreOffice/Excel."""

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
        global _cmp
        file = _get_ifc()
        source = file.by_id(int(context.scene.tender_source_boq))
        tenders = _get_schedules("TENDER")
        rows, sg, tg, names = _build_comparison(source, tenders)
        _cmp.update({
            "source_name": source.Name or f"#{source.id()}",
            "rows": rows,
            "source_grand": sg,
            "tender_names": names,
            "tender_grands": tg,
        })
        return context.window_manager.invoke_props_dialog(self, width=620)

    def draw(self, context):
        layout = self.layout
        sg = _cmp["source_grand"]

        layout.label(text=f"Base estimate: {_cmp['source_name']}", icon="SPREADSHEET")
        layout.separator()

        box = layout.box()

        # Header
        header = box.row()
        header.label(text="Bidder")
        header.label(text="Total bid")
        header.label(text="Difference")
        header.label(text="Discount %")

        # Base estimate row
        r = box.row()
        r.label(text="Base estimate")
        r.label(text=f"{sg:,.2f}")
        r.label(text="—")
        r.label(text="—")

        best_total = None
        best_name = ""
        for name, total in zip(_cmp["tender_names"], _cmp["tender_grands"]):
            delta = total - sg
            pct = (delta / sg * 100) if sg else 0.0
            short = name
            row = box.row()
            row.label(text=short)
            row.label(text=f"{total:,.2f}")
            c_delta = row.column()
            c_delta.alert = delta > 0
            c_delta.label(text=f"{delta:+,.2f}")
            c_pct = row.column()
            c_pct.alert = delta > 0
            c_pct.label(text=f"{pct:+.2f}%")
            if best_total is None or total < best_total:
                best_total = total
                best_name = short

        if best_name and len(_cmp["tender_grands"]) > 0:
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
    """Copy the detailed Bid Comparison to clipboard as TSV (for LibreOffice/Excel).
    Columns: Code, Description, UoM, Qty, Base Unit Price, Base Total, [Bidder Unit Price, Total, Δ%] per tender."""

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
        global _cmp
        # Rebuild if empty (called standalone, outside the dialog)
        if not _cmp["rows"]:
            file = _get_ifc()
            source = file.by_id(int(context.scene.tender_source_boq))
            tenders = _get_schedules("TENDER")
            rows, sg, tg, names = _build_comparison(source, tenders)
            _cmp.update({"source_name": source.Name or "", "rows": rows,
                          "source_grand": sg, "tender_names": names, "tender_grands": tg})

        lines = []
        lines.append("BID COMPARISON TABLE")
        lines.append(f"Base estimate:\t{_cmp['source_name']}")
        lines.append("")

        short_names = _cmp["tender_names"]

        # Header row
        h = ["Code", "Description", "UoM", "Qty", "Base Unit Price", "Base Total"]
        for sn in short_names:
            h += [f"{sn}\nP.U.", f"{sn}\nTotale", f"{sn}\nΔ%"]
        lines.append("\t".join(h))

        # Data rows
        for r in _cmp["rows"]:
            base_total = r["base_total"]
            cols = [
                r["identification"],
                r["name"],
                r["unit"],
                f"{r['qty']:.3f}",
                f"{r['base_pu']:.2f}",
                f"{base_total:.2f}",
            ]
            for t in r["tenders"]:
                pct = ((t["total"] - base_total) / base_total * 100) if base_total else 0.0
                cols += [f"{t['pu']:.2f}", f"{t['total']:.2f}", f"{pct:+.2f}%"]
            lines.append("\t".join(cols))

        # Totals footer
        sg = _cmp["source_grand"]
        foot = ["", "TOTAL", "", "", "", f"{sg:.2f}"]
        for total in _cmp["tender_grands"]:
            pct = ((total - sg) / sg * 100) if sg else 0.0
            foot += ["", f"{total:.2f}", f"{pct:+.2f}%"]
        lines.append("\t".join(foot))

        context.window_manager.clipboard = "\n".join(lines)
        self.report({"INFO"}, "Bid Comparison copied to clipboard.")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class TenderComparisonPanel(bpy.types.Panel):
    bl_label = "Tender"
    bl_idname = "SCENE_PT_tender_comparison"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        # ── Create Tender ─────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Create Tender Schedule", icon="ADD")
        box.prop(context.scene, "tender_source_boq", text="Source BoQ")
        box.prop(context.scene, "tender_company_name", text="Name")
        box.prop(context.scene, "tender_price_mode", expand=True)
        if context.scene.tender_price_mode == "DISCOUNT":
            box.prop(context.scene, "tender_discount_pct", text="Discount %")
            box.prop(context.scene, "tender_safety_item_id", text="Exclude from discount")
        box.operator(CreateTenderScheduleOperator.bl_idname, icon="DUPLICATE")

        # ── Enter Prices ──────────────────────────────────────────────────
        box2 = layout.box()
        box2.label(text="Offered Prices", icon="GREASEPENCIL")
        box2.prop(context.scene, "tender_active_schedule", text="Tender")
        box2.operator(EditTenderPricesOperator.bl_idname, icon="MODIFIER")

        # ── Bid Comparison ────────────────────────────────────────────────
        box3 = layout.box()
        box3.label(text="Bid Comparison", icon="SPREADSHEET")
        row = box3.row(align=True)
        row.operator(ShowTenderComparisonOperator.bl_idname, icon="NLA_PUSHDOWN")
        row.operator(CopyTenderComparisonOperator.bl_idname, icon="COPYDOWN", text="TSV")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    TenderPriceItem,
    TENDER_UL_PriceItems,
    CreateTenderScheduleOperator,
    EditTenderPricesOperator,
    ShowTenderComparisonOperator,
    CopyTenderComparisonOperator,
    TenderComparisonPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.tender_source_boq = bpy.props.EnumProperty(
        name="Source BoQ",
        items=_boq_items,
    )
    bpy.types.Scene.tender_price_mode = bpy.props.EnumProperty(
        name="Price mode",
        items=[
            ("EMPTY",    "Empty prices",    "Leaf prices start at 0, filled manually"),
            ("DISCOUNT", "Apply discount %", "Apply a percentage discount to source prices"),
        ],
        default="EMPTY",
    )
    bpy.types.Scene.tender_discount_pct = bpy.props.FloatProperty(
        name="Discount %",
        min=0.0, max=100.0, precision=3, default=0.0,
        subtype="PERCENTAGE",
    )
    bpy.types.Scene.tender_safety_item_id = bpy.props.EnumProperty(
        name="Exclude from discount",
        items=_safety_item_enum,
        description="Summary item whose entire subtree is excluded from the discount",
    )
    bpy.types.Scene.tender_company_name = bpy.props.StringProperty(
        name="Name",
        default="",
    )
    bpy.types.Scene.tender_active_schedule = bpy.props.EnumProperty(
        name="Tender",
        items=_tender_items,
    )
    bpy.types.Scene.tender_price_items = bpy.props.CollectionProperty(type=TenderPriceItem)
    bpy.types.Scene.tender_price_index = bpy.props.IntProperty(default=0)


def unregister():
    del bpy.types.Scene.tender_price_mode
    del bpy.types.Scene.tender_discount_pct
    del bpy.types.Scene.tender_safety_item_id
    del bpy.types.Scene.tender_source_boq
    del bpy.types.Scene.tender_company_name
    del bpy.types.Scene.tender_active_schedule
    del bpy.types.Scene.tender_price_items
    del bpy.types.Scene.tender_price_index
    class_unregister()
