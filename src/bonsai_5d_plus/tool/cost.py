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

"""Shared IFC cost helpers — used by module/rate_list and module/import_export."""

import json


# ---------------------------------------------------------------------------
# Unit resolution helpers (shared with rate_analysis)
# ---------------------------------------------------------------------------

# unit string → (UnitType, IFC_Name, Prefix|None)
_UNIT_TO_SI_DESCRIPTOR = {
    "mq": ("AREAUNIT",   "SQUARE_METRE", None),
    "m2": ("AREAUNIT",   "SQUARE_METRE", None),
    "m²": ("AREAUNIT",   "SQUARE_METRE", None),
    "mc": ("VOLUMEUNIT", "CUBIC_METRE",  None),
    "m3": ("VOLUMEUNIT", "CUBIC_METRE",  None),
    "m³": ("VOLUMEUNIT", "CUBIC_METRE",  None),
    "m":  ("LENGTHUNIT", "METRE",        None),
    "ml": ("LENGTHUNIT", "METRE",        None),
    "lm": ("LENGTHUNIT", "METRE",        None),
    "km": ("LENGTHUNIT", "METRE",        "KILO"),
    "dm": ("LENGTHUNIT", "METRE",        "DECI"),
    "cm": ("LENGTHUNIT", "METRE",        "CENTI"),
    "kg": ("MASSUNIT",   "GRAM",         "KILO"),
    "t":  ("MASSUNIT",   "GRAM",         "MEGA"),
}

# unit string → (UnitType, canonical_name, factor, SI_base_UnitType, SI_base_Name, SI_base_Prefix)
_UNIT_TO_CONVERSION_DESCRIPTOR = {
    "h":   ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "ore": ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "ora": ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "min": ("TIMEUNIT", "MINUTE",   60.0, "TIMEUNIT", "SECOND", None),
}


def _find_si_unit(file, unit_type, si_name, prefix):
    for u in file.by_type("IfcSIUnit"):
        if u.UnitType == unit_type and u.Name == si_name and (u.Prefix or None) == prefix:
            return u
    return None


def get_or_create_unit_entity(file, unit_str):
    """Return an IFC unit entity for unit_str, reusing project units where possible."""
    key = unit_str.lower().strip()

    si_desc = _UNIT_TO_SI_DESCRIPTOR.get(key)
    if si_desc:
        found = _find_si_unit(file, *si_desc)
        if found:
            return found

    conv_desc = _UNIT_TO_CONVERSION_DESCRIPTOR.get(key)
    if conv_desc:
        unit_type, name, factor, base_type, base_name, base_prefix = conv_desc
        for u in file.by_type("IfcConversionBasedUnit"):
            if u.UnitType == unit_type and (u.Name or "").upper() == name:
                return u
        base_si = _find_si_unit(file, base_type, base_name, base_prefix)
        if base_si:
            dims = file.create_entity(
                "IfcDimensionalExponents",
                LengthExponent=0, MassExponent=0, TimeExponent=1,
                ElectricCurrentExponent=0, ThermodynamicTemperatureExponent=0,
                AmountOfSubstanceExponent=0, LuminousIntensityExponent=0,
            )
            conversion_factor = file.create_entity(
                "IfcMeasureWithUnit",
                ValueComponent=file.create_entity("IfcNumericMeasure", factor),
                UnitComponent=base_si,
            )
            return file.create_entity(
                "IfcConversionBasedUnit",
                Dimensions=dims,
                UnitType=unit_type,
                Name=name,
                ConversionFactor=conversion_factor,
            )

    for ifc_class in ("IfcConversionBasedUnit", "IfcContextDependentUnit"):
        for u in file.by_type(ifc_class):
            if (u.Name or "").lower().strip() == key:
                return u

    dims = file.create_entity(
        "IfcDimensionalExponents",
        LengthExponent=0, MassExponent=0, TimeExponent=0,
        ElectricCurrentExponent=0, ThermodynamicTemperatureExponent=0,
        AmountOfSubstanceExponent=0, LuminousIntensityExponent=0,
    )
    return file.create_entity(
        "IfcContextDependentUnit",
        Dimensions=dims,
        UnitType="USERDEFINED",
        Name=unit_str,
    )


