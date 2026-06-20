# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import time as _time

from ...tool.cost import PRICED_BOQ_TYPES

SOURCE_TYPES = {*PRICED_BOQ_TYPES, "UNPRICEDBILLOFQUANTITIES"}

_ENUM_TTL = 1.0  # seconds before enum caches rebuild

_safety_enum_cache = {}          # {sid: items_list}
_boq_cache: tuple = (0.0, None)  # (timestamp, result)
_tender_cache: tuple = (0.0, None)


def _invalidate_tender_enum_caches():
    global _safety_enum_cache, _boq_cache, _tender_cache
    _safety_enum_cache = {}
    _boq_cache = (0.0, None)
    _tender_cache = (0.0, None)

_cmp = {
    "source_name": "",
    "rows": [],
    "source_grand": 0.0,
    "tender_names": [],
    "tender_grands": [],
}


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
    """Yield leaf IfcCostItem objects."""
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

        quantities = []
        for q in (src.CostQuantities or []):
            info = {k: v for k, v in q.get_info().items() if k not in ("id", "type")}
            quantities.append(ifc.create_entity(q.is_a(), **info))
        if quantities:
            dst.CostQuantities = quantities

        children = [c for rel in (src.IsNestedBy or []) for c in rel.RelatedObjects]
        is_leaf = not children

        if exclude_id.startswith("#"):
            _matches = src.id() == int(exclude_id[1:])
        else:
            _matches = bool(exclude_id) and (src.Identification or "") == exclude_id
        now_safety = inside_safety or _matches

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


# Dynamic enum callbacks ─────────────────────────────────────────────────────

def _safety_item_enum(self, context):
    _default = [("NONE", "(none)", "Do not exclude any subtree from the discount")]
    try:
        sid = getattr(context.scene, "tender_source_boq", "0")
        if sid == "0":
            return _default
        if sid in _safety_enum_cache:
            return _safety_enum_cache[sid]
        file = _get_ifc()
        if file is None:
            return _default
        import ifcopenshell.util.cost
        items = [_default[0]]
        schedule = file.by_id(int(sid))

        def _walk(item):
            children = [c for rel in (item.IsNestedBy or []) for c in rel.RelatedObjects]
            if children:
                ident = item.Identification or ""
                enum_id = ident if ident else f"#{item.id()}"
                label = f"[{ident}]  {item.Name or ''}" if ident else (item.Name or f"#{item.id()}")
                items.append((enum_id, label, ""))
            for ch in children:
                _walk(ch)

        for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
            _walk(root)
        _safety_enum_cache[sid] = items
        return items
    except Exception:
        return _default


def _boq_items(self, context):
    global _boq_cache
    ts, result = _boq_cache
    if result is not None and _time.monotonic() - ts < _ENUM_TTL:
        return result
    try:
        schedules = _get_schedules(SOURCE_TYPES)
        result = [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules] if schedules else [("0", "No BoQ found", "")]
    except Exception:
        result = [("0", "Error reading IFC", "")]
    _boq_cache = (_time.monotonic(), result)
    return result


def _tender_items(self, context):
    global _tender_cache
    ts, result = _tender_cache
    if result is not None and _time.monotonic() - ts < _ENUM_TTL:
        return result
    try:
        schedules = _get_schedules("TENDER")
        result = [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules] if schedules else [("0", "No Tender schedules found", "")]
    except Exception:
        result = [("0", "Error reading IFC", "")]
    _tender_cache = (_time.monotonic(), result)
    return result
