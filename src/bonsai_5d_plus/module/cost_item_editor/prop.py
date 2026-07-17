# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import COMPONENT_CATEGORIES, _unit_enum_items
from ...tool.cost import QTY_TYPE_INFO

_QTY_ENUM_ITEMS = [(k, v['label'], v['label']) for k, v in QTY_TYPE_INFO.items()]


class RateAnalysisComponent(bpy.types.PropertyGroup):
    category: bpy.props.EnumProperty(
        name="Category",
        items=COMPONENT_CATEGORIES,
        default='LABOR',
        options={'SKIP_SAVE'},
    )
    description: bpy.props.StringProperty(name="Description", options={'SKIP_SAVE'})
    unit: bpy.props.EnumProperty(name="Unit", items=_unit_enum_items, options={'SKIP_SAVE'})
    unit_custom: bpy.props.StringProperty(
        name="Custom Unit",
        description="Custom unit string, used when Unit is set to Custom…",
        options={'SKIP_SAVE'},
    )
    qty: bpy.props.FloatProperty(name="Qty", min=0.0, precision=3, default=1.0, options={'SKIP_SAVE'})
    unit_price: bpy.props.FloatProperty(name="Unit Price", min=0.0, precision=2, default=0.0, options={'SKIP_SAVE'})
    source_ifc_id: bpy.props.IntProperty(
        name="Source IFC ID",
        description="Step ID of the source IfcCostItem in the current project (0 = free-form)",
        default=0,
        options={'SKIP_SAVE'},
    )
    source_identification: bpy.props.StringProperty(
        name="Source Identification",
        description="Identification of the source rate item (cached for display)",
        default="",
        options={'SKIP_SAVE'},
    )
    needs_rate_update: bpy.props.BoolProperty(
        name="Rate value has changed",
        default=False,
        options={'SKIP_SAVE'},
    )


class MeasureRow(bpy.types.PropertyGroup):
    """Single row of a libretto-delle-misure measurement table."""
    qty_desc: bpy.props.StringProperty(name="Description", options={'SKIP_SAVE'})
    qty_nr: bpy.props.FloatProperty(name="NR", precision=2, options={'SKIP_SAVE'})
    qty_l: bpy.props.FloatProperty(name="L", precision=2, options={'SKIP_SAVE'})
    qty_b: bpy.props.FloatProperty(name="B", precision=2, options={'SKIP_SAVE'})
    qty_h: bpy.props.FloatProperty(name="H", precision=2, options={'SKIP_SAVE'})
    ifc_id: bpy.props.IntProperty(name="IFC ID", default=0, options={'SKIP_SAVE'})
    is_selected: bpy.props.BoolProperty(name="Selected", default=False, options={'SKIP_SAVE'})


classes = [RateAnalysisComponent, MeasureRow]


