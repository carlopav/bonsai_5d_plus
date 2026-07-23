# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import re
import time as _time
import bpy

from ...tool.cost import (
    QTY_TYPE_INFO,
    QTY_FROM_IFC_CLASS,
    refresh_cost_ui,
    ifc_unit_to_str,
    project_unit_entities,
    resolve_unit_choice,
    set_unit_basis_entity,
    ifc_quantity_type_from_unit,
    get_rate_dependents,
    resync_rate_values,
    get_rate_controller,
    unlink_from_rate,
    duplicate_and_relink_rate,
    is_summary_cost_item,
    move_cost_item,
    build_cost_value_ref,
    parse_cost_value_ref,
)
from ..toolbox.cost_sync.operator import schedule_propagate_popup

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)

# ---------------------------------------------------------------------------
# Constants (used by prop.py, ui.py)
# ---------------------------------------------------------------------------

COMPONENT_CATEGORIES = (
    ('NONE',         "—",            "No category (existing value, not a rate analysis component)"),
    ('SUB_CONTRACT', "Sub-Contract", "Subcontracted works (opere compiute)"),
    ('LABOR',        "Labor",        "Labor costs (manodopera)"),
    ('EQUIPMENT',    "Equipment",    "Equipment rental costs (noli)"),
    ('MATERIAL',     "Material",     "Material costs (materiali)"),
    ('SAFETY',       "Safety",       "Safety costs (oneri sicurezza)"),
)

# ---------------------------------------------------------------------------
# Unit of measure picker — shared by the Fixed panel's list-wide unit, the
# Rate Analysis panel's per-component unit, and its overall "final price"
# unit. Primary choices are the project's own declared units (IfcProject.
# UnitsInContext.Units), shown as IFC-native "UNITTYPE / NAME" labels (no
# abbreviation translation) via Bonsai's own tool.Cost.format_unit(). A unit
# already referenced by the item being edited is always included even if it
# isn't part of the project's declared units (legacy files).
# ---------------------------------------------------------------------------

_unit_items_cache = []  # prevents GC of the enum item strings (dynamic items)

# Cache for _custom_units_in_use(): a dynamic EnumProperty items callback runs
# on every redraw (and once per row for Rate Analysis components), so a full
# file.by_type("IfcCostValue") scan on every call would add up needlessly.
# Explicitly invalidated (_invalidate_custom_units_cache) right after our own
# Apply operators write a new UnitBasis, so a just-typed custom unit is
# immediately offered elsewhere — no rescan needed during normal browsing.
# The TTL is only a safety net for cost values changed outside our own
# operators (e.g. Bonsai's native editor); keyed by file identity so
# switching IFC files can't serve another file's stale results.
_custom_units_cache = {"file": None, "time": 0.0, "units": []}
_CUSTOM_UNITS_CACHE_TTL = 10.0  # seconds — safety net only, see above


def _invalidate_custom_units_cache():
    _custom_units_cache["time"] = 0.0


def _custom_units_in_use(file):
    """Unit entities already referenced by some IfcCostValue.UnitBasis or
    IfcPhysicalSimpleQuantity.Unit anywhere in the file — offered in the unit
    picker so a custom unit typed once (e.g. "a corpo") can be reused on
    other items instead of retyped (and duplicated as a near-identical
    entity)."""
    global _custom_units_cache
    now = _time.monotonic()
    if _custom_units_cache["file"] is file and now - _custom_units_cache["time"] < _CUSTOM_UNITS_CACHE_TTL:
        return _custom_units_cache["units"]
    seen_ids = set()
    found = []
    for cv in file.by_type("IfcCostValue"):
        ub = getattr(cv, "UnitBasis", None)
        unit = getattr(ub, "UnitComponent", None) if ub is not None else None
        if unit is not None and unit.id() not in seen_ids:
            seen_ids.add(unit.id())
            found.append(unit)
    for q in file.by_type("IfcPhysicalSimpleQuantity"):
        unit = getattr(q, "Unit", None)
        if unit is not None and unit.id() not in seen_ids:
            seen_ids.add(unit.id())
            found.append(unit)
    _custom_units_cache = {"file": file, "time": now, "units": found}
    return found


def _unit_enum_items(self, context):
    global _unit_items_cache
    items = [('NONE', "— (none)", "No unit")]
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is not None:
            seen_ids = set()
            for unit in project_unit_entities(file):
                items.append((str(unit.id()), tool.Cost.format_unit(unit), ""))
                seen_ids.add(unit.id())
            for unit in _custom_units_in_use(file):
                if unit.id() not in seen_ids:
                    label = f"{tool.Cost.format_unit(unit)}  (not in project units)"
                    items.append((str(unit.id()), label, ""))
                    seen_ids.add(unit.id())
    except Exception:
        pass
    items.append(('USERDEFINED', "Custom…", "Enter a custom unit string"))
    _unit_items_cache = items
    return _unit_items_cache


def _unit_display_label(unit_value, custom_str=""):
    """Compact label for a resolved unit choice — for list rows, not the
    picker itself (which uses the fuller IFC-native format_unit label)."""
    if not unit_value or unit_value == 'NONE':
        return ""
    if unit_value == 'USERDEFINED':
        return custom_str or ""
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        unit = file.by_id(int(unit_value)) if file else None
    except Exception:
        unit = None
    if unit is None:
        return ""
    name = unit.Name or ""
    prefix = getattr(unit, "Prefix", None)
    return f"{prefix} {name}" if prefix else name


_TO_IFC = {
    'SUB_CONTRACT': 'Sub-Contract',
    'LABOR':        'Labor',
    'EQUIPMENT':    'Equipment',
    'MATERIAL':     'Material',
    'SAFETY':       'Safety',
}
_FROM_IFC = {v: k for k, v in _TO_IFC.items()}
_CATEGORY_WRITE_ORDER = ['SUB_CONTRACT', 'LABOR', 'EQUIPMENT', 'MATERIAL', 'SAFETY']

_LINE_CATEGORIES = set(_TO_IFC.values())


def _detect_component_category(rate_item):
    """Classify a source cost item as a rate-analysis component category.

    A pure single-category resource — its whole value in one IFC category with
    no uncategorised remainder — maps to that category (LABOR / EQUIPMENT /
    MATERIAL / ...).  Composite works, or items carrying an uncategorised part,
    fall back to SUB_CONTRACT.
    """
    line_cats = []
    has_uncategorised = False
    for cv in rate_item.CostValues or []:
        cat = getattr(cv, "Category", None)
        if cat in _LINE_CATEGORIES:
            line_cats.append(cat)
        elif cat != "*":  # None / "General" / anything else = uncategorised part
            has_uncategorised = True
    if len(line_cats) == 1 and not has_uncategorised:
        return _FROM_IFC.get(line_cats[0], 'SUB_CONTRACT')
    return 'SUB_CONTRACT'

# ---------------------------------------------------------------------------
# Quantity (libretto delle misure) — derived from tool.cost.QTY_TYPE_INFO
# ---------------------------------------------------------------------------

_QTY_VALUE_ATTR = {k: v['value_attr'] for k, v in QTY_TYPE_INFO.items()}
_QTY_FROM_IFC   = QTY_FROM_IFC_CLASS

