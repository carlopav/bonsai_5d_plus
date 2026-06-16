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

"""Cost-schedule exporters — IFC → external formats. Symmetric to core/parsers.

Pure-Python (ifcopenshell + stdlib only, zero bpy dependency) so they can be
unit-tested outside Blender. The Blender operators only resolve the active
schedule and pass the ``ifcopenshell.file`` plus the schedule entity in.
"""

from .xpwe import export_cost_schedule_to_xpwe

__all__ = ["export_cost_schedule_to_xpwe"]
