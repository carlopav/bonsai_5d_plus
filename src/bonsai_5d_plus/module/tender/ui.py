# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from ..app_tabs.ui import tab_active
from .operator import (
    CreateTenderScheduleOperator,
    EditTenderPricesOperator,
    ShowTenderComparisonOperator,
    CopyTenderComparisonOperator,
)


class TENDER_UL_PriceItems(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        s = layout.split(factor=0.13)
        s.label(text=(item.identification or "")[:14])
        s2 = s.split(factor=0.48)
        s2.label(text=(item.item_name or "")[:40])
        s3 = s2.split(factor=0.12)
        s3.label(text=(item.unit_label or "")[:8])
        s4 = s3.split(factor=0.22)
        s4.label(text=f"{item.quantity:.2f}")
        s5 = s4.split(factor=0.52)
        s5.prop(item, "unit_price", text="")
        s5.label(text=f"{item.quantity * item.unit_price:,.2f}")


class TenderComparisonPanel(bpy.types.Panel):
    bl_label = "Tenders Manager"
    bl_idname = "SCENE_PT_tender_comparison"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return tab_active(context, "TENDERS")

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Create Tender Schedule", icon="ADD")
        box.prop(context.scene, "tender_source_boq", text="Source BoQ")
        box.prop(context.scene, "tender_company_name", text="Name")
        box.prop(context.scene, "tender_price_mode", expand=True)
        if context.scene.tender_price_mode == "DISCOUNT":
            box.prop(context.scene, "tender_discount_pct", text="Discount %")
            box.prop(context.scene, "tender_safety_item_id", text="Exclude from discount")
        box.operator(CreateTenderScheduleOperator.bl_idname, icon="DUPLICATE")

        box2 = layout.box()
        box2.label(text="Offered Prices", icon="GREASEPENCIL")
        box2.prop(context.scene, "tender_active_schedule", text="Tender")
        box2.operator(EditTenderPricesOperator.bl_idname, icon="MODIFIER")

        box3 = layout.box()
        box3.label(text="Bid Comparison", icon="SPREADSHEET")
        row = box3.row(align=True)
        row.operator(ShowTenderComparisonOperator.bl_idname, icon="NLA_PUSHDOWN")
        row.operator(CopyTenderComparisonOperator.bl_idname, icon="COPYDOWN", text="TSV")


classes = [TENDER_UL_PriceItems, TenderComparisonPanel]
