# Requires pytest: pip install pytest
"""Regression test for Cost Item Editor's FIXED-mode load logic
(_load_cost_item in module/cost_item_editor/operator.py).

Covers the bug found in review: when a cost item's flat top-level
CostValues carry *different* units of measure (possible on files not
produced by this addon's own Fixed editor, which always writes one
shared unit), the loader used to silently pick the first unit found and
discard the rest with no indication to the user. Fixed by tracking all
distinct units seen and setting wm.cost_value_fixed_unit_mixed when
there's more than one."""

import types

from bonsai_5d_plus.module.cost_item_editor import operator as op


class _Measure:
    def __init__(self, value):
        self.wrappedValue = value


class _MockUnit:
    """Minimal stand-in for an IfcNamedUnit entity (IfcSIUnit etc)."""

    def __init__(self, unit_id, unit_type="AREAUNIT", name="SQUARE_METRE", ifc_class="IfcSIUnit"):
        self._id = unit_id
        self.UnitType = unit_type
        self.Name = name
        self._ifc_class = ifc_class

    def id(self):
        return self._id

    def is_a(self, cls=None):
        return self._ifc_class if cls is None else cls == self._ifc_class


class _UnitBasis:
    def __init__(self, unit_entity):
        self.ValueComponent = _Measure(1.0)
        self.UnitComponent = unit_entity


class _MockCostValue:
    def __init__(self, category, value, unit=None):
        self.Category = category
        self.AppliedValue = _Measure(value)
        self.Name = None
        self.Description = None
        self.Components = None
        self.UnitBasis = _UnitBasis(unit) if unit else None


class _MockCostItem:
    def __init__(self, item_id, cost_values):
        self._id = item_id
        self.CostValues = cost_values
        self.ObjectType = None
        self.Identification = "X"
        self.Name = "leaf"
        self.Description = None
        self.CostQuantities = []
        self.IsNestedBy = []
        self.Nests = []

    def id(self):
        return self._id

    def is_a(self, cls=None):
        return "IfcCostItem" if cls is None else cls == "IfcCostItem"


class _MockFile:
    def __init__(self, item):
        self._item = item

    def by_id(self, item_id):
        assert item_id == self._item.id()
        return self._item

    def by_type(self, t):
        return []


class _Collection(list):
    def add(self):
        row = types.SimpleNamespace(
            category="LABOR", description="", unit='NONE', unit_custom="", qty=1.0, unit_price=0.0,
            source_ifc_id=0, source_identification="", needs_rate_update=False,
        )
        self.append(row)
        return row

    def clear(self):
        del self[:]


def _make_wm():
    return types.SimpleNamespace(
        rate_analysis_components=_Collection(),
        rate_analysis_active_index=0,
        rate_analysis_overhead_pct=0.0,
        rate_analysis_profit_pct=0.0,
        rate_analysis_rounding=0.0,
        rate_analysis_unit='NONE',
        rate_analysis_unit_custom="",
        cost_value_fixed_components=_Collection(),
        cost_value_fixed_active_index=0,
        cost_value_fixed_unit='NONE',
        cost_value_fixed_unit_custom="",
        cost_value_fixed_unit_mixed=False,
        rate_analysis_drafting=False,
        cost_value_fixed_drafting=False,
        rate_analysis_target_ifc_id=0,
        rate_analysis_item_identification="",
        rate_analysis_item_name="",
        rate_analysis_item_description="",
        cost_value_mode="",
        cost_quantities=_Collection(),
        cost_quantities_active_index=0,
        cost_quantities_type="COUNT",
    )


def _load(item, monkeypatch):
    """Call the real _load_cost_item() against a mock IFC file/item."""
    file = _MockFile(item)
    bonsai_mod = types.ModuleType("bonsai")
    bonsai_tool_mod = types.ModuleType("bonsai.tool")

    class _Ifc:
        @staticmethod
        def get():
            return file

    bonsai_tool_mod.Ifc = _Ifc
    bonsai_mod.tool = bonsai_tool_mod
    monkeypatch.setitem(__import__("sys").modules, "bonsai", bonsai_mod)
    monkeypatch.setitem(__import__("sys").modules, "bonsai.tool", bonsai_tool_mod)
    monkeypatch.setattr(op, "_read_cost_item_info", lambda ctx: None)
    monkeypatch.setattr(op, "_load_quantities", lambda ctx, item: None)

    wm = _make_wm()
    context = types.SimpleNamespace(window_manager=wm)
    found = op._load_cost_item(context, item_id=item.id())
    return found, wm


