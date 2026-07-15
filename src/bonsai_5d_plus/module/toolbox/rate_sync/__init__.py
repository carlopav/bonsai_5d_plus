# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

from . import operator, ui


def register():
    operator.register()
    ui.register()


def unregister():
    ui.unregister()
    operator.unregister()
