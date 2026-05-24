import os
import bpy
import ifcopenshell
import ifcopenshell.api.classification
import ifcopenshell.util.classification
import ifcopenshell.util.cost

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


# ---------------------------------------------------------------------------
# Load classification systems from src/data/classifications/*.ifc
# ---------------------------------------------------------------------------

_CLASSIFICATIONS_DIR = os.path.join(os.path.dirname(__file__), "data", "classifications")


def _load_systems():
    """Return {key: (ifc_name, label, [(code, name), ...])} from IFC files."""
    systems = {}
    if not os.path.isdir(_CLASSIFICATIONS_DIR):
        return systems
    for fname in sorted(os.listdir(_CLASSIFICATIONS_DIR)):
        if not fname.lower().endswith(".ifc"):
            continue
        key = os.path.splitext(fname)[0]
        path = os.path.join(_CLASSIFICATIONS_DIR, fname)
        try:
            f = ifcopenshell.open(path)
            clss = f.by_type("IfcClassification")
            if not clss:
                continue
            ifc_name = clss[0].Name or key
            cats = []
            for ref in f.by_type("IfcClassificationReference"):
                ident = getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
                name = ref.Name or ident
                if ident:
                    cats.append((ident, name))
            systems[key] = (ifc_name, key, cats)
        except Exception as e:
            print(f"[CostClassification] Cannot load {fname}: {e}")
    return systems


# Built once at import time — reloading the addon refreshes this
_SYSTEMS = _load_systems()

_BY_CODE = {
    key: {code: name for code, name in cats}
    for key, (_, _, cats) in _SYSTEMS.items()
}

_ENUM_ITEMS = {
    key: [("", "—", "")] + [(code, f"{code}  –  {name}", name) for code, name in cats]
    for key, (_, _, cats) in _SYSTEMS.items()
}


def _prop_name(key):
    return f"cc_{key}_category"


# ---------------------------------------------------------------------------
# Generic IFC helpers
# ---------------------------------------------------------------------------

def _get_or_create_classification(file, ifc_name):
    for cls in file.by_type("IfcClassification"):
        if cls.Name == ifc_name:
            return cls
    return ifcopenshell.api.classification.add_classification(file, classification=ifc_name)


def _get_code(cost_item, ifc_name):
    for ref in ifcopenshell.util.classification.get_references(cost_item):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            return getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None) or ""
    return ""


def _set_code(file, cost_item, ifc_name, code, code_names):
    for ref in list(ifcopenshell.util.classification.get_references(cost_item)):
        cls = ifcopenshell.util.classification.get_classification(ref)
        if cls and cls.Name == ifc_name:
            ifcopenshell.api.classification.remove_reference(file, reference=ref, products=[cost_item])

    if not code:
        return

    classification = _get_or_create_classification(file, ifc_name)
    ifcopenshell.api.classification.add_reference(
        file,
        products=[cost_item],
        classification=classification,
        identification=code,
        name=code_names.get(code, code),
    )


# ---------------------------------------------------------------------------
# Total + summary traversal
# ---------------------------------------------------------------------------

def _get_item_total(cost_item):
    rate = 0.0
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                rate += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    qty = 0.0
    for cq in (cost_item.CostQuantities or []):
        for attr in ("LengthValue", "AreaValue", "VolumeValue", "WeightValue", "CountValue", "TimeValue"):
            v = getattr(cq, attr, None)
            if v is not None:
                try:
                    qty += float(v)
                except Exception:
                    pass
                break
    return rate * qty if qty else rate


def _collect_totals(cost_item, inherited_code, ifc_name, accumulator):
    """Traverse propagating classification code downward; only leaf values counted."""
    code = _get_code(cost_item, ifc_name) or inherited_code
    children = [c for rel in (cost_item.IsNestedBy or []) for c in rel.RelatedObjects]
    if not children:
        key = code or "__none__"
        accumulator[key] = accumulator.get(key, 0.0) + _get_item_total(cost_item)
    else:
        for child in children:
            _collect_totals(child, code, ifc_name, accumulator)