def set_unit_basis(file, cv, qty, unit_str):
    """Set cv.UnitBasis = IfcMeasureWithUnit(qty, unit_entity). Returns True on success."""
    if not unit_str:
        return False
    try:
        unit_entity = get_or_create_unit_entity(file, unit_str)
        wrapped_qty = file.create_entity("IfcNumericMeasure", qty)
        unit_basis = file.create_entity(
            "IfcMeasureWithUnit",
            ValueComponent=wrapped_qty,
            UnitComponent=unit_entity,
        )
        cv.UnitBasis = unit_basis
        return True
    except Exception:
        return False


def _ifc_str(s):
    """Strip whitespace; return None if empty (IfcLabel must be non-empty)."""
    s = (s or "").strip()
    return s or None


_UNIT_TO_IFC_QUANTITY = {
    # Area
    "m2":    ("IfcQuantityArea",   "AreaValue"),
    "mq":    ("IfcQuantityArea",   "AreaValue"),
    "m²":    ("IfcQuantityArea",   "AreaValue"),
    "mq/cm": ("IfcQuantityArea",   "AreaValue"),   # surface × thickness layer; area is the input
    # Volume
    "m3":    ("IfcQuantityVolume", "VolumeValue"),
    "mc":    ("IfcQuantityVolume", "VolumeValue"),
    "m³":    ("IfcQuantityVolume", "VolumeValue"),
    "l":     ("IfcQuantityVolume", "VolumeValue"),   # litri
    "dmc":   ("IfcQuantityVolume", "VolumeValue"),   # dm³
    "cmc":   ("IfcQuantityVolume", "VolumeValue"),   # cm³
    # Length
    "m":     ("IfcQuantityLength", "LengthValue"),
    "ml":    ("IfcQuantityLength", "LengthValue"),
    "lm":    ("IfcQuantityLength", "LengthValue"),
    "cm":    ("IfcQuantityLength", "LengthValue"),
    "dm":    ("IfcQuantityLength", "LengthValue"),
    "km":    ("IfcQuantityLength", "LengthValue"),
    # Weight
    "kg":    ("IfcQuantityWeight", "WeightValue"),
    "t":     ("IfcQuantityWeight", "WeightValue"),
    "ton":   ("IfcQuantityWeight", "WeightValue"),
    "q":     ("IfcQuantityWeight", "WeightValue"),
    "100 kg":("IfcQuantityWeight", "WeightValue"),
    # Time
    "h":     ("IfcQuantityTime",   "TimeValue"),
    "ore":   ("IfcQuantityTime",   "TimeValue"),
    "ora":   ("IfcQuantityTime",   "TimeValue"),
    "min":   ("IfcQuantityTime",   "TimeValue"),
    # Count — dimensionless or non-mappable units
    "n":       ("IfcQuantityCount", "CountValue"),
    "n.":      ("IfcQuantityCount", "CountValue"),
    "nr":      ("IfcQuantityCount", "CountValue"),
    "nr.":     ("IfcQuantityCount", "CountValue"),
    "cad":     ("IfcQuantityCount", "CountValue"),
    "pz":      ("IfcQuantityCount", "CountValue"),
    "corpo":   ("IfcQuantityCount", "CountValue"),
    "a corpo": ("IfcQuantityCount", "CountValue"),
    "paio":    ("IfcQuantityCount", "CountValue"),
    "coppia":  ("IfcQuantityCount", "CountValue"),
    "kw":      ("IfcQuantityCount", "CountValue"),   # power — no IfcPhysicalSimpleQuantity subtype in IFC4
    "kn":      ("IfcQuantityCount", "CountValue"),   # force — no IfcPhysicalSimpleQuantity subtype in IFC4
}


def _ifc_quantity_type(unit_str):
    """Map an XPWE unit string to (IfcClass, value_attribute) for IfcCostItem.CostQuantities."""
    return _UNIT_TO_IFC_QUANTITY.get(unit_str.lower().strip(), ("IfcQuantityCount", "CountValue"))