_SAFETY_PCT_CAT = "Safety Percentage"
_OVERHEAD_CAT = "Overhead"
_PROFIT_CAT = "Profit"
_ROUNDING_CAT = "Rounding"
# The markup block doubles as the boundary between components that are subject to
# markups and those already inclusive of them — see _write_analysis_values.
_MARKUP_CATEGORIES = {_SAFETY_PCT_CAT, _OVERHEAD_CAT, _PROFIT_CAT, _ROUNDING_CAT}
_ALL_PA_CATEGORIES = _LINE_CATEGORIES | _MARKUP_CATEGORIES

_DESCRIPTION_TEXT_NAME = "Bonsai5D+_Description"

_build_cv_ref = build_cost_value_ref


def _parse_cv_source_id(cv):
    """Return source IFC step-ID from Description (new format) or Condition (legacy), or None."""
    return parse_cost_value_ref(cv)[1]

# ---------------------------------------------------------------------------
# Text editor helpers
# ---------------------------------------------------------------------------

def _open_text_editor(context, text):
    # Reuse any existing text editor in any open window
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = text
                area.spaces.active.show_word_wrap = True
                return
    # Open a new floating window and convert its largest area
    bpy.ops.wm.window_new()
    new_win = context.window_manager.windows[-1]
    target = max(new_win.screen.areas, key=lambda a: a.width * a.height, default=None)
    if target:
        target.type = 'TEXT_EDITOR'
        target.spaces.active.text = text
        target.spaces.active.show_word_wrap = True


def _close_text_editor(context):
    # Close a dedicated floating window that contains the text editor
    for window in list(context.window_manager.windows):
        if window == context.window:
            continue
        if any(a.type == 'TEXT_EDITOR' for a in window.screen.areas):
            with context.temp_override(window=window):
                bpy.ops.wm.window_close()
            return
    # Fallback: revert embedded text editor area back to 3D Viewport
    for area in context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            area.type = 'VIEW_3D'
            return


def _remove_description_text():
    if _DESCRIPTION_TEXT_NAME in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[_DESCRIPTION_TEXT_NAME])


# ---------------------------------------------------------------------------
# IFC helpers
# ---------------------------------------------------------------------------

def _get_rate_value_and_unit(file, source_ifc_id):
    """(total_value, unit_str) for a rate item's current CostValues, or (None, "")."""
    try:
        rate_item = file.by_id(source_ifc_id)
        cvs = list(rate_item.CostValues or [])
        if not cvs:
            return None, ""
        # Nested structure: summary CV holds the total directly, unit on the same CV
        if len(cvs) == 1 and (getattr(cvs[0], "Components", None) or []):
            v = cvs[0].AppliedValue
            total = float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else None
            _, unit_str = _read_unit_basis(cvs[0])
            return total, unit_str or ""
        # Flat structure (legacy / plain EPU / Fixed): sum all, take the first unit found
        total, found, unit_str = 0.0, False, ""
        for cv in cvs:
            if cv.AppliedValue is not None:
                v = cv.AppliedValue
                total += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
                found = True
            if not unit_str:
                _, u = _read_unit_basis(cv)
                if u:
                    unit_str = u
        return (total if found else None), unit_str
    except Exception:
        return None, ""


def _get_rate_current_value(file, source_ifc_id):
    return _get_rate_value_and_unit(file, source_ifc_id)[0]


def _get_totals(ed):
    """Rate-analysis totals, following the Italian "nuovo prezzo" worksheet.

    Safety, overhead and profit compound on the running total, and components
    flagged as already inclusive of them stay out of that base, joining only
    after the marked-up subtotal.

    Returns (ct_base, safety, overhead, profit, subtotal, ct_incl, final).
    """
    ct_base = sum(
        round(c.qty * c.unit_price, 2)
        for c in ed.rate_analysis_components
        if c.apply_markup
    )
    ct_incl = sum(
        round(c.qty * c.unit_price, 2)
        for c in ed.rate_analysis_components
        if not c.apply_markup
    )
    safety   = round(ct_base * ed.rate_analysis_safety_pct / 100.0, 2)
    overhead = round((ct_base + safety) * ed.rate_analysis_overhead_pct / 100.0, 2)
    profit   = round((ct_base + safety + overhead) * ed.rate_analysis_profit_pct / 100.0, 2)
    subtotal = ct_base + safety + overhead + profit
    final    = subtotal + ct_incl + ed.rate_analysis_rounding
    return ct_base, safety, overhead, profit, subtotal, ct_incl, final


# unit string → (UnitType, SIName, Prefix|None)  — reuse existing IfcSIUnit


def _read_unit_basis(cv):
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        unit_str = ifc_unit_to_str(ub.UnitComponent)
        return qty, unit_str
    except Exception:
        return None, None


def _read_unit_basis_entity(cv):
    """Like _read_unit_basis, but returns the raw unit entity instead of an
    abbreviation string — used to populate the unit picker on load."""
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        return qty, ub.UnitComponent
    except Exception:
        return None, None


def _unit_enum_value_for(unit_entity):
    """Unit picker enum identifier for a resolved unit entity: 'NONE' for no
    entity or the dimensionless "1" placeholder (set_unit_basis_entity's
    fallback), else the entity's IFC step-id as a string."""
    if unit_entity is None:
        return 'NONE'
    if unit_entity.is_a("IfcContextDependentUnit") and unit_entity.UnitType == "USERDEFINED" \
            and (unit_entity.Name or "") == "1":
        return 'NONE'
    return str(unit_entity.id())


def _set_unit_enum(owner, attr, value):
    """Assign a unit picker enum value read from IFC, tolerating a unit entity
    the picker doesn't currently offer.

    The picker's items are the project units plus the units already referenced
    by some cost value or quantity, and that second scan is cached — an
    operator that has just created unit entities (or a file changed outside our
    own operators) can leave a perfectly valid unit out of the items, which
    Blender rejects with a TypeError. Rescan once, and only then fall back to
    'NONE': losing a unit label is not a reason to abort the whole load.
    """
    try:
        setattr(owner, attr, value)
        return True
    except TypeError:
        pass
    _invalidate_custom_units_cache()
    try:
        setattr(owner, attr, value)
        return True
    except TypeError:
        setattr(owner, attr, 'NONE')
        return False


def _active_item_unit_choice(ed):
    """Unit-picker enum choice governing this item's unit of measure — the
    same one already used for CostValue.UnitBasis in the active cost value
    mode. Quantities (libretto delle misure) piggyback on it so a cost item
    has a single unit of measure, not one for price and a different implicit
    one for quantities."""
    if ed.cost_value_mode == 'FIXED':
        return ed.cost_value_fixed_unit, ed.cost_value_fixed_unit_custom
    return ed.rate_analysis_unit, ed.rate_analysis_unit_custom


def _pct_label(label, pct):
    return f"{label} {pct:.1f}%"


def _parse_pct(name):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", name or "")
    return float(m.group(1)) if m else None


def _remove_analysis_values(tool, cost_item):
    file = tool.Ifc.get()
    for cv in list(cost_item.CostValues or []):
        for sub_cv in list(getattr(cv, "Components", None) or []):
            file.remove(sub_cv)
        tool.Ifc.run("cost.remove_cost_value", parent=cost_item, cost_value=cv)


def _get_cost_schedule(cost_item):
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcCostSchedule"):
            return rel.RelatingControl
    for rel in (cost_item.Nests or []):
        return _get_cost_schedule(rel.RelatingObject)
    return None


def _get_cost_item_controller(cost_item):
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                return ctrl
    return None


