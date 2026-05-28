# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

VALID_TYPES = {"UNPRICEDBILLOFQUANTITIES", "PRICEDBILLOFQUANTITIES"}
MAX_DISPLAY = 10

_state = {
    "unique_items": [],
    "conflicts": [],
    "to_add": [],
    "already_present": [],
    "mismatched": [],
    "orphaned": [],
    "resolutions": {},
    "mismatched_tooltips": {},
    "schedule_name": "",
    "total": 0,
    "mode": "NEW",
    "target_schedule_name": "",
}


def _get_applied_value(cost_item):
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                return float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    return None


def _collect_leaf_items(schedule):
    import ifcopenshell.util.cost
    items = []

    def traverse(cost_item):
        children = [child for rel in (cost_item.IsNestedBy or []) for child in rel.RelatedObjects]
        if not children:
            items.append(cost_item)
        for child in children:
            traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)
    return items


def _build_unique_items(all_items):
    groups = {}
    order = []
    for item in all_items:
        key = (item.Identification or "", item.Name or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    unique_items = []
    conflicts = []

    for key in order:
        items = groups[key]
        if len(items) == 1:
            unique_items.append(items[0])
            continue
        descriptions = {item.Description or "" for item in items}
        values = {_get_applied_value(item) for item in items}
        if len(descriptions) > 1 or len(values) > 1:
            conflicts.append({
                "identification": key[0],
                "name": key[1],
                "count": len(items),
                "descriptions": descriptions,
                "values": values,
            })
        else:
            unique_items.append(items[0])

    return unique_items, conflicts


def _collect_sor_items(schedule):
    import ifcopenshell.util.cost
    items = []

    def traverse(cost_item):
        items.append(((cost_item.Identification or "", cost_item.Name or ""), cost_item))
        for rel in (cost_item.IsNestedBy or []):
            for child in rel.RelatedObjects:
                traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)
    return items


def _diff_text(a, b, label_a="BoQ", label_b="SoR", ctx=30):
    import difflib
    a, b = (str(a) if a is not None else ""), (str(b) if b is not None else "")
    if a == b:
        return ""
    out_a, out_b = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        sa, sb = a[i1:i2], b[j1:j2]
        if tag == "equal":
            if len(sa) > ctx * 2:
                sa = sa[:ctx] + "…" + sa[-ctx:]
                sb = sb[:ctx] + "…" + sb[-ctx:]
            out_a.append(sa)
            out_b.append(sb)
        else:
            out_a.append(f"«{sa}»")
            out_b.append(f"«{sb}»")
    return f"{label_a}: " + "".join(out_a) + f"\n{label_b}: " + "".join(out_b)


def _format_diffs(diffs, label_boq="BoQ", label_sor="SoR"):
    parts = []
    for d in diffs:
        if isinstance(d["boq"], str) or isinstance(d["sor"], str):
            parts.append(f"{d['field']}:\n{_diff_text(d['boq'], d['sor'], label_boq, label_sor)}")
        else:
            parts.append(f"{d['field']}:\n  {label_boq}: {d['boq']}\n  {label_sor}: {d['sor']}")
    return "\n\n".join(parts)


def _compare_cost_items(boq_item, sor_item):
    diffs = []
    boq_desc = boq_item.Description or ""
    sor_desc = sor_item.Description or ""
    if boq_desc != sor_desc:
        diffs.append({"field": "Description", "boq": boq_desc, "sor": sor_desc})
    boq_val = _get_applied_value(boq_item)
    sor_val = _get_applied_value(sor_item)
    if boq_val != sor_val:
        diffs.append({"field": "Value", "boq": boq_val, "sor": sor_val})
    return diffs


def _copy_cost_values(tool, source_item, target_item):
    def copy_cv(source_cv, parent):
        target_cv = tool.Ifc.run("cost.add_cost_value", parent=parent)
        attrs = {}
        if source_cv.AppliedValue is not None:
            try:
                attrs["AppliedValue"] = float(
                    source_cv.AppliedValue.wrappedValue
                    if hasattr(source_cv.AppliedValue, "wrappedValue")
                    else source_cv.AppliedValue
                )
            except Exception:
                pass
        if source_cv.Category:
            attrs["Category"] = source_cv.Category
        if source_cv.ArithmeticOperator:
            attrs["ArithmeticOperator"] = source_cv.ArithmeticOperator
        if attrs:
            tool.Ifc.run("cost.edit_cost_value", cost_value=target_cv, attributes=attrs)
        for component in (source_cv.Components or []):
            copy_cv(component, target_cv)

    for source_cv in (source_item.CostValues or []):
        copy_cv(source_cv, target_item)


def _replace_cost_values(tool, source_item, target_item):
    for cv in list(target_item.CostValues or []):
        tool.Ifc.run("cost.remove_cost_value", parent=target_item, cost_value=cv)
    _copy_cost_values(tool, source_item, target_item)


_sor_cache: tuple = (0.0, None)  # (timestamp, result)
_SOR_ENUM_TTL = 1.0


def _sor_schedule_items(self, context):
    import time
    global _sor_cache
    ts, result = _sor_cache
    if result is not None and time.monotonic() - ts < _SOR_ENUM_TTL:
        return result
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            result = [("0", "No IFC file loaded", "")]
        else:
            schedules = [s for s in file.by_type("IfcCostSchedule") if s.PredefinedType == "SCHEDULEOFRATES"]
            result = [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules] if schedules else [("0", "No Schedule of Rates found", "")]
    except Exception:
        result = [("0", "Error reading IFC file", "")]
    _sor_cache = (time.monotonic(), result)
    return result
