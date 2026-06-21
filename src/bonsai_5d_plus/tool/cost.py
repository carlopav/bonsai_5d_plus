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


# IfcCostSchedule.PredefinedType values handled as a priced Bill of Quantities:
# the proper priced BoQ plus cost estimates (ESTIMATE), cost plans (COSTPLAN) and
# budgets (BUDGET), which carry priced cost items with quantities and so use the
# same handling and PDF template. Single source of truth shared across modules.
PRICED_BOQ_TYPES = ("PRICEDBILLOFQUANTITIES", "ESTIMATE", "COSTPLAN", "BUDGET")


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
# factor = how many SI-base units one of these equals (e.g. 1 cm² = 0.0001 m²).
# Area sub-multiples MUST be conversion units, not prefixed IfcSIUnit: ifcopenshell
# applies an SI prefix linearly even to SQUARE_METRE, so SQUARE_METRE+CENTI would
# wrongly scale to 0.01 m² instead of 0.0001 m².
_UNIT_TO_CONVERSION_DESCRIPTOR = {
    "h":   ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "ore": ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "ora": ("TIMEUNIT", "HOUR",   3600.0, "TIMEUNIT", "SECOND", None),
    "min": ("TIMEUNIT", "MINUTE",   60.0, "TIMEUNIT", "SECOND", None),
    # Area sub-multiples (relative to SQUARE_METRE)
    "dm2": ("AREAUNIT", "SQUARE_DECIMETRE",  0.01,   "AREAUNIT", "SQUARE_METRE", None),
    "dmq": ("AREAUNIT", "SQUARE_DECIMETRE",  0.01,   "AREAUNIT", "SQUARE_METRE", None),
    "dm²": ("AREAUNIT", "SQUARE_DECIMETRE",  0.01,   "AREAUNIT", "SQUARE_METRE", None),
    "cm2": ("AREAUNIT", "SQUARE_CENTIMETRE", 0.0001, "AREAUNIT", "SQUARE_METRE", None),
    "cmq": ("AREAUNIT", "SQUARE_CENTIMETRE", 0.0001, "AREAUNIT", "SQUARE_METRE", None),
    "cm²": ("AREAUNIT", "SQUARE_CENTIMETRE", 0.0001, "AREAUNIT", "SQUARE_METRE", None),
    # Mass: 1 quintal = 100 kg
    "q":        ("MASSUNIT", "QUINTAL", 100.0, "MASSUNIT", "GRAM", "KILO"),
    "quintale": ("MASSUNIT", "QUINTAL", 100.0, "MASSUNIT", "GRAM", "KILO"),
    "quintali": ("MASSUNIT", "QUINTAL", 100.0, "MASSUNIT", "GRAM", "KILO"),
}

# UnitType → IfcDimensionalExponents tuple
# (Length, Mass, Time, ElectricCurrent, Temperature, Substance, Luminous).
_UNIT_TYPE_EXPONENTS = {
    "LENGTHUNIT": (1, 0, 0, 0, 0, 0, 0),
    "AREAUNIT":   (2, 0, 0, 0, 0, 0, 0),
    "VOLUMEUNIT": (3, 0, 0, 0, 0, 0, 0),
    "MASSUNIT":   (0, 1, 0, 0, 0, 0, 0),
    "TIMEUNIT":   (0, 0, 1, 0, 0, 0, 0),
}


# Reverse lookups: IFC unit entity → preferred display abbreviation
_SI_DESCRIPTOR_TO_ABBR = {}
for _abbr, _desc in _UNIT_TO_SI_DESCRIPTOR.items():
    if _desc not in _SI_DESCRIPTOR_TO_ABBR:
        _SI_DESCRIPTOR_TO_ABBR[_desc] = _abbr

_CONVERSION_NAME_TO_ABBR = {}
for _abbr, (_, _name, *_) in _UNIT_TO_CONVERSION_DESCRIPTOR.items():
    if _name not in _CONVERSION_NAME_TO_ABBR:
        _CONVERSION_NAME_TO_ABBR[_name] = _abbr