def _read_cost_item_info(context):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        target_id = ed.rate_analysis_target_ifc_id
        if target_id:
            cost_item = file.by_id(target_id)
        else:
            cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        ed.rate_analysis_item_identification = cost_item.Identification or ""
        ed.rate_analysis_item_name = cost_item.Name or ""
        ed.rate_analysis_item_description = cost_item.Description or ""
    except Exception:
        pass


def _write_cost_item_info(tool, cost_item, ed):
    tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
        "Identification": ed.rate_analysis_item_identification or None,
        "Name": ed.rate_analysis_item_name or None,
        "Description": ed.rate_analysis_item_description or None,
    })


def _compute_partial_qty(nr, l, b, h):
    """Product of non-zero fields; returns 0 if all fields are zero."""
    result = 1.0
    used = False
    for v in (nr, l, b, h):
        if v != 0.0:
            result *= v
            used = True
    return result if used else 0.0


def _build_formula_qty(nr, l, b, h):
    """Build 'NR × L × B × H', one factor per fixed position, so each factor's
    column is preserved on reload. Returns "" when all four fields are blank."""
    if nr == 0.0 and l == 0.0 and b == 0.0 and h == 0.0:
        return ""
    return " × ".join(f"{v:g}" for v in (nr, l, b, h))


def _parse_formula_qty(formula_str):
    """Parse 'NR × L × B × H' → (nr, l, b, h); missing/unparseable fields → 0.0."""
    if not formula_str:
        return 0.0, 0.0, 0.0, 0.0
    parts = [p.strip() for p in formula_str.split("×")]
    vals = []
    for p in parts[:4]:
        try:
            vals.append(float(p.replace(",", ".")))
        except ValueError:
            vals.append(0.0)
    while len(vals) < 4:
        vals.append(0.0)
    return vals[0], vals[1], vals[2], vals[3]


_QTY_CLIPBOARD_MARKER = "BONSAI5D_MEASURE_ROWS_V3"


def _serialize_measure_rows(rows):
    """Encode measurement rows (description + NR/L/B/H) as tab-separated text
    for the system clipboard, so rows can be pasted into another cost item,
    schedule, or IFC file."""
    lines = [_QTY_CLIPBOARD_MARKER]
    for r in rows:
        desc = (r.qty_desc or "").replace("\t", " ").replace("\n", " ")
        lines.append("\t".join((desc, repr(r.qty_nr), repr(r.qty_l), repr(r.qty_b), repr(r.qty_h))))
    return "\n".join(lines)


def _deserialize_measure_rows(text):
    """Parse clipboard text written by _serialize_measure_rows(); None if not ours."""
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != _QTY_CLIPBOARD_MARKER:
        return None
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        try:
            nr, l, b, h = (float(p) for p in parts[1:])
        except ValueError:
            continue
        rows.append((parts[0], nr, l, b, h))
    return rows


def _load_quantities(context, cost_item=None):
    """Populate cost_quantities collection from cost_item.CostQuantities."""
    ed = context.scene.bonsai5d_cost_editor
    ed.cost_quantities.clear()
    ed.cost_quantities_active_index = 0
    if cost_item is None:
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            target_id = ed.rate_analysis_target_ifc_id
            if target_id:
                cost_item = file.by_id(target_id)
            else:
                cost_item = file.by_id(
                    context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
                )
        except Exception:
            return

    quantities = cost_item.CostQuantities or []
    if quantities:
        # Quantities may come from a source with its own unit of measure
        # (import, takeoff, a previous file) — trust what's actually stored
        # over whatever the price panel currently shows. Legacy quantities
        # with no .Unit reset the picker to NONE rather than guess.
        _set_unit_enum(ed, "cost_quantities_unit", _unit_enum_value_for(getattr(quantities[0], "Unit", None)))
        ed.cost_quantities_unit_custom = ""
    else:
        # No quantities yet — prefill from the item's price unit as a
        # starting suggestion; the user can still change it freely.
        ed.cost_quantities_unit, ed.cost_quantities_unit_custom = _active_item_unit_choice(ed)

    for q in quantities:
        row = ed.cost_quantities.add()
        # "Unnamed" is the blank-name sentinel written on apply; show it empty.
        _qname = q.Name or ""
        row.qty_desc = "" if _qname == "Unnamed" else _qname
        row.ifc_id = q.id()
        ifc_type = q.is_a()
        type_id = _QTY_FROM_IFC.get(ifc_type, 'COUNT')
        val_attr = _QTY_VALUE_ATTR.get(type_id, "CountValue")
        stored_value = float(getattr(q, val_attr, 0.0) or 0.0)
        # Formula is the correct IFC4 attribute; fall back to Description for files
        # imported before this fix (XPWE importer used to write formula to Description)
        formula = getattr(q, "Formula", None) or q.Description or ""
        nr, l, b, h = _parse_formula_qty(formula)
        # Validate: recomputed partial must match stored value (within tolerance)
        recomputed = _compute_partial_qty(nr, l, b, h)
        if formula and abs(recomputed - stored_value) < max(abs(stored_value) * 0.001, 0.0001):
            row.qty_nr, row.qty_l, row.qty_b, row.qty_h = nr, l, b, h
        else:
            # Formula unreadable — put stored value in NR, leave others at 0
            row.qty_nr = stored_value


