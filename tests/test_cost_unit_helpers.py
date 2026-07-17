# Requires pytest: pip install pytest
"""Unit tests for the IFC-native unit picker helpers in tool/cost.py
(project_unit_entities, resolve_unit_choice, set_unit_basis_entity,
ifc_quantity_type_from_unit), used by the Cost Item Editor's Fixed and Rate
Analysis unit dropdowns.

These helpers only touch the `file` object via by_type/by_id/create_entity,
so they're tested here against lightweight duck-typed fakes rather than a
real ifcopenshell.file (not importable outside Blender's bundled Python)."""

import types

from bonsai_5d_plus.tool import cost as cost_tool


class _FakeUnit:
    """Minimal stand-in for an IfcSIUnit / IfcConversionBasedUnit / etc."""

    def __init__(self, unit_id, unit_type, name, ifc_class="IfcSIUnit"):
        self._id = unit_id
        self.UnitType = unit_type
        self.Name = name
        self._ifc_class = ifc_class

    def id(self):
        return self._id

    def is_a(self, cls=None):
        if cls is None:
            return self._ifc_class
        if cls == "IfcNamedUnit":
            return self._ifc_class in ("IfcSIUnit", "IfcConversionBasedUnit", "IfcContextDependentUnit")
        return cls == self._ifc_class


class _FakeMonetaryUnit:
    """Not an IfcNamedUnit — must be filtered out of project_unit_entities."""

    UnitType = None

    def id(self):
        return 999

    def is_a(self, cls=None):
        return "IfcMonetaryUnit" if cls is None else cls == "IfcMonetaryUnit"


class _FakeAssignment:
    def __init__(self, units):
        self.Units = units


class _FakeProject:
    def __init__(self, units_in_context):
        self.UnitsInContext = units_in_context


class _FakeFile:
    def __init__(self, project=None, entities=None):
        self._project = project
        self._entities = entities or {}
        self.created = []

    def by_type(self, ifc_class):
        if ifc_class == "IfcProject":
            return [self._project] if self._project else []
        return []

    def by_id(self, step_id):
        return self._entities[step_id]

    def create_entity(self, ifc_class, *args, **kwargs):
        if ifc_class == "IfcNumericMeasure":
            entity = types.SimpleNamespace(wrappedValue=args[0] if args else kwargs.get("value"))
        else:
            entity = types.SimpleNamespace(**kwargs)
        entity.is_a = lambda cls=None, _c=ifc_class: _c if cls is None else cls == _c
        self.created.append(entity)
        return entity


# ---------------------------------------------------------------------------
# project_unit_entities
# ---------------------------------------------------------------------------


def test_project_unit_entities_filters_to_relevant_types_and_excludes_monetary():
    area = _FakeUnit(10, "AREAUNIT", "SQUARE_METRE")
    angle = _FakeUnit(11, "PLANEANGLEUNIT", "RADIAN")  # not a cost-relevant type
    money = _FakeMonetaryUnit()
    project = _FakeProject(_FakeAssignment([area, angle, money]))
    file = _FakeFile(project=project)

    assert cost_tool.project_unit_entities(file) == [area]


def test_project_unit_entities_empty_when_no_units_in_context():
    file = _FakeFile(project=_FakeProject(None))
    assert cost_tool.project_unit_entities(file) == []


def test_project_unit_entities_empty_when_no_project():
    file = _FakeFile(project=None)
    assert cost_tool.project_unit_entities(file) == []


# ---------------------------------------------------------------------------
# resolve_unit_choice
# ---------------------------------------------------------------------------


def test_resolve_unit_choice_none_and_blank():
    file = _FakeFile()
    assert cost_tool.resolve_unit_choice(file, "NONE") is None
    assert cost_tool.resolve_unit_choice(file, "") is None


def test_resolve_unit_choice_looks_up_entity_by_id():
    unit = _FakeUnit(42, "MASSUNIT", "GRAM", ifc_class="IfcSIUnit")
    file = _FakeFile(entities={42: unit})
    assert cost_tool.resolve_unit_choice(file, "42") is unit


def test_resolve_unit_choice_userdefined_creates_a_unit_from_custom_text():
    file = _FakeFile()
    unit = cost_tool.resolve_unit_choice(file, "USERDEFINED", "cad")
    assert unit is not None
    assert unit.Name == "cad"


def test_resolve_unit_choice_userdefined_blank_text_is_none():
    file = _FakeFile()
    assert cost_tool.resolve_unit_choice(file, "USERDEFINED", "   ") is None


# ---------------------------------------------------------------------------
# set_unit_basis_entity
# ---------------------------------------------------------------------------


def test_set_unit_basis_entity_writes_measure_with_unit():
    unit = _FakeUnit(7, "AREAUNIT", "SQUARE_METRE")
    file = _FakeFile()
    cv = types.SimpleNamespace(UnitBasis=None)

    ok = cost_tool.set_unit_basis_entity(file, cv, 3.0, unit)

    assert ok is True
    assert cv.UnitBasis.UnitComponent is unit
    assert cv.UnitBasis.ValueComponent.wrappedValue == 3.0


def test_set_unit_basis_entity_falls_back_to_dimensionless_placeholder():
    file = _FakeFile()
    cv = types.SimpleNamespace(UnitBasis=None)

    ok = cost_tool.set_unit_basis_entity(file, cv, 1.0, None)

    assert ok is True
    assert cv.UnitBasis.UnitComponent.Name == "1"


def test_set_unit_basis_entity_no_qty_is_noop():
    file = _FakeFile()
    cv = types.SimpleNamespace(UnitBasis=None)
    assert cost_tool.set_unit_basis_entity(file, cv, 0.0, None) is False
    assert cv.UnitBasis is None


def test_set_unit_basis_entity_writes_unit_even_with_zero_qty():
    """A Rate Analysis component not yet measured (Qty=0) must still record
    its chosen unit, so the BoQ PDF/ODS 'Unit' column isn't blank."""
    unit = _FakeUnit(5, "AREAUNIT", "SQUARE_METRE")
    file = _FakeFile()
    cv = types.SimpleNamespace(UnitBasis=None)

    ok = cost_tool.set_unit_basis_entity(file, cv, 0.0, unit)

    assert ok is True
    assert cv.UnitBasis.UnitComponent is unit
    assert cv.UnitBasis.ValueComponent.wrappedValue == 0.0


# ---------------------------------------------------------------------------
# ifc_quantity_type_from_unit
# ---------------------------------------------------------------------------


def test_ifc_quantity_type_from_unit_maps_by_unit_type():
    area = _FakeUnit(1, "AREAUNIT", "SQUARE_METRE")
    assert cost_tool.ifc_quantity_type_from_unit(area) == ("IfcQuantityArea", "AreaValue")


def test_ifc_quantity_type_from_unit_defaults_to_count():
    assert cost_tool.ifc_quantity_type_from_unit(None) == ("IfcQuantityCount", "CountValue")
    userdefined = _FakeUnit(2, "USERDEFINED", "cad", ifc_class="IfcContextDependentUnit")
    assert cost_tool.ifc_quantity_type_from_unit(userdefined) == ("IfcQuantityCount", "CountValue")