def _build_summary(file, schedule_id, ifc_name):
    schedule = file.by_id(int(schedule_id))
    acc = {}
    for root in ifcopenshell.util.cost.get_root_cost_items(schedule):
        _collect_totals(root, "", ifc_name, acc)
    return acc


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

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
        ifc_name, _, cats = _SYSTEMS[self.system]
        code = getattr(context.scene, _prop_name(self.system), "")
        _set_code(file, cost_item, ifc_name, code, {c: n for c, n in cats})


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
        ifc_name, _, cats = _SYSTEMS[self.system]
        _set_code(file, cost_item, ifc_name, "", {c: n for c, n in cats})


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class CostClassificationPanel(bpy.types.Panel):
    bl_label = "Cost Item Classification"
    bl_idname = "SCENE_PT_cost_classification"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        if not _SYSTEMS:
            layout.label(text="Nessun sistema di classificazione trovato.", icon="INFO")
            layout.label(text=f"Cartella: {_CLASSIFICATIONS_DIR}")
            return

        try:
            from bonsai import tool
            file = tool.Ifc.get()
        except Exception:
            layout.label(text="Bonsai non disponibile.", icon="ERROR")
            return

        if not file:
            layout.label(text="Nessun file IFC caricato.", icon="INFO")
            return

        props = context.scene.BIMCostProperties
        if props.active_cost_schedule_id == 0:
            layout.label(text="Nessun cost schedule attivo.", icon="INFO")
            return

        cost_item = None
        if props.active_cost_item:
            cost_item = file.by_id(props.active_cost_item.ifc_definition_id)

        # --- One box per classification system ---
        for system_key, (ifc_name, label, _) in _SYSTEMS.items():
            by_code = _BY_CODE[system_key]

            box = layout.box()
            row = box.row()
            row.label(text=label, icon="ASSET_MANAGER")

            if cost_item:
                current = _get_code(cost_item, ifc_name)
                if current:
                    row.label(text=current)
                    op = row.operator("cost_classification.clear_code", text="", icon="X")
                    op.system = system_key
                else:
                    row.label(text="—")

                if current and current in by_code:
                    box.label(text=by_code[current])

                row2 = box.row(align=True)
                row2.prop(context.scene, _prop_name(system_key), text="")
                op = row2.operator("cost_classification.set_code", text="", icon="CHECKMARK")
                op.system = system_key
            else:
                box.label(text="Nessuna voce attiva.", icon="INFO")

        # --- Summary ---
        layout.separator()
        layout.label(text="Riepilogo schedule:", icon="LINENUMBERS_ON")
        layout.prop(context.scene, "cc_summary_system", text="Sistema")

        summary_key = context.scene.cc_summary_system
        if summary_key not in _SYSTEMS:
            return
        ifc_name, _, _ = _SYSTEMS[summary_key]
        by_code = _BY_CODE[summary_key]

        totals = _build_summary(file, props.active_cost_schedule_id, ifc_name)
        if not totals:
            layout.label(text="Nessuna voce trovata.", icon="INFO")
            return

        grand_total = sum(totals.values())
        box = layout.box()

        classified = sorted(k for k in totals if k != "__none__")
        if "__none__" in totals:
            classified.append("__none__")

        for key in classified:
            amount = totals[key]
            pct = (amount / grand_total * 100) if grand_total else 0.0
            split = box.split(factor=0.30)
            if key == "__none__":
                split.label(text="(non classif.)", icon="QUESTION")
            else:
                split.label(text=key)
            split2 = split.split(factor=0.62)
            split2.label(text=f"{amount:,.2f}")
            split2.label(text=f"{pct:.1f}%")

        box.separator()
        split = box.split(factor=0.30)
        split.label(text="TOTALE")
        split2 = split.split(factor=0.62)
        split2.label(text=f"{grand_total:,.2f}")
        split2.label(text="100%")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    CC_OT_SetCode,
    CC_OT_ClearCode,
    CostClassificationPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()

    for key, (ifc_name, label, _) in _SYSTEMS.items():
        setattr(
            bpy.types.Scene,
            _prop_name(key),
            bpy.props.EnumProperty(
                name=f"Categoria {label}",
                description=ifc_name,
                items=_ENUM_ITEMS[key],
                default="",
            ),
        )

    if _SYSTEMS:
        bpy.types.Scene.cc_summary_system = bpy.props.EnumProperty(
            name="Sistema di classificazione",
            items=[(key, f"{key} – {ifc_name}", ifc_name) for key, (ifc_name, _, _) in _SYSTEMS.items()],
            default=next(iter(_SYSTEMS)),
        )


def unregister():
    class_unregister()
    for key in _SYSTEMS:
        prop = _prop_name(key)
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    if hasattr(bpy.types.Scene, "cc_summary_system"):
        del bpy.types.Scene.cc_summary_system