def _load_cost_item(context, item_id=None):
    from bonsai import tool

    file = tool.Ifc.get()
    if item_id is None:
        item_id = context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
    cost_item = file.by_id(item_id)
    ed = context.scene.bonsai5d_cost_editor

    ed.rate_analysis_components.clear()
    ed.rate_analysis_active_index = 0
    ed.rate_analysis_safety_pct = 0.0
    ed.rate_analysis_overhead_pct = 0.0
    ed.rate_analysis_profit_pct = 0.0
    ed.rate_analysis_rounding = 0.0
    ed.rate_analysis_unit = 'NONE'
    ed.rate_analysis_unit_custom = ""
    ed.cost_value_fixed_components.clear()
    ed.cost_value_fixed_active_index = 0
    ed.cost_value_fixed_unit = 'NONE'
    ed.cost_value_fixed_unit_custom = ""
    ed.cost_value_fixed_unit_mixed = False
    ed.rate_analysis_drafting = False
    ed.cost_value_fixed_drafting = False
    ed.rate_analysis_target_ifc_id = cost_item.id()
    _read_cost_item_info(context)

    found = False

    cost_values = list(cost_item.CostValues or [])

    if is_summary_cost_item(cost_item):
        ed.cost_value_mode = 'SUM'
        found = True

    elif cost_item.ObjectType == "RATE_ANALYSIS":
        ed.cost_value_mode = 'RATE_ANALYSIS'

        # Nested structure: one summary CV with sub-components
        if len(cost_values) == 1 and (getattr(cost_values[0], "Components", None) or []):
            summary_cv = cost_values[0]
            _, unit_entity = _read_unit_basis_entity(summary_cv)
            _set_unit_enum(ed, "rate_analysis_unit", _unit_enum_value_for(unit_entity))
            cost_values = list(summary_cv.Components or [])

        # Components written after the markup block already include safety costs,
        # overhead and profit — their position is what marks them (see
        # RA_OT_ApplyToIfc). In files written before this convention every
        # component precedes the block, so they all come back subject to markups.
        past_markups = False

        for cv in cost_values:
            cat = cv.Category or ""

            if cat in _LINE_CATEGORIES or cat not in _ALL_PA_CATEGORIES:
                found = True
                comp = ed.rate_analysis_components.add()
                comp.category = _FROM_IFC.get(cat, 'NONE')
                comp.description = cv.Name or ""
                comp.apply_markup = not past_markups

                v = cv.AppliedValue
                line_total = float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0

                qty, unit_entity = _read_unit_basis_entity(cv)
                if qty is not None:
                    comp.qty = qty
                    _set_unit_enum(comp, "unit", _unit_enum_value_for(unit_entity))
                    comp.unit_price = round(line_total / qty, 6) if qty else line_total
                else:
                    comp.unit_price = line_total

                src_id = _parse_cv_source_id(cv)
                if src_id is not None:
                    try:
                        comp.source_ifc_id = src_id
                        comp.source_identification = file.by_id(src_id).Identification or ""
                    except Exception:
                        pass
                else:
                    # Free-form component: Description carries its extended text.
                    comp.long_description = cv.Description or ""

                if comp.source_ifc_id:
                    current = _get_rate_current_value(file, comp.source_ifc_id)
                    if current is not None and round(current, 2) != round(comp.unit_price, 2):
                        comp.needs_rate_update = True

            elif cat == _SAFETY_PCT_CAT:
                found = True
                past_markups = True
                pct = _parse_pct(cv.Name)
                if pct is not None:
                    ed.rate_analysis_safety_pct = pct

            elif cat == _OVERHEAD_CAT:
                found = True
                past_markups = True
                pct = _parse_pct(cv.Name)
                if pct is not None:
                    ed.rate_analysis_overhead_pct = pct

            elif cat == _PROFIT_CAT:
                found = True
                past_markups = True
                pct = _parse_pct(cv.Name)
                if pct is not None:
                    ed.rate_analysis_profit_pct = pct

            elif cat == _ROUNDING_CAT:
                found = True
                past_markups = True
                v = cv.AppliedValue
                if v is not None:
                    ed.rate_analysis_rounding = float(
                        v.wrappedValue if hasattr(v, "wrappedValue") else v
                    )

    else:
        ed.cost_value_mode = 'FIXED'
        found = True
        seen_units = []  # order of first appearance; more than one entry = mixed units
        for cv in cost_values:
            comp = ed.cost_value_fixed_components.add()
            comp.category = _FROM_IFC.get(cv.Category or "", 'NONE')
            comp.description = cv.Name or ""

            v = cv.AppliedValue
            comp.unit_price = float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0

            _, unit_entity = _read_unit_basis_entity(cv)
            unit_value = _unit_enum_value_for(unit_entity)
            if unit_value != 'NONE' and unit_value not in seen_units:
                seen_units.append(unit_value)

            src_id = _parse_cv_source_id(cv)
            if src_id is not None:
                try:
                    comp.source_ifc_id = src_id
                    comp.source_identification = file.by_id(src_id).Identification or ""
                except Exception:
                    pass

        if seen_units:
            _set_unit_enum(ed, "cost_value_fixed_unit", seen_units[0])
            ed.cost_value_fixed_unit_mixed = len(seen_units) > 1

    _load_quantities(context, cost_item)
    return found


_handler_last_check = 0.0
# Last Bonsai-native active_cost_item id observed by the handler — tracked
# separately from ed.rate_analysis_target_ifc_id so that operators which
# deliberately pin a *different* item without touching Bonsai's own tree
# selection (e.g. "Load Controlling Item", which may point at an item in a
# schedule not even shown in the current tree) aren't immediately clobbered
# by auto-load on the next scene update. Auto-load should only kick in when
# the user actually changes Bonsai's native selection, not merely because it
# differs from our pinned target.
_handler_last_seen_active_id = 0


@bpy.app.handlers.persistent
def _auto_load_handler(scene, depsgraph):
    global _handler_last_check, _handler_last_seen_active_id
    t = _time.monotonic()
    if t - _handler_last_check < 0.1:
        return
    _handler_last_check = t
    try:
        ed = bpy.context.scene.bonsai5d_cost_editor
        if not ed.rate_analysis_auto_load:
            return
        props = bpy.context.scene.BIMCostProperties
        if props.active_cost_item is None or props.active_cost_schedule_id == 0:
            return
        item_id = props.active_cost_item.ifc_definition_id
        if item_id == _handler_last_seen_active_id:
            return
        _handler_last_seen_active_id = item_id
        if item_id == ed.rate_analysis_target_ifc_id:
            return
        _load_cost_item(bpy.context)
    except Exception:
        pass


@bpy.app.handlers.persistent
def _invalidate_auto_load_memo(scene=None):
    """Force auto-load to re-evaluate against the current selection after undo.

    Auto-load writes target_ifc_id/draft to the Scene from a depsgraph handler,
    without its own undo step, so undo can land on a snapshot where those
    predate the load and no longer match Bonsai's restored selection — the
    panel then shows a different cost item than the one selected. The dedup
    memo still holds the selection id, so auto-load would treat it as "no
    change" and never repair the mismatch. Clearing the memo makes the next
    depsgraph tick re-check: the existing `item_id == target` guard means it
    only reloads when there is a genuine mismatch, so a consistent undo (e.g. a
    restored quantity row) is left untouched.
    """
    global _handler_last_seen_active_id
    _handler_last_seen_active_id = 0


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class RA_OT_AddComponent(bpy.types.Operator):
    bl_idname = "rate_analysis.add_component"
    bl_label = "Add Free-form Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        ed.rate_analysis_components.add()
        ed.rate_analysis_active_index = len(ed.rate_analysis_components) - 1
        return {'FINISHED'}