def ifc_unit_to_str(unit_entity):
    """Return the preferred display abbreviation for an IFC unit entity."""
    if unit_entity is None:
        return ""
    if unit_entity.is_a("IfcSIUnit"):
        key = (unit_entity.UnitType, unit_entity.Name, unit_entity.Prefix or None)
        return _SI_DESCRIPTOR_TO_ABBR.get(key, str(unit_entity.Name or ""))
    if unit_entity.is_a("IfcConversionBasedUnit"):
        name = (getattr(unit_entity, "Name", None) or "").upper()
        return _CONVERSION_NAME_TO_ABBR.get(name, str(getattr(unit_entity, "Name", None) or ""))
    return str(getattr(unit_entity, "Name", None) or "")


def _find_si_unit(file, unit_type, si_name, prefix):
    for u in file.by_type("IfcSIUnit"):
        if u.UnitType == unit_type and u.Name == si_name and (u.Prefix or None) == prefix:
            return u
    return None


def _get_or_create_si_unit(file, unit_type, si_name, prefix):
    found = _find_si_unit(file, unit_type, si_name, prefix)
    if found:
        return found
    attrs = {"UnitType": unit_type, "Name": si_name}
    if prefix:
        attrs["Prefix"] = prefix
    return file.create_entity("IfcSIUnit", **attrs)


def _make_dimensional_exponents(file, unit_type):
    e = _UNIT_TYPE_EXPONENTS.get(unit_type, (0, 0, 0, 0, 0, 0, 0))
    return file.create_entity(
        "IfcDimensionalExponents",
        LengthExponent=e[0], MassExponent=e[1], TimeExponent=e[2],
        ElectricCurrentExponent=e[3], ThermodynamicTemperatureExponent=e[4],
        AmountOfSubstanceExponent=e[5], LuminousIntensityExponent=e[6],
    )


def get_or_create_unit_entity(file, unit_str):
    """Return an IFC unit entity for unit_str, reusing project units where possible."""
    key = unit_str.lower().strip()

    si_desc = _UNIT_TO_SI_DESCRIPTOR.get(key)
    if si_desc:
        return _get_or_create_si_unit(file, *si_desc)

    conv_desc = _UNIT_TO_CONVERSION_DESCRIPTOR.get(key)
    if conv_desc:
        unit_type, name, factor, base_type, base_name, base_prefix = conv_desc
        for u in file.by_type("IfcConversionBasedUnit"):
            if u.UnitType == unit_type and (u.Name or "").upper() == name:
                return u
        base_si = _get_or_create_si_unit(file, base_type, base_name, base_prefix)
        dims = _make_dimensional_exponents(file, unit_type)
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
    if not qty:
        return False
    effective_unit = unit_str if unit_str else "1"
    try:
        unit_entity = get_or_create_unit_entity(file, effective_unit)
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
    "dm2":   ("IfcQuantityArea",   "AreaValue"),
    "dmq":   ("IfcQuantityArea",   "AreaValue"),
    "dm²":   ("IfcQuantityArea",   "AreaValue"),
    "cm2":   ("IfcQuantityArea",   "AreaValue"),
    "cmq":   ("IfcQuantityArea",   "AreaValue"),
    "cm²":   ("IfcQuantityArea",   "AreaValue"),
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
    "quintale": ("IfcQuantityWeight", "WeightValue"),
    "quintali": ("IfcQuantityWeight", "WeightValue"),
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


def ifc_quantity_type(unit_str):
    """Map a unit string to (IfcClass, value_attribute) for IfcCostItem.CostQuantities."""
    return _UNIT_TO_IFC_QUANTITY.get((unit_str or "").lower().strip(), ("IfcQuantityCount", "CountValue"))


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
# EPU -> CME rate synchronisation
#
# A CME/BoQ cost item borrows its price from a rate item (EPU/Schedule of
# Rates) via IfcRelAssignsToControl + shared IfcCostValue entities (Bonsai's
# assign_cost_value). The rate is the single source of truth (one-way EPU->CME).
# Rewriting a rate's cost values replaces the entities and breaks the share, so
# after any rate edit we re-share the values and (on demand) propagate Name /
# Description / Identification to the dependents.
# ---------------------------------------------------------------------------

