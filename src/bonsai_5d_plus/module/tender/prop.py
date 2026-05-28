# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import _boq_items, _tender_items, _safety_item_enum


class TenderPriceItem(bpy.types.PropertyGroup):
    ifc_id: bpy.props.IntProperty()
    identification: bpy.props.StringProperty()
    item_name: bpy.props.StringProperty()
    unit_label: bpy.props.StringProperty()
    quantity: bpy.props.FloatProperty(precision=3)
    unit_price: bpy.props.FloatProperty(name="P.U.", min=0.0, precision=2)


classes = [TenderPriceItem]


def register():
    bpy.types.Scene.tender_source_boq = bpy.props.EnumProperty(
        name="Source BoQ",
        items=_boq_items,
    )
    bpy.types.Scene.tender_price_mode = bpy.props.EnumProperty(
        name="Price mode",
        items=[
            ("EMPTY",    "Empty prices",    "Leaf prices start at 0, filled manually"),
            ("DISCOUNT", "Apply discount %", "Apply a percentage discount to source prices"),
        ],
        default="EMPTY",
    )
    bpy.types.Scene.tender_discount_pct = bpy.props.FloatProperty(
        name="Discount %",
        min=0.0, max=100.0, precision=3, default=0.0,
        subtype="PERCENTAGE",
    )
    bpy.types.Scene.tender_safety_item_id = bpy.props.EnumProperty(
        name="Exclude from discount",
        items=_safety_item_enum,
        description="Summary item whose entire subtree is excluded from the discount",
    )
    bpy.types.Scene.tender_company_name = bpy.props.StringProperty(
        name="Name",
        default="",
    )
    bpy.types.Scene.tender_active_schedule = bpy.props.EnumProperty(
        name="Tender",
        items=_tender_items,
    )
    bpy.types.Scene.tender_price_items = bpy.props.CollectionProperty(type=TenderPriceItem)
    bpy.types.Scene.tender_price_index = bpy.props.IntProperty(default=0)


def unregister():
    del bpy.types.Scene.tender_price_mode
    del bpy.types.Scene.tender_discount_pct
    del bpy.types.Scene.tender_safety_item_id
    del bpy.types.Scene.tender_source_boq
    del bpy.types.Scene.tender_company_name
    del bpy.types.Scene.tender_active_schedule
    del bpy.types.Scene.tender_price_items
    del bpy.types.Scene.tender_price_index