class RA_OT_AddFromRate(bpy.types.Operator):
    bl_idname = "rate_analysis.add_from_rate"
    bl_label = "Add Component from Active Cost Item"
    bl_description = (
        "Add the currently selected cost item in the BIM Cost panel as a component. "
        "First use Load to pin the item being analysed, then browse to a rate and click this."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_item is None or props.active_cost_schedule_id == 0:
                return False
            target = context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id
            return target == 0 or props.active_cost_item.ifc_definition_id != target
        except Exception:
            return False

    def execute(self, context):
        from bonsai import tool
        ed = context.scene.bonsai5d_cost_editor
        props = context.scene.BIMCostProperties
        file = tool.Ifc.get()
        rate_item = file.by_id(props.active_cost_item.ifc_definition_id)

        comp = ed.rate_analysis_components.add()
        comp.description = rate_item.Name or ""
        comp.qty = 1.0
        comp.category = _detect_component_category(rate_item)
        comp.source_ifc_id = rate_item.id()
        comp.source_identification = rate_item.Identification or ""
        comp.unit_price = _get_rate_current_value(file, rate_item.id()) or 0.0

        ed.rate_analysis_active_index = len(ed.rate_analysis_components) - 1
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Generic base classes for cost-editor draft collection list operators
# ---------------------------------------------------------------------------

class _DraftListRemove(bpy.types.Operator):
    """Remove the active item from a draft CollectionProperty."""
    bl_options = {'REGISTER', 'UNDO'}
    _collection_attr: str
    _index_attr: str

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        items = getattr(ed, self._collection_attr)
        idx   = getattr(ed, self._index_attr)
        if 0 <= idx < len(items):
            items.remove(idx)
            setattr(ed, self._index_attr, max(0, idx - 1))
        return {'FINISHED'}


class _DraftListMoveUp(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    _collection_attr: str
    _index_attr: str

    def execute(self, context):
        ed  = context.scene.bonsai5d_cost_editor
        items = getattr(ed, self._collection_attr)
        idx   = getattr(ed, self._index_attr)
        if idx > 0:
            items.move(idx, idx - 1)
            setattr(ed, self._index_attr, idx - 1)
        return {'FINISHED'}


class _DraftListMoveDown(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    _collection_attr: str
    _index_attr: str

    def execute(self, context):
        ed    = context.scene.bonsai5d_cost_editor
        items = getattr(ed, self._collection_attr)
        idx   = getattr(ed, self._index_attr)
        if idx < len(items) - 1:
            items.move(idx, idx + 1)
            setattr(ed, self._index_attr, idx + 1)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Rate Analysis list operators
# ---------------------------------------------------------------------------

class RA_OT_RemoveComponent(_DraftListRemove):
    bl_idname = "rate_analysis.remove_component"
    bl_label = "Remove Component"
    _collection_attr = "rate_analysis_components"
    _index_attr      = "rate_analysis_active_index"


class RA_OT_MoveUp(_DraftListMoveUp):
    bl_idname = "rate_analysis.move_up"
    bl_label = "Move Up"
    _collection_attr = "rate_analysis_components"
    _index_attr      = "rate_analysis_active_index"


class RA_OT_MoveDown(_DraftListMoveDown):
    bl_idname = "rate_analysis.move_down"
    bl_label = "Move Down"
    _collection_attr = "rate_analysis_components"
    _index_attr      = "rate_analysis_active_index"


class RA_OT_ClearAll(bpy.types.Operator):
    bl_idname = "rate_analysis.clear_all"
    bl_label = "Clear Analysis"
    bl_description = "Clear all components and reset percentages"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        ed.rate_analysis_components.clear()
        ed.rate_analysis_active_index = 0
        ed.rate_analysis_overhead_pct = 0.0
        ed.rate_analysis_profit_pct = 0.0
        ed.rate_analysis_rounding = 0.0
        return {'FINISHED'}


class RA_OT_StartDraft(bpy.types.Operator):
    bl_idname = "rate_analysis.start_draft"
    bl_label = "Clear Cost Values and Add Rate Analysis"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        ed.rate_analysis_components.clear()
        ed.rate_analysis_active_index = 0
        ed.rate_analysis_overhead_pct = 15.0
        ed.rate_analysis_profit_pct = 10.0
        ed.rate_analysis_rounding = 0.0
        ed.rate_analysis_unit = 'NONE'
        ed.rate_analysis_unit_custom = ""
        ed.rate_analysis_drafting = True
        return {'FINISHED'}


class CV_OT_StartFixedDraft(bpy.types.Operator):
    bl_idname = "cost_value.start_fixed_draft"
    bl_label = "Clear Cost Values and Add New Fixed Cost Value"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        ed.cost_value_fixed_components.clear()
        ed.cost_value_fixed_active_index = 0
        ed.cost_value_fixed_unit = 'NONE'
        ed.cost_value_fixed_unit_custom = ""
        ed.cost_value_fixed_unit_mixed = False
        ed.cost_value_fixed_drafting = True
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Fixed value list operators
# ---------------------------------------------------------------------------

class CV_OT_AddFixedComponent(bpy.types.Operator):
    bl_idname = "cost_value.add_fixed_component"
    bl_label = "Add Cost Value"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        ed.cost_value_fixed_components.add()
        ed.cost_value_fixed_active_index = len(ed.cost_value_fixed_components) - 1
        return {'FINISHED'}


class CV_OT_RemoveFixedComponent(_DraftListRemove):
    bl_idname = "cost_value.remove_fixed_component"
    bl_label = "Remove Cost Value"
    _collection_attr = "cost_value_fixed_components"
    _index_attr      = "cost_value_fixed_active_index"


class CV_OT_MoveFixedComponentUp(_DraftListMoveUp):
    bl_idname = "cost_value.move_fixed_component_up"
    bl_label = "Move Cost Value Up"
    _collection_attr = "cost_value_fixed_components"
    _index_attr      = "cost_value_fixed_active_index"


class CV_OT_MoveFixedComponentDown(_DraftListMoveDown):
    bl_idname = "cost_value.move_fixed_component_down"
    bl_label = "Move Cost Value Down"
    _collection_attr = "cost_value_fixed_components"
    _index_attr      = "cost_value_fixed_active_index"


class RA_OT_RefreshComponentRate(bpy.types.Operator):
    bl_idname = "rate_analysis.refresh_component_rate"
    bl_label = "Update rate value"
    bl_description = "The linked rate value has changed — click to reload the current value"
    bl_options = {'REGISTER', 'UNDO'}

    component_index: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        from bonsai import tool
        ed = context.scene.bonsai5d_cost_editor
        comps = ed.rate_analysis_components
        if not (0 <= self.component_index < len(comps)):
            return {'CANCELLED'}
        comp = comps[self.component_index]
        if not comp.source_ifc_id:
            return {'CANCELLED'}
        file = tool.Ifc.get()
        current = _get_rate_current_value(file, comp.source_ifc_id)
        if current is not None:
            comp.unit_price = current
        try:
            comp.source_identification = file.by_id(comp.source_ifc_id).Identification or ""
        except Exception:
            pass
        comp.needs_rate_update = False
        return {'FINISHED'}


class RA_OT_EditDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.edit_description"
    bl_label = "Edit Description"
    bl_description = "Open Text Editor to edit the item description"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        _remove_description_text()
        text = bpy.data.texts.new(_DESCRIPTION_TEXT_NAME)
        text.write(ed.rate_analysis_item_description)
        text.cursor_set(0, character=0)
        _open_text_editor(context, text)
        ed.rate_analysis_editing_description = True
        return {'FINISHED'}


class RA_OT_ApplyDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.apply_description"
    bl_label = "Apply"
    bl_description = "Write the text back to the description and close the editor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        if _DESCRIPTION_TEXT_NAME in bpy.data.texts:
            ed.rate_analysis_item_description = bpy.data.texts[_DESCRIPTION_TEXT_NAME].as_string()
            self.report({'INFO'}, "Description applied")
        _remove_description_text()
        _close_text_editor(context)
        ed.rate_analysis_editing_description = False
        return {'FINISHED'}


class RA_OT_CancelDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.cancel_description"
    bl_label = "Cancel"
    bl_description = "Discard changes and close the editor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _remove_description_text()
        _close_text_editor(context)
        context.scene.bonsai5d_cost_editor.rate_analysis_editing_description = False
        return {'FINISHED'}


class RA_OT_SyncItemInfo(*_IfcOperatorBase):
    """Re-read Identification, Name and Description from the active (or pinned) cost item."""
    bl_idname = "rate_analysis.sync_item_info"
    bl_label = "Load identification from IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0:
            return True
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        if ed.rate_analysis_target_ifc_id == 0:
            from bonsai import tool
            file = tool.Ifc.get()
            cost_item = file.by_id(
                context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
            )
            ed.rate_analysis_target_ifc_id = cost_item.id()
        _read_cost_item_info(context)


class RA_OT_ApplyItemInfo(*_IfcOperatorBase):
    """Write Identification, Name and Description to the pinned target item."""
    bl_idname = "rate_analysis.apply_item_info"
    bl_label = "Write info to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        _write_cost_item_info(tool, cost_item, ed)
        refresh_cost_ui(tool)
        # If this item is a rate controlling CME items, offer to propagate.
        if get_rate_dependents(cost_item):
            schedule_propagate_popup(cost_item.id())


class RA_OT_ApplyToIfc(*_IfcOperatorBase):
    """Write the rate analysis to the active IFC cost item."""
    bl_idname = "rate_analysis.apply_to_ifc"
    bl_label = "Apply Rate Analysis to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ed = context.scene.bonsai5d_cost_editor
        if ed.rate_analysis_target_ifc_id == 0:
            return False
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            if not file:
                return False
            return get_rate_controller(file.by_id(ed.rate_analysis_target_ifc_id)) is None
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool


        ed = context.scene.bonsai5d_cost_editor
        file = tool.Ifc.get()
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        if get_rate_controller(cost_item) is not None:
            self.report({'WARNING'}, "Item is controlled by a rate — unlink first")
            return

        _write_cost_item_info(tool, cost_item, ed)
        tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={"ObjectType": "RATE_ANALYSIS"})
        _remove_analysis_values(tool, cost_item)
        _, safety, sg, profit, _, _, final = _get_totals(ed)

        def _add_cv(name, category, amount):
            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                "Name": name or None,
                "Category": category or None,
                "AppliedValue": round(amount, 2),
            })
            return cv

        def _add_component_cvs(components):
            cvs = []
            ordered = sorted(
                components,
                key=lambda c: _CATEGORY_WRITE_ORDER.index(c.category)
                if c.category in _CATEGORY_WRITE_ORDER else len(_CATEGORY_WRITE_ORDER),
            )
            for comp in ordered:
                line_total = round(comp.qty * comp.unit_price, 2)
                cv = _add_cv(comp.description, _TO_IFC.get(comp.category), line_total)
                unit_entity = resolve_unit_choice(file, comp.unit, comp.unit_custom)
                set_unit_basis_entity(file, cv, comp.qty, unit_entity)
                if comp.source_ifc_id:
                    cv.Description = _build_cv_ref(comp.source_ifc_id, comp.source_identification)
                elif comp.long_description:
                    # Free-form component: Description is free to hold its own text.
                    cv.Description = comp.long_description
                cvs.append(cv)
            return cvs

        # Components are written on either side of the markup block, which is what
        # tells them apart on read: those before it are subject to safety, overhead
        # and profit, those after it already include them. Overhead, profit and
        # rounding are always written, even at 0%, so the boundary always exists.
        sub_cvs = _add_component_cvs([c for c in ed.rate_analysis_components if c.apply_markup])
        if ed.rate_analysis_safety_pct:
            sub_cvs.append(_add_cv(
                _pct_label("Safety Costs", ed.rate_analysis_safety_pct), _SAFETY_PCT_CAT, safety))
        sub_cvs.append(_add_cv(
            _pct_label("Overhead", ed.rate_analysis_overhead_pct), _OVERHEAD_CAT, sg))
        sub_cvs.append(_add_cv(
            _pct_label("Profit", ed.rate_analysis_profit_pct), _PROFIT_CAT, profit))
        sub_cvs += _add_component_cvs([c for c in ed.rate_analysis_components if not c.apply_markup])
        sub_cvs.append(_add_cv("Rounding", _ROUNDING_CAT, ed.rate_analysis_rounding))

        cv_summary = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv_summary, attributes={
            "AppliedValue": round(final, 2),
            "ArithmeticOperator": "ADD",
        })
        unit_entity = resolve_unit_choice(file, ed.rate_analysis_unit, ed.rate_analysis_unit_custom)
        set_unit_basis_entity(file, cv_summary, 1.0, unit_entity)
        _invalidate_custom_units_cache()

        # Restructure: move sub_cvs from CostValues into summary.Components
        cv_summary.Components = sub_cvs
        cost_item.CostValues = [cv_summary]

        # The rewrite above replaced the cost-value entities; re-share them onto
        # any control-linked dependents and offer to propagate name/description.
        resync_rate_values(tool, cost_item)
        refresh_cost_ui(tool)
        if get_rate_dependents(cost_item):
            schedule_propagate_popup(cost_item.id())