UNIT_MQ = _MockUnit(501, unit_type="AREAUNIT", name="SQUARE_METRE")
UNIT_H = _MockUnit(502, unit_type="TIMEUNIT", name="HOUR", ifc_class="IfcConversionBasedUnit")


def test_fixed_mode_loads_all_rows_with_consistent_unit(monkeypatch):
    item = _MockCostItem(1, [
        _MockCostValue(None, 50.0, unit=UNIT_MQ),
        _MockCostValue("Labor", 20.0, unit=UNIT_MQ),
    ])
    found, wm = _load(item, monkeypatch)

    assert found is True
    assert wm.cost_value_mode == 'FIXED'
    assert len(wm.cost_value_fixed_components) == 2
    assert wm.cost_value_fixed_components[0].category == 'NONE'
    assert wm.cost_value_fixed_components[0].unit_price == 50.0
    assert wm.cost_value_fixed_components[1].category == 'LABOR'
    assert wm.cost_value_fixed_components[1].unit_price == 20.0
    assert wm.cost_value_fixed_unit == str(UNIT_MQ.id())
    assert wm.cost_value_fixed_unit_mixed is False


def test_fixed_mode_flags_mixed_units_instead_of_silently_dropping_one(monkeypatch):
    item = _MockCostItem(2, [
        _MockCostValue(None, 50.0, unit=UNIT_MQ),
        _MockCostValue("Labor", 20.0, unit=UNIT_H),  # different unit — used to be silently lost
    ])
    found, wm = _load(item, monkeypatch)

    assert found is True
    # Both rows are still loaded (the bug was about the unit, not the rows/values).
    assert len(wm.cost_value_fixed_components) == 2
    assert wm.cost_value_fixed_components[0].unit_price == 50.0
    assert wm.cost_value_fixed_components[1].unit_price == 20.0
    # The first unit encountered still wins as the shared display unit...
    assert wm.cost_value_fixed_unit == str(UNIT_MQ.id())
    # ...but the mismatch is now flagged instead of silently swallowed.
    assert wm.cost_value_fixed_unit_mixed is True


def test_fixed_mode_single_unit_is_not_flagged_as_mixed(monkeypatch):
    item = _MockCostItem(3, [_MockCostValue(None, 50.0, unit=UNIT_MQ)])
    _, wm = _load(item, monkeypatch)

    assert wm.cost_value_fixed_unit_mixed is False
    assert wm.cost_value_fixed_unit == str(UNIT_MQ.id())


# ---------------------------------------------------------------------------
# _active_item_unit_choice — quantities (libretto delle misure) must share
# the same unit of measure as whichever cost value mode is active, instead
# of an independently-picked quantity type that could disagree with it.
# ---------------------------------------------------------------------------


def test_active_item_unit_choice_uses_fixed_unit_in_fixed_mode():
    wm = types.SimpleNamespace(
        cost_value_mode='FIXED',
        cost_value_fixed_unit='501',
        cost_value_fixed_unit_custom="",
        rate_analysis_unit='NONE',
        rate_analysis_unit_custom="",
    )
    assert op._active_item_unit_choice(wm) == ('501', "")


def test_active_item_unit_choice_uses_rate_analysis_unit_otherwise():
    wm = types.SimpleNamespace(
        cost_value_mode='RATE_ANALYSIS',
        cost_value_fixed_unit='NONE',
        cost_value_fixed_unit_custom="",
        rate_analysis_unit='USERDEFINED',
        rate_analysis_unit_custom="cad",
    )
    assert op._active_item_unit_choice(wm) == ('USERDEFINED', "cad")