def register():
    bpy.types.WindowManager.rate_analysis_components = bpy.props.CollectionProperty(
        type=RateAnalysisComponent,
    )
    bpy.types.WindowManager.rate_analysis_active_index = bpy.props.IntProperty(default=0)
    bpy.types.WindowManager.rate_analysis_overhead_pct = bpy.props.FloatProperty(
        name="Overhead %",
        description="Overhead percentage applied to technical cost",
        default=15.0, min=0.0, max=100.0, precision=1,
    )
    bpy.types.WindowManager.rate_analysis_profit_pct = bpy.props.FloatProperty(
        name="Profit %",
        description="Profit margin applied to (technical cost + overhead)",
        default=10.0, min=0.0, max=100.0, precision=1,
    )
    bpy.types.WindowManager.rate_analysis_rounding = bpy.props.FloatProperty(
        name="Rounding",
        description="Rounding adjustment (positive or negative) added to the final price",
        default=0.0, precision=2,
    )
    bpy.types.WindowManager.rate_analysis_unit = bpy.props.EnumProperty(
        name="Unit of Measure",
        description="Unit of measure for the finished work",
        items=_unit_enum_items,
    )
    bpy.types.WindowManager.rate_analysis_unit_custom = bpy.props.StringProperty(
        name="Custom Unit",
        description="Custom unit string, used when Unit of Measure is set to Custom…",
        default="",
    )
    bpy.types.WindowManager.rate_analysis_item_identification = bpy.props.StringProperty(
        name="Identification", default="",
    )
    bpy.types.WindowManager.rate_analysis_item_name = bpy.props.StringProperty(
        name="Name", default="",
    )
    bpy.types.WindowManager.rate_analysis_item_description = bpy.props.StringProperty(
        name="Description", default="",
    )
    bpy.types.WindowManager.rate_analysis_target_ifc_id = bpy.props.IntProperty(
        name="Target IFC ID",
        description="IFC step ID of the cost item being analysed (0 = none)",
        default=0,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.rate_analysis_editing_description = bpy.props.BoolProperty(
        name="Editing Description",
        default=False,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.rate_analysis_drafting = bpy.props.BoolProperty(
        name="Drafting Rate Analysis",
        description="A new rate analysis is being built for the current item, not yet applied to IFC",
        default=False,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.rate_analysis_auto_load = bpy.props.BoolProperty(
        name="Auto Load",
        description="Automatically reload data when the active cost item changes",
        default=False,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.cost_value_mode = bpy.props.EnumProperty(
        name="Cost Value Mode",
        items=[
            ('SUM', "Sum", "This item sums its children's costs (Category='*')"),
            ('FIXED', "Fixed", "A single flat price, with no cost breakdown"),
            ('RATE_ANALYSIS', "Rate Analysis", "Build the price from labor/material/equipment components"),
        ],
        default='FIXED',
    )
    bpy.types.WindowManager.cost_value_fixed_components = bpy.props.CollectionProperty(
        type=RateAnalysisComponent,
    )
    bpy.types.WindowManager.cost_value_fixed_active_index = bpy.props.IntProperty(default=0)
    bpy.types.WindowManager.cost_value_fixed_drafting = bpy.props.BoolProperty(
        name="Drafting Fixed Cost Values",
        description="New fixed cost values are being built for the current item, not yet applied to IFC",
        default=False,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.cost_value_fixed_unit = bpy.props.EnumProperty(
        name="Unit",
        description="Unit of measure shared by all fixed cost values on this item",
        items=_unit_enum_items,
    )
    bpy.types.WindowManager.cost_value_fixed_unit_custom = bpy.props.StringProperty(
        name="Custom Unit",
        description="Custom unit string, used when Unit is set to Custom…",
        default="",
    )
    bpy.types.WindowManager.cost_value_fixed_unit_mixed = bpy.props.BoolProperty(
        name="Mixed Units on Load",
        description="The loaded cost values had different units — unified to one on load, review before applying",
        default=False,
        options={'SKIP_SAVE'},
    )
    bpy.types.WindowManager.cost_quantities = bpy.props.CollectionProperty(type=MeasureRow)
    bpy.types.WindowManager.cost_quantities_active_index = bpy.props.IntProperty(default=0)
    bpy.types.WindowManager.cost_quantities_type = bpy.props.EnumProperty(
        name="Quantity Type",
        items=_QTY_ENUM_ITEMS,
        default='COUNT',
    )


def unregister():
    del bpy.types.WindowManager.rate_analysis_components
    del bpy.types.WindowManager.rate_analysis_active_index
    del bpy.types.WindowManager.rate_analysis_overhead_pct
    del bpy.types.WindowManager.rate_analysis_profit_pct
    del bpy.types.WindowManager.rate_analysis_rounding
    del bpy.types.WindowManager.rate_analysis_unit
    del bpy.types.WindowManager.rate_analysis_unit_custom
    del bpy.types.WindowManager.rate_analysis_item_identification
    del bpy.types.WindowManager.rate_analysis_item_name
    del bpy.types.WindowManager.rate_analysis_item_description
    del bpy.types.WindowManager.rate_analysis_target_ifc_id
    del bpy.types.WindowManager.rate_analysis_editing_description
    del bpy.types.WindowManager.rate_analysis_drafting
    del bpy.types.WindowManager.rate_analysis_auto_load
    del bpy.types.WindowManager.cost_value_mode
    del bpy.types.WindowManager.cost_value_fixed_components
    del bpy.types.WindowManager.cost_value_fixed_active_index
    del bpy.types.WindowManager.cost_value_fixed_drafting
    del bpy.types.WindowManager.cost_value_fixed_unit
    del bpy.types.WindowManager.cost_value_fixed_unit_custom
    del bpy.types.WindowManager.cost_value_fixed_unit_mixed
    del bpy.types.WindowManager.cost_quantities
    del bpy.types.WindowManager.cost_quantities_active_index
    del bpy.types.WindowManager.cost_quantities_type