class CV_OT_ApplySum(*_IfcOperatorBase):
    """Mark the active cost item as a Sum (Category='*') aggregator."""
    bl_idname = "cost_value.apply_sum"
    bl_label = "Apply Sum"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool

        ed = context.scene.bonsai5d_cost_editor
        file = tool.Ifc.get()
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)

        _write_cost_item_info(tool, cost_item, ed)
        tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={"ObjectType": None})
        _remove_analysis_values(tool, cost_item)

        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={"Category": "*"})

        # Sum is exempt from the controlled-item restriction, but if this item
        # itself controls others, re-share the new value onto them.
        resync_rate_values(tool, cost_item)
        refresh_cost_ui(tool)
        if get_rate_dependents(cost_item):
            schedule_propagate_popup(cost_item.id())


class CV_OT_ApplyFixed(*_IfcOperatorBase):
    """Write one or more flat CostValues (no breakdown) to the active cost item."""
    bl_idname = "cost_value.apply_fixed"
    bl_label = "Apply Fixed Price"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ed = context.scene.bonsai5d_cost_editor
        if ed.rate_analysis_target_ifc_id == 0:
            return False
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            if not file:
                return False
            return get_rate_controller(file.by_id(ed.rate_analysis_target_ifc_id)) is None
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool

        ed = context.scene.bonsai5d_cost_editor
        file = tool.Ifc.get()
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        if get_rate_controller(cost_item) is not None:
            self.report({'WARNING'}, "Item is controlled by a rate — unlink first")
            return

        _write_cost_item_info(tool, cost_item, ed)
        tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={"ObjectType": None})
        _remove_analysis_values(tool, cost_item)

        unit_entity = resolve_unit_choice(file, ed.cost_value_fixed_unit, ed.cost_value_fixed_unit_custom)

        for comp in ed.cost_value_fixed_components:
            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                "Name": comp.description or None,
                "Category": _TO_IFC.get(comp.category),
                "AppliedValue": round(comp.unit_price, 2),
            })
            if unit_entity is not None:
                set_unit_basis_entity(file, cv, 1.0, unit_entity)
            if comp.source_ifc_id:
                cv.Description = _build_cv_ref(comp.source_ifc_id, comp.source_identification)
        _invalidate_custom_units_cache()

        resync_rate_values(tool, cost_item)
        refresh_cost_ui(tool)
        if get_rate_dependents(cost_item):
            schedule_propagate_popup(cost_item.id())


def _find_parent_and_index(file, props):
    """Return (parent_cost_item_or_None, active_index_in_parent_or_None)."""
    try:
        active_id = props.active_cost_item.ifc_definition_id
        if not active_id:
            return None, None
        active = file.by_id(active_id)
        for rel in (active.Nests or []):
            obj = rel.RelatingObject
            if obj.is_a("IfcCostItem"):
                for r in (obj.IsNestedBy or []):
                    siblings = list(r.RelatedObjects)
                    if active in siblings:
                        return obj, siblings.index(active)
                return obj, None
    except Exception:
        pass
    return None, None


def _reorder_after_add(parent_item, new_item, insert_index):
    """Move new_item to insert_index within its parent's RelatedObjects list."""
    if parent_item is None or insert_index is None:
        return
    for r in (parent_item.IsNestedBy or []):
        siblings = list(r.RelatedObjects)
        if new_item in siblings:
            siblings.remove(new_item)
            siblings.insert(max(0, insert_index), new_item)
            r.RelatedObjects = siblings
            return


def _select_and_load(context, ifc_id):
    """Select new item in Bonsai's cost tree and load it in the editor."""
    try:
        props = context.scene.BIMCostProperties
        for i, item in enumerate(props.cost_items):
            if getattr(item, 'ifc_definition_id', None) == ifc_id:
                props.active_cost_item_index = i
                break
    except Exception:
        pass
    _load_cost_item(context, ifc_id)