def get_cost_item_schedule(item):
    """The IfcCostSchedule an IfcCostItem belongs to (walks up the nesting)."""
    for rel in (item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcCostSchedule"):
            return rel.RelatingControl
    for rel in (item.Nests or []):
        return get_cost_item_schedule(rel.RelatingObject)
    return None


def get_rate_controller(item):
    """The rate IfcCostItem controlling this one (IfcRelAssignsToControl), or None."""
    for rel in (item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                return ctrl
    return None


def get_rate_dependents(rate_item):
    """Cost items controlled by this rate item (via IfcRelAssignsToControl)."""
    return [
        obj
        for rel in (getattr(rate_item, "Controls", None) or [])
        for obj in (rel.RelatedObjects or [])
        if obj.is_a("IfcCostItem")
    ]


def _same_cost_values(a, b):
    """True if two cost items reference the exact same IfcCostValue entities."""
    return [cv.id() for cv in (a.CostValues or [])] == [cv.id() for cv in (b.CostValues or [])]


def rate_dependent_diffs(rate_item):
    """Attributes out of sync between the rate and at least one dependent.

    Returns a subset of {"name", "description", "value"}.
    """
    diffs = set()
    for dep in get_rate_dependents(rate_item):
        if (dep.Name or "") != (rate_item.Name or ""):
            diffs.add("name")
        if (dep.Description or "") != (rate_item.Description or ""):
            diffs.add("description")
        if not _same_cost_values(dep, rate_item):
            diffs.add("value")
    return diffs


def is_item_in_sync(item):
    """For a CME item linked to a rate: True if name/description/value all match.

    Returns None when the item has no rate controller (not applicable).
    """
    rate = get_rate_controller(item)
    if rate is None:
        return None
    return (
        (item.Name or "") == (rate.Name or "")
        and (item.Description or "") == (rate.Description or "")
        and _same_cost_values(item, rate)
    )


def group_dependents_by_schedule(rate_item):
    """Return [(schedule, [dependents])], grouping a rate's dependents by schedule.

    ``schedule`` is the IfcCostSchedule entity (None when unresolvable); order is
    stable by first appearance.
    """
    groups = {}
    order = []
    for dep in get_rate_dependents(rate_item):
        sch = get_cost_item_schedule(dep)
        key = sch.id() if sch is not None else 0
        if key not in groups:
            groups[key] = (sch, [])
            order.append(key)
        groups[key][1].append(dep)
    return [groups[k] for k in order]


def resync_rate_values(tool, rate_item):
    """Re-share the rate's current CostValues onto every dependent (silent).

    Uses Bonsai's native cost.assign_cost_value so dependents point at the same
    IfcCostValue entities again. Returns the number of dependents.
    """
    deps = get_rate_dependents(rate_item)
    for dep in deps:
        if not _same_cost_values(dep, rate_item):
            tool.Ifc.run("cost.assign_cost_value", cost_item=dep, cost_rate=rate_item)
    return len(deps)


def propagate_rate_to_dependents(tool, rate_item, with_identification=False):
    """Propagate the rate to its dependents: re-share values + copy Name and
    Description (and Identification when requested). Returns the dependent count.
    """
    deps = get_rate_dependents(rate_item)
    for dep in deps:
        if not _same_cost_values(dep, rate_item):
            tool.Ifc.run("cost.assign_cost_value", cost_item=dep, cost_rate=rate_item)
        attrs = {"Name": rate_item.Name, "Description": rate_item.Description}
        if with_identification:
            attrs["Identification"] = rate_item.Identification
        tool.Ifc.run("cost.edit_cost_item", cost_item=dep, attributes=attrs)
    return len(deps)


def align_item_to_rate(tool, item, with_identification=False):
    """Pull a single CME item back in line with its controlling rate: re-share
    values + copy Name/Description (and Identification when requested). Returns
    False when the item has no rate controller.
    """
    rate = get_rate_controller(item)
    if rate is None:
        return False
    if not _same_cost_values(item, rate):
        tool.Ifc.run("cost.assign_cost_value", cost_item=item, cost_rate=rate)
    attrs = {"Name": rate.Name, "Description": rate.Description}
    if with_identification:
        attrs["Identification"] = rate.Identification
    tool.Ifc.run("cost.edit_cost_item", cost_item=item, attributes=attrs)
    return True


# ---------------------------------------------------------------------------
# Cost value writers
# ---------------------------------------------------------------------------

def write_epu_cost_values(file, tool, cost_item, total_value, unit, incidences):
    """Write a prezzario/EPU item's cost as flat, categorised top-level CostValues.

    One IfcCostValue per non-zero incidence category (plus an uncategorised
    remainder when the breakdown doesn't cover the whole value), each created
    via the Bonsai API for undo safety, with AppliedValue = the category total
    and UnitBasis = (1.0, unit).

    The categories are kept at the top level — not nested under a summary —
    because the ifc5d exporter only reads top-level CostValue categories.
    Nesting would hide the per-category totals (e.g. Labor) that the cost
    documents need; here we only need the category total, not a cost tree.

    incidences: list of (category_str, amount_float), e.g.
        [("Labor", 30.0), ("Equipment", 0.0), ("Material", 60.0), ("Safety", 10.0)]
    """
    if total_value == 0.0:
        # Keep any dependents aligned with the (now empty) rate too.
        resync_rate_values(tool, cost_item)
        return

    active = [(cat, amt) for cat, amt in incidences if amt != 0.0]
    remaining = round(total_value - sum(amt for _, amt in active), 2)

    rows = []
    # Uncategorised remainder, or the whole value when no breakdown is known.
    if remaining != 0.0 or not active:
        rows.append((None, remaining if active else total_value))
    rows.extend(active)

    for category, amount in rows:
        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        attributes = {"AppliedValue": round(amount, 2)}
        if category:
            attributes["Category"] = category
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes=attributes)
        set_unit_basis(file, cv, 1.0, unit)

    # Re-share the freshly written values onto any control-linked dependents
    # (the rewrite above replaced the entities, breaking the previous share).
    resync_rate_values(tool, cost_item)


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

    write_epu_cost_values(file, tool, cost_item,
        total_value=float(rate_attrib["value"]),
        unit=rate_attrib.get("unit", ""),
        incidences=[
            ("Labor",     float(rate_attrib["labor"])),
            ("Equipment", float(rate_attrib["equipment"])),
            ("Material", float(rate_attrib["materials"])),
            ("Safety",    float(rate_attrib["safety"])),
        ],
    )

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
                write_epu_cost_values(file, tool, cost_item,
                    total_value=float(rate["value"]),
                    unit=rate.get("unit", ""),
                    incidences=[
                        ("Labor",     float(rate["labor"])),
                        ("Equipment", float(rate["equipment"])),
                        ("Material", float(rate["materials"])),
                        ("Safety",    float(rate["safety"])),
                    ],
                )

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
                ifc_class, value_attr = ifc_quantity_type(unit)
                rg_items = rate.get("rg_items") or []
                if import_measurement_rows and rg_items:
                    new_qtys = []
                    for rg in rg_items:
                        # Keep note/heading rows (qty 0 with text); skip only the
                        # truly empty placeholder rows (no text, no value).
                        if rg["qty"] == 0.0 and not rg["desc"]:
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
                        # All rows were empty placeholders → keep the VCItem total.
                        qty = file.create_entity(ifc_class, **{
                            "Name": rate.get("qty_name") or "Qty",
                            value_attr: round(quantity, 4),
                        })
                        cost_item.CostQuantities = list(cost_item.CostQuantities or []) + [qty]
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