# Canonical quantity type info — single source of truth shared across modules.
# Keys are the Blender enum identifiers used in prop.py.
QTY_TYPE_INFO = {
    'AREA':   {'label': "Area",   'ifc_class': "IfcQuantityArea",   'value_attr': "AreaValue",    'abbr': "m²"},
    'VOLUME': {'label': "Volume", 'ifc_class': "IfcQuantityVolume",  'value_attr': "VolumeValue",  'abbr': "m³"},
    'LENGTH': {'label': "Length", 'ifc_class': "IfcQuantityLength",  'value_attr': "LengthValue",  'abbr': "m"},
    'COUNT':  {'label': "Count",  'ifc_class': "IfcQuantityCount",   'value_attr': "CountValue",   'abbr': ""},
    'WEIGHT': {'label': "Weight", 'ifc_class': "IfcQuantityWeight",  'value_attr': "WeightValue",  'abbr': "kg"},
    'TIME':   {'label': "Time",   'ifc_class': "IfcQuantityTime",    'value_attr': "TimeValue",    'abbr': "h"},
    # IFC4X3 only — generic numeric value (not a discrete count)
    'NUMBER': {'label': "Number", 'ifc_class': "IfcQuantityNumber",  'value_attr': "NumberValue",  'abbr': ""},
}
# Reverse: IfcClassName → type_id
QTY_FROM_IFC_CLASS = {info['ifc_class']: k for k, info in QTY_TYPE_INFO.items()}


def refresh_cost_ui(tool):
    """Refresh the Bonsai cost schedule tree. Call after any IFC cost modification."""
    import bpy
    import bonsai.bim.module.cost.data
    bonsai.bim.module.cost.data.refresh()
    if bpy.context.scene.BIMCostProperties.active_cost_schedule_id != 0:
        tool.Cost.load_cost_schedule_tree()


# Internal alias kept for backward compat with calls inside this file.
_refresh_ui = refresh_cost_ui


def get_cost_item_children(item):
    """Return direct IfcCostItem children of item via IsNestedBy."""
    return [
        obj
        for rel in (item.IsNestedBy or [])
        for obj in (rel.RelatedObjects or [])
        if obj.is_a("IfcCostItem")
    ]


def is_summary_cost_item(item):
    """True if item has a SUM cost value (Category='*')."""
    return any(getattr(cv, "Category", None) == "*" for cv in (item.CostValues or []))


def remove_all_cost_values(tool, item):
    """Remove all direct CostValues from item using the Bonsai undo-safe API."""
    for cv in list(item.CostValues or []):
        tool.Ifc.run("cost.remove_cost_value", parent=item, cost_value=cv)


# ---------------------------------------------------------------------------
# Rate list → cost item creation
# ---------------------------------------------------------------------------

def get_parent_desc(selected_rate):
    import bpy
    rate_attrib = json.loads(selected_rate.attributes)
    parent_indices = [p for p in rate_attrib.get("parents", "").split(",") if p.strip()]
    if not parent_indices:
        return ""
    parent_idx = int(parent_indices[-1])
    items = bpy.context.scene.xml_rate_list
    if parent_idx < len(items):
        return json.loads(items[parent_idx].attributes).get("desc", "")
    return ""