class RA_OT_AddCostItem(*_IfcOperatorBase):
    """Add a cost item (plain or summary) relative to the active one."""
    bl_idname = "rate_analysis.add_cost_item"
    bl_label = "Add Cost Item"
    bl_options = {'REGISTER', 'UNDO'}

    position: bpy.props.EnumProperty(
        items=[
            ('BEFORE', "Before",         "Insert a new cost item before the active one (same level)"),
            ('AFTER',  "After",          "Insert a new cost item after the active one (same level)"),
            ('CHILD',  "As child",       "Insert a new cost item as a child of the active one"),
        ],
        default='AFTER',
        options={'SKIP_SAVE'},
    )
    summary: bpy.props.BoolProperty(
        name="Summary",
        description="Add a summary cost item (Category='*', sums child values) instead of a plain one",
        default=False,
        options={'SKIP_SAVE'},
    )

    @classmethod
    def description(cls, context, properties):
        kind = "summary cost item (Category='*', sums child values)" if properties.summary else "cost item"
        return {
            'BEFORE': f"Insert a new {kind} before the active one (same level)",
            'AFTER':  f"Insert a new {kind} after the active one (same level)",
            'CHILD':  f"Insert a new {kind} as a child of the active one",
        }.get(properties.position, f"Add {kind}")

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool


        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        schedule = file.by_id(int(props.active_cost_schedule_id))

        if self.position == 'CHILD':
            try:
                active_id = props.active_cost_item.ifc_definition_id
                active = file.by_id(active_id) if active_id else None
            except Exception:
                active = None
            if active:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_item=active)
            else:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
        else:
            parent_item, active_index = _find_parent_and_index(file, props)
            if parent_item:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_item=parent_item)
                insert_index = active_index if self.position == 'BEFORE' else active_index + 1
                _reorder_after_add(parent_item, new_item, insert_index)
            else:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)

        if self.summary:
            cv = tool.Ifc.run("cost.add_cost_value", parent=new_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={"Category": "*"})

        refresh_cost_ui(tool)
        _select_and_load(context, new_item.id())


class RA_OT_MoveCostItem(*_IfcOperatorBase):
    """Move the active cost item up or down among its siblings."""
    bl_idname = "rate_analysis.move_cost_item"
    bl_label = "Move Cost Item"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[
            ('UP',   "Up",   "Move the active cost item up among its siblings"),
            ('DOWN', "Down", "Move the active cost item down among its siblings"),
        ],
        default='UP',
        options={'SKIP_SAVE'},
    )

    @classmethod
    def description(cls, context, properties):
        where = "up" if properties.direction == 'UP' else "down"
        return (
            f"Move the active cost item {where} among its siblings. "
            "Summary items move with their children"
        )

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if not props.active_cost_schedule_id:
                return False
            return bool(props.active_cost_item.ifc_definition_id)
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        cost_item = file.by_id(props.active_cost_item.ifc_definition_id)

        if not move_cost_item(cost_item, -1 if self.direction == 'UP' else 1):
            edge = "first" if self.direction == 'UP' else "last"
            self.report({'INFO'}, f"Cost item is already {edge} among its siblings")
            return

        refresh_cost_ui(tool)
        # Keep it selected so successive clicks keep moving the same item.
        _select_and_load(context, cost_item.id())


class RA_OT_LoadFromIfc(*_IfcOperatorBase):
    """Load rate analysis from the active IFC cost item."""
    bl_idname = "rate_analysis.load_from_ifc"
    bl_label = "Load Rate Analysis from IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        if not _load_cost_item(context):
            self.report({'WARNING'}, "No price analysis data found on this cost item.")


class RA_OT_LoadController(*_IfcOperatorBase):
    """Load the cost item that controls the current one."""
    bl_idname = "rate_analysis.load_controller"
    bl_label = "Load Controlling Item"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ed = context.scene.bonsai5d_cost_editor
        if ed.rate_analysis_target_ifc_id == 0:
            return False
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            if not file:
                return False
            cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
            return _get_cost_item_controller(cost_item) is not None
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        controller = _get_cost_item_controller(cost_item)
        if controller:
            _load_cost_item(context, item_id=controller.id())


class RA_OT_UnlinkFromRate(*_IfcOperatorBase):
    """Detach the active cost item from its rate controller, keeping its
    current values as an independent copy."""
    bl_idname = "rate_analysis.unlink_from_rate"
    bl_label = "Unlink from Rate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            item_id = context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id
            if not file or not item_id:
                return False
            return get_rate_controller(file.by_id(item_id)) is not None
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        if unlink_from_rate(tool, cost_item, copy_info=False):
            refresh_cost_ui(tool)
            _load_cost_item(context, cost_item.id())
        else:
            self.report({"ERROR"}, "Item has no rate controller")


class RA_OT_MakeUnique(*_IfcOperatorBase):
    """Detach the active cost item from its rate controller, first copying
    the controller's Name/Description onto it."""
    bl_idname = "rate_analysis.make_unique"
    bl_label = "Make Unique"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return RA_OT_UnlinkFromRate.poll(context)

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        if unlink_from_rate(tool, cost_item, copy_info=True):
            refresh_cost_ui(tool)
            _load_cost_item(context, cost_item.id())
        else:
            self.report({"ERROR"}, "Item has no rate controller")


class RA_OT_DuplicateRate(*_IfcOperatorBase):
    """Duplicate the active cost item's rate controller and relink the item
    to the copy, so it can diverge from the shared rate without affecting it."""
    bl_idname = "rate_analysis.duplicate_rate"
    bl_label = "Duplicate Rate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return RA_OT_UnlinkFromRate.poll(context)

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        if duplicate_and_relink_rate(tool, cost_item) is not None:
            refresh_cost_ui(tool)
            _load_cost_item(context, cost_item.id())
        else:
            self.report({"ERROR"}, "Item has no rate controller")


class RA_OT_AddZeroQuantity(*_IfcOperatorBase):
    """Add a zero-value quantity row to mark the item as 'not yet measured'."""
    bl_idname = "rate_analysis.add_zero_quantity"
    bl_label = "Add Zero Quantity"
    bl_description = (
        "Add a quantity = 0 using the quantities' unit of measure. "
        "Prevents the item from contributing to the parent SUM total until measured."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
        unit_entity = resolve_unit_choice(file, ed.cost_quantities_unit, ed.cost_quantities_unit_custom)

        ifc_class, value_attr = ifc_quantity_type_from_unit(unit_entity)
        kw = {"Name": "Da misurare", value_attr: 0.0}
        if unit_entity is not None:
            kw["Unit"] = unit_entity
        qty_entity = file.create_entity(ifc_class, **kw)
        cost_item.CostQuantities = list(cost_item.CostQuantities or []) + [qty_entity]

        _load_quantities(context, cost_item)
        refresh_cost_ui(tool)


class QTY_OT_AddRow(bpy.types.Operator):
    bl_idname = "cost_quantities.add_row"
    bl_label = "Add Measurement Row"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        row = ed.cost_quantities.add()
        row.qty_nr = 1.0
        ed.cost_quantities_active_index = len(ed.cost_quantities) - 1
        return {'FINISHED'}


class QTY_OT_RemoveRow(bpy.types.Operator):
    """Remove the checked measurement rows, or just the active row if none
    are checked — mirrors Copy Rows' selection-checkbox behaviour."""
    bl_idname = "cost_quantities.remove_row"
    bl_label = "Remove Measurement Row"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.bonsai5d_cost_editor.cost_quantities) > 0

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        items = ed.cost_quantities
        indices = [i for i, r in enumerate(items) if r.is_selected]
        if not indices:
            idx = ed.cost_quantities_active_index
            if 0 <= idx < len(items):
                indices = [idx]
        for i in sorted(indices, reverse=True):
            items.remove(i)
        ed.cost_quantities_active_index = max(0, min(ed.cost_quantities_active_index, len(items) - 1))
        return {'FINISHED'}


