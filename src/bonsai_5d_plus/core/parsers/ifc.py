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

"""IfcCostSchedule importer (re-import an existing schedule as a rate list)."""

from .base import PriceListParser


class ParserIfcCostSchedule(PriceListParser):
    """Parser per IfcCostSchedule — progetto corrente o file IFC esterno."""

    def parse_schedule(self, file, schedule_id):
        import ifcopenshell.util.cost as cost_util
        schedule = file.by_id(int(schedule_id))
        self.title = schedule.Name or f"Schedule {schedule_id}"
        root_items = cost_util.get_root_cost_items(schedule)
        index = 0

        def _val(cost_item):
            for cv in (cost_item.CostValues or []):
                try:
                    v = cv.AppliedValue
                    if v is not None:
                        return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                except Exception:
                    pass
            return 0.0

        def _labor(cost_item):
            for cv in (cost_item.CostValues or []):
                for sub in (getattr(cv, 'Components', None) or []):
                    if getattr(sub, 'Category', None) == 'Labor':
                        try:
                            v = sub.AppliedValue
                            return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                        except Exception:
                            pass
            return 0.0

        def traverse(cost_item, level, parent_indices):
            nonlocal index
            has_children = bool(cost_item.IsNestedBy)
            self.xml_rate_list.append({
                "index": index,
                "ifc_id": cost_item.id(),
                "level": level,
                "is_parent": has_children,
                "parents": ",".join(str(p) for p in parent_indices),
                "id": cost_item.Identification or "",
                "name": cost_item.Name or "",
                "desc": cost_item.Description or "",
                "unit": "",
                "value": _val(cost_item),
                "labor": _labor(cost_item),
                "equipment": 0.0,
                "materials": 0.0,
                "safety": 0.0,
            })
            current_index = index
            index += 1
            for rel in (cost_item.IsNestedBy or []):
                for child in rel.RelatedObjects:
                    traverse(child, level + 1, parent_indices + [current_index])

        for root_item in root_items:
            traverse(root_item, 0, [])