def create_cost_item(file, selected_rate, create_new_item=True, combine_desc=False):
    import bpy
    from bonsai import tool
    import ifcopenshell.util.cost
    import bonsai.bim.module.cost.data

    active_ui_cost_item = bpy.context.scene.BIMCostProperties.active_cost_item
    active_ifc_cost_item = file.by_id(active_ui_cost_item.ifc_definition_id)

    if create_new_item:
        if active_ifc_cost_item in ifcopenshell.util.cost.get_root_cost_items(
            file.by_id(bpy.context.scene.BIMCostProperties.active_cost_schedule_id)
        ):
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item)
        elif active_ui_cost_item.has_children:
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item)
        else:
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item.Nests[0].RelatingObject)
    else:
        cost_item = active_ifc_cost_item
        if cost_item.CostValues:
            for cost_value in list(cost_item.CostValues):
                tool.Ifc.run("cost.remove_cost_value", parent=cost_item, cost_value=cost_value)

    rate_attrib = json.loads(selected_rate.attributes)
    if combine_desc:
        parent_desc = get_parent_desc(selected_rate)
        desc = (parent_desc + "\n" + rate_attrib["desc"]).strip() if parent_desc else rate_attrib["desc"]
    else:
        desc = rate_attrib["desc"]

    tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
        "Identification": rate_attrib["id"],
        "Name": rate_attrib["name"],
        "Description": desc,
    })

    labor = float(rate_attrib["labor"])
    equipment = float(rate_attrib["equipment"])
    materials = float(rate_attrib["materials"])
    safety = float(rate_attrib["safety"])
    total_value = float(rate_attrib["value"])
    unit = rate_attrib.get("unit", "")

    components = [
        ("Labor", labor),
        ("Equipment", equipment),
        ("Materials", materials),
        ("Safety", safety),
    ]
    has_components = any(v != 0.0 for _, v in components)

    if not has_components:
        cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value,
                     attributes={"AppliedValue": round(total_value, 2)})
        set_unit_basis(file, cost_value, 1.0, unit)
    else:
        remaining = round(total_value - sum(v for _, v in components), 2)
        if remaining != 0.0:
            cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value,
                         attributes={"AppliedValue": remaining})
            set_unit_basis(file, cost_value, 1.0, unit)
        for category, amount in components:
            if amount != 0.0:
                cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={
                    "Category": category,
                    "AppliedValue": round(amount, 2),
                })
                set_unit_basis(file, cost_value, 1.0, unit)

    _refresh_ui(tool)


# ---------------------------------------------------------------------------
# XPWE → IFC schedule builders
# ---------------------------------------------------------------------------

def build_schedule_from_xpwe(parser, schedule_name, report=None, flatten=True):
    """Create a new IfcCostSchedule (EPU/SoR) from parser.xml_rate_list.

    Returns (True, ep_ifc_map) on success, (False, {}) on failure.
    ep_ifc_map maps {xml_ep_id: IfcCostItem} for the CME linker.
    """
    try:
        from bonsai import tool
        import bonsai.bim.module.cost.data
    except ImportError as e:
        if report:
            report({'ERROR'}, f"Bonsai not available: {e}")
        return False, {}

    file = tool.Ifc.get()
    if file is None:
        if report:
            report({'ERROR'}, "No IFC file loaded")
        return False, {}

    try:
        schedule = tool.Ifc.run(
            "cost.add_cost_schedule",
            name=schedule_name,
            predefined_type="SCHEDULEOFRATES",
        )

        index_to_ifc = {}

        if flatten:
            epu_root = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
            tool.Ifc.run("cost.edit_cost_item", cost_item=epu_root, attributes={
                "Identification": None,
                "Name": "EPU",
                "Description": None,
            })

        for rate in parser.xml_rate_list:
            parent_indices = [int(p) for p in rate["parents"].split(",") if p.strip()]

            if flatten:
                if rate["is_parent"]:
                    index_to_ifc[rate["index"]] = epu_root
                    continue
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=epu_root)
            elif not parent_indices:
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
            else:
                cost_item = tool.Ifc.run("cost.add_cost_item",
                                         cost_item=index_to_ifc[parent_indices[-1]])

            tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
                "Identification": _ifc_str(rate["id"]),
                "Name": _ifc_str(rate["name"]),
                "Description": _ifc_str(rate["desc"]),
            })

            if not rate["is_parent"]:
                value = float(rate["value"])
                unit = rate.get("unit", "")
                components = [
                    ("Labor",     float(rate["labor"])),
                    ("Equipment", float(rate["equipment"])),
                    ("Materials", float(rate["materials"])),
                    ("Safety",    float(rate["safety"])),
                ]
                has_components = any(v != 0.0 for _, v in components)

                if not has_components:
                    if value != 0.0:
                        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                        tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                     attributes={"AppliedValue": round(value, 2)})
                        set_unit_basis(file, cv, 1.0, unit)
                else:
                    remaining = round(value - sum(v for _, v in components), 2)
                    if remaining != 0.0:
                        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                        tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                     attributes={"AppliedValue": remaining})
                        set_unit_basis(file, cv, 1.0, unit)
                    for category, amount in components:
                        if amount != 0.0:
                            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                                "Category": category,
                                "AppliedValue": round(amount, 2),
                            })
                            set_unit_basis(file, cv, 1.0, unit)

            index_to_ifc[rate["index"]] = cost_item

        ep_ifc_map = {
            xml_id: index_to_ifc[ep["index"]]
            for xml_id, ep in parser._ep_by_xml_id.items()
            if ep["index"] in index_to_ifc
        }

        _refresh_ui(tool)

    except Exception as e:
        if report:
            import traceback
            report({'ERROR'}, f"EPU import failed: {e}\n{traceback.format_exc()}")
        return False, {}

    return True, ep_ifc_map