class QTY_OT_MoveRowUp(_DraftListMoveUp):
    bl_idname = "cost_quantities.move_row_up"
    bl_label = "Move Row Up"
    _collection_attr = "cost_quantities"
    _index_attr      = "cost_quantities_active_index"


class QTY_OT_MoveRowDown(_DraftListMoveDown):
    bl_idname = "cost_quantities.move_row_down"
    bl_label = "Move Row Down"
    _collection_attr = "cost_quantities"
    _index_attr      = "cost_quantities_active_index"


class QTY_OT_SelectAll(bpy.types.Operator):
    bl_idname = "cost_quantities.select_all"
    bl_label = "Select All Rows"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.bonsai5d_cost_editor.cost_quantities) > 0

    def execute(self, context):
        for row in context.scene.bonsai5d_cost_editor.cost_quantities:
            row.is_selected = True
        return {'FINISHED'}


class QTY_OT_SelectNone(bpy.types.Operator):
    bl_idname = "cost_quantities.select_none"
    bl_label = "Deselect All Rows"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.bonsai5d_cost_editor.cost_quantities) > 0

    def execute(self, context):
        for row in context.scene.bonsai5d_cost_editor.cost_quantities:
            row.is_selected = False
        return {'FINISHED'}


class QTY_OT_CopyRows(bpy.types.Operator):
    """Copy selected measurement rows to the system clipboard (survives across
    cost items, schedules, and IFC files — paste with Paste Rows)."""
    bl_idname = "cost_quantities.copy_rows"
    bl_label = "Copy Rows"

    @classmethod
    def poll(cls, context):
        return len(context.scene.bonsai5d_cost_editor.cost_quantities) > 0

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        rows = [r for r in ed.cost_quantities if r.is_selected]
        if not rows:
            idx = ed.cost_quantities_active_index
            if 0 <= idx < len(ed.cost_quantities):
                rows = [ed.cost_quantities[idx]]
        if not rows:
            self.report({'WARNING'}, "No rows to copy")
            return {'CANCELLED'}
        context.window_manager.clipboard = _serialize_measure_rows(rows)
        self.report({'INFO'}, f"Copied {len(rows)} row(s)")
        return {'FINISHED'}


class QTY_OT_PasteRows(bpy.types.Operator):
    """Paste measurement rows previously copied with Copy Rows, inserting
    them after the active row."""
    bl_idname = "cost_quantities.paste_rows"
    bl_label = "Paste Rows"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ed = context.scene.bonsai5d_cost_editor
        parsed = _deserialize_measure_rows(context.window_manager.clipboard)
        if not parsed:
            self.report({'ERROR'}, "Clipboard does not contain copied quantity rows")
            return {'CANCELLED'}

        items = ed.cost_quantities
        insert_at = ed.cost_quantities_active_index + 1 if len(items) else 0
        insert_at = max(0, min(insert_at, len(items)))

        for offset, (desc, nr, l, b, h) in enumerate(parsed):
            row = items.add()
            row.qty_desc, row.qty_nr, row.qty_l, row.qty_b, row.qty_h = desc, nr, l, b, h
            row.is_selected = False
            new_idx = len(items) - 1
            target = insert_at + offset
            if target < new_idx:
                items.move(new_idx, target)

        ed.cost_quantities_active_index = insert_at + len(parsed) - 1
        self.report({'INFO'}, f"Pasted {len(parsed)} row(s)")
        return {'FINISHED'}


class QTY_OT_Load(*_IfcOperatorBase):
    """Load quantities from the pinned IFC cost item."""
    bl_idname = "cost_quantities.load"
    bl_label = "Load Quantities from IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ed = context.scene.bonsai5d_cost_editor
        if ed.rate_analysis_target_ifc_id != 0:
            return True
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        _load_quantities(context)


class QTY_OT_Apply(*_IfcOperatorBase):
    """Write measurement rows to the pinned IFC cost item as CostQuantities."""
    bl_idname = "cost_quantities.apply"
    bl_label = "Apply Quantities to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.bonsai5d_cost_editor.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        ed = context.scene.bonsai5d_cost_editor
        cost_item = file.by_id(ed.rate_analysis_target_ifc_id)

        for q in list(cost_item.CostQuantities or []):
            file.remove(q)

        unit_entity = resolve_unit_choice(file, ed.cost_quantities_unit, ed.cost_quantities_unit_custom)
        ifc_class, val_attr = ifc_quantity_type_from_unit(unit_entity)
        new_quantities = []
        for row in ed.cost_quantities:
            partial = _compute_partial_qty(row.qty_nr, row.qty_l, row.qty_b, row.qty_h)
            kw = {
                # IfcPhysicalQuantity.Name is a mandatory attribute; a None name
                # produces a malformed quantity that crashes downstream readers
                # (e.g. ifc5d serialise_cost_quantities). Use the "Unnamed"
                # sentinel that ifc5d/the BoQ template already treat as blank.
                "Name": row.qty_desc or "Unnamed",
                val_attr: round(partial, 6),
            }
            if unit_entity is not None:
                kw["Unit"] = unit_entity
            formula = _build_formula_qty(row.qty_nr, row.qty_l, row.qty_b, row.qty_h)
            if formula:
                kw["Formula"] = formula
            new_quantities.append(file.create_entity(ifc_class, **kw))

        cost_item.CostQuantities = new_quantities
        refresh_cost_ui(tool)


classes = [
    RA_OT_AddComponent,
    RA_OT_AddFromRate,
    RA_OT_RemoveComponent,
    RA_OT_MoveUp,
    RA_OT_MoveDown,
    RA_OT_ClearAll,
    RA_OT_StartDraft,
    CV_OT_StartFixedDraft,
    CV_OT_AddFixedComponent,
    CV_OT_RemoveFixedComponent,
    CV_OT_MoveFixedComponentUp,
    CV_OT_MoveFixedComponentDown,
    RA_OT_RefreshComponentRate,
    RA_OT_EditDescription,
    RA_OT_ApplyDescription,
    RA_OT_CancelDescription,
    RA_OT_SyncItemInfo,
    RA_OT_ApplyItemInfo,
    RA_OT_ApplyToIfc,
    CV_OT_ApplySum,
    CV_OT_ApplyFixed,
    RA_OT_AddCostItem,
    RA_OT_MoveCostItem,
    RA_OT_LoadFromIfc,
    RA_OT_LoadController,
    RA_OT_UnlinkFromRate,
    RA_OT_MakeUnique,
    RA_OT_DuplicateRate,
    RA_OT_AddZeroQuantity,
    QTY_OT_AddRow,
    QTY_OT_RemoveRow,
    QTY_OT_MoveRowUp,
    QTY_OT_MoveRowDown,
    QTY_OT_SelectAll,
    QTY_OT_SelectNone,
    QTY_OT_CopyRows,
    QTY_OT_PasteRows,
    QTY_OT_Load,
    QTY_OT_Apply,
]
