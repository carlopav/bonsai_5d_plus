# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import re
import json

_preview = {"ordered": [], "to_update": []}


def _match_key(name, identification):
    m = re.search(r'\[([^\]]+)\]', name or '')
    if m:
        return m.group(1)
    return re.sub(r'^([A-Z]+)\d{2}(-)', r'\1\2', identification or '')


def _get_cost_item_value(cost_item):
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
        except Exception:
            pass
    return 0.0


def _build_rate_index(context):
    index = {}
    for item in context.scene.xml_rate_list:
        rate = json.loads(item.attributes)
        if rate.get("is_parent"):
            continue
        key = _match_key(rate["name"], rate["id"])
        if key and key not in index:
            index[key] = rate
    return index


def compute_diff(context):
    """Traverse the active schedule, match rates, return preview dict."""
    from bonsai import tool
    import ifcopenshell.util.cost
    file = tool.Ifc.get()
    schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
    schedule = file.by_id(int(schedule_id))
    rate_index = _build_rate_index(context)

    ordered = []
    to_update = []

    def traverse(cost_item):
        key = _match_key(cost_item.Name or '', cost_item.Identification or '')
        if key:
            old_value = _get_cost_item_value(cost_item)
            entry = {
                "ifc_item": cost_item,
                "key": key,
                "identification": cost_item.Identification or '',
                "name": cost_item.Name or '',
                "old_value": old_value,
            }
            if key in rate_index:
                rate = rate_index[key]
                new_value = float(rate["value"])
                entry["rate"] = rate
                entry["new_identification"] = rate["id"]
                entry["new_name"] = rate["name"]
                entry["new_value"] = new_value
                if abs(old_value - new_value) > 1e-6:
                    entry["status"] = "to_update"
                    to_update.append(entry)
                else:
                    entry["status"] = "unchanged"
            else:
                entry["status"] = "not_found"
            ordered.append(entry)

        for rel in (cost_item.IsNestedBy or []):
            for child in rel.RelatedObjects:
                traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)

    return {"ordered": ordered, "to_update": to_update}