def build_cme_schedule(parser, schedule_name, ep_ifc_map, report=None, import_measurement_rows=False):
    """Create an IfcCostSchedule (CME/BoQ) from parser.xml_computo_list.

    ep_ifc_map: {xml_ep_id: IfcCostItem} from build_schedule_from_xpwe.
    Each leaf item's rate is linked via assign_cost_value so SoR price
    changes propagate automatically to the BoQ.
    """
    try:
        from bonsai import tool
        from bonsai.core import cost as cost_core
        import bonsai.bim.module.cost.data
    except ImportError as e:
        if report:
            report({'ERROR'}, f"Bonsai not available: {e}")
        return False

    file = tool.Ifc.get()
    if file is None:
        if report:
            report({'ERROR'}, "No IFC file loaded")
        return False

    try:
        schedule = tool.Ifc.run(
            "cost.add_cost_schedule",
            name=schedule_name,
            predefined_type="PRICEDBILLOFQUANTITIES",
        )

        index_to_ifc = {}

        for rate in parser.xml_computo_list:
            parent_indices = [int(p) for p in rate["parents"].split(",") if p.strip()]

            if not parent_indices:
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
            else:
                cost_item = tool.Ifc.run("cost.add_cost_item",
                                         cost_item=index_to_ifc[parent_indices[-1]])

            tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
                "Identification": _ifc_str(rate["id"]),
                "Name": _ifc_str(rate["name"]),
                "Description": _ifc_str(rate["desc"]),
            })

            if rate["is_parent"]:
                # SUM: Bonsai's add_cost_value with cost_type="SUM" sets up
                # the aggregation so chapter subtotals are visible in the UI
                import bpy as _bpy
                _bpy.ops.bim.add_cost_value(parent=cost_item.id(), cost_type="SUM")
            else:
                ep_xml_id = rate.get("ep_xml_id", "")
                cost_rate = ep_ifc_map.get(ep_xml_id)
                quantity = float(rate.get("quantity", 0.0))

                if cost_rate is not None:
                    cost_core.assign_cost_value(
                        tool.Ifc, tool.Cost,
                        cost_item=cost_item,
                        cost_rate=cost_rate,
                    )
                elif float(rate["value"]) != 0.0:
                    cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                    tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                 attributes={"AppliedValue": round(float(rate["value"]), 2)})

                unit = rate.get("unit", "")
                ifc_class, value_attr = _ifc_quantity_type(unit)
                rg_items = rate.get("rg_items") or []
                if import_measurement_rows and rg_items:
                    new_qtys = []
                    for rg in rg_items:
                        if rg["qty"] == 0.0:
                            continue
                        kw = {
                            "Name": rg["desc"] or "Qty",
                            value_attr: round(rg["qty"], 4),
                        }
                        if rg.get("formula"):
                            kw["Formula"] = rg["formula"]
                        new_qtys.append(file.create_entity(ifc_class, **kw))
                    if new_qtys:
                        cost_item.CostQuantities = list(cost_item.CostQuantities or []) + new_qtys
                elif quantity != 0.0:
                    qty = file.create_entity(ifc_class, **{
                        "Name": rate.get("qty_name") or "Qty",
                        value_attr: round(quantity, 4),
                    })
                    cost_item.CostQuantities = list(cost_item.CostQuantities or []) + [qty]

            index_to_ifc[rate["index"]] = cost_item

        _refresh_ui(tool)

    except Exception as e:
        if report:
            import traceback
            report({'ERROR'}, f"CME import failed: {e}\n{traceback.format_exc()}")
        return False

    return True
