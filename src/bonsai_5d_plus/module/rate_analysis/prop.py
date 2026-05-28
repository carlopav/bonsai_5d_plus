# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import COMPONENT_CATEGORIES


class RateAnalysisComponent(bpy.types.PropertyGroup):
    category: bpy.props.EnumProperty(
        name="Category",
        items=COMPONENT_CATEGORIES,
        default='LABOR',
        options={'SKIP_SAVE'},
    )
    description: bpy.props.StringProperty(name="Description", options={'SKIP_SAVE'})
    unit: bpy.props.StringProperty(name="Unit", options={'SKIP_SAVE'})
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


classes = [RateAnalysisComponent]


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
    )
    bpy.types.WindowManager.rate_analysis_editing_description = bpy.props.BoolProperty(
        name="Editing Description",
        default=False,
    )
    bpy.types.WindowManager.rate_analysis_auto_load = bpy.props.BoolProperty(
        name="Auto Load",
        description="Automatically reload data when the active cost item changes",
        default=False,
    )


def unregister():
    del bpy.types.WindowManager.rate_analysis_components
    del bpy.types.WindowManager.rate_analysis_active_index
    del bpy.types.WindowManager.rate_analysis_overhead_pct
    del bpy.types.WindowManager.rate_analysis_profit_pct
    del bpy.types.WindowManager.rate_analysis_rounding
    del bpy.types.WindowManager.rate_analysis_item_identification
    del bpy.types.WindowManager.rate_analysis_item_name
    del bpy.types.WindowManager.rate_analysis_item_description
    del bpy.types.WindowManager.rate_analysis_target_ifc_id
    del bpy.types.WindowManager.rate_analysis_editing_description
    del bpy.types.WindowManager.rate_analysis_auto_load
