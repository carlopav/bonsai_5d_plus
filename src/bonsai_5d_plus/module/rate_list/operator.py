# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import json
import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .data import _do_import, _do_import_ifc, _refresh_ifc_schedules_cache
from ...tool.cost import create_cost_item

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class ImportRateList(Operator, ImportHelper):
    """Import an Italian regional price list (prezzario) in XML or XPWE format."""

    bl_idname = "import.rate_list"
    bl_label = "Import Rate List"
    filename_ext = ".xml"
    filter_glob: bpy.props.StringProperty(
        default="*.xml;*.xpwe",
        options={"HIDDEN"},
        maxlen=255,
    )
    chosen_parser: bpy.props.EnumProperty(
        name="Parser",
        description="Choose the available parser",
        items=[
            ("Auto", "Auto", "Try to guess which importer is more suitable for the given data"),
            ("RegioneVeneto", "Regione Veneto", "Tooltip"),
            ("RegioneFriuliVeneziaGiulia", "Regione Friuli Venezia Giulia", "Tooltip"),
        ],
        default="RegioneVeneto",
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Options:")
        box.label(text="")

    def execute(self, context):
        success = _do_import(self.filepath, context, self.report)
        return {"FINISHED"} if success else {"CANCELLED"}


class UpdateActiveCostItem(*_IfcOperatorBase):
    """Update active cost item with selected rate data."""

    bl_idname = "import.xml_rate_update_cost_item"
    bl_label = "Update active cost item"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = bpy.context.scene.BIMCostProperties
            return (
                len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=False,
            combine_desc=context.scene.xml_rate_combine_desc)


class ImportRateToActiveCostSchedule(*_IfcOperatorBase):
    """Add a new cost item to the active schedule with selected rate data."""

    bl_idname = "import.xml_rate_add_cost_item"
    bl_label = "Import Rate to Active Cost Schedule"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = bpy.context.scene.BIMCostProperties
            return (
                len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True,
            combine_desc=context.scene.xml_rate_combine_desc)


class AssignRateValue(*_IfcOperatorBase):
    """Assign the selected rate as the cost value of the active cost item."""

    bl_idname = "import.xml_rate_assign_cost_value"
    bl_label = "Assign Cost Rate Value"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            if context.scene.rate_source_mode != 'IFC_SCHEDULE':
                return False
            props = context.scene.BIMCostProperties
            if str(props.active_cost_schedule_id) == context.scene.ifc_rate_source_schedule:
                return False
            if props.active_cost_schedule_id == 0 or props.active_cost_item is None:
                return False
            selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
            return json.loads(selected.attributes).get("ifc_id", 0) != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        from bonsai.core import cost as cost_core
        import bonsai.bim.module.cost.data
        selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
        ifc_id = json.loads(selected.attributes).get("ifc_id", 0)
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        cost_rate = file.by_id(ifc_id)
        cost_core.assign_cost_value(tool.Ifc, tool.Cost, cost_item=cost_item, cost_rate=cost_rate)
        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


class CUSTOM_OT_toggle(Operator):
    bl_idname = "xml_rate_list_ui.toggle"
    bl_label = "Toggle"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = context.scene.xml_rate_list[self.index]
        item.is_expanded = not item.is_expanded
        context.scene.xml_rate_list_active_index = self.index
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_0(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_0"
    bl_label = "Collapse to Level 0"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = item.level < 0
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_1(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_1"
    bl_label = "Collapse to Level 1"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = item.level < 1
        return {"FINISHED"}


class CUSTOM_OT_expand_all(Operator):
    bl_idname = "xml_rate_list_ui.expand_all"
    bl_label = "Expand All"

    def execute(self, context):
        for item in context.scene.xml_rate_list:
            if item.is_parent:
                item.is_expanded = True
        return {"FINISHED"}


class IFC_OT_rate_source_refresh(Operator):
    bl_idname = "ifc_rate_source.refresh"
    bl_label = "Refresh Schedules"

    def execute(self, context):
        _refresh_ifc_schedules_cache()
        schedule_id = context.scene.ifc_rate_source_schedule
        if schedule_id and schedule_id != '__NONE__':
            _do_import_ifc(schedule_id, context)
        return {"FINISHED"}


classes = [
    ImportRateList,
    UpdateActiveCostItem,
    ImportRateToActiveCostSchedule,
    AssignRateValue,
    CUSTOM_OT_toggle,
    CUSTOM_OT_collapse_to_level_0,
    CUSTOM_OT_collapse_to_level_1,
    CUSTOM_OT_expand_all,
    IFC_OT_rate_source_refresh,
]
