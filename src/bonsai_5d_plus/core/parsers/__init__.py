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

"""Pure-Python price list parsers — zero bpy dependency.

Imported by module/rate_list_importer and module/import_export. Each regional parser
lives in its own submodule; shared base class and category helpers are in
``base``. This package re-exports the public names so existing imports such as
``from ...core.parsers import ParserXpwe`` keep working unchanged.
"""

from .base import (
    XmlRateItem,
    PriceListParser,
    classify_section,
    apply_resource_category,
)
from .veneto import ParserXmlVeneto
from .basilicata import ParserXmlBasilicata
from .toscana import ParserXmlToscana
from .liguria import ParserXmlLiguria
from .lombardia import ParserXmlLombardia
from .xpwe import ParserXpwe
from .six import ParserXmlSix
from .ifc import ParserIfcCostSchedule

__all__ = [
    "XmlRateItem",
    "PriceListParser",
    "classify_section",
    "apply_resource_category",
    "ParserXmlVeneto",
    "ParserXmlBasilicata",
    "ParserXmlToscana",
    "ParserXmlLiguria",
    "ParserXmlLombardia",
    "ParserXpwe",
    "ParserXmlSix",
    "ParserIfcCostSchedule",
    "_find_xml_parser",
]


def _find_xml_parser(xml_content):
    """From Leeno (thanks Giuserpe): pre-scans the XML to pick the right parser."""
    parsers = {
        "PweDatiGenerali": ParserXpwe,
        'xmlns="six.xsd"': ParserXmlSix,
        'autore="Regione Toscana"': ParserXmlToscana,
        'autore="Regione Calabria"': ParserXmlToscana,
        'autore="Regione Campania"': ParserXmlToscana,
        'autore="Regione Sardegna"': ParserXmlToscana,
        'autore="Regione Liguria"': ParserXmlLiguria,
        "rks=": ParserXmlVeneto,
        "<settore cod=": ParserXmlVeneto,
        "<pdf>Prezzario_Regione_Basilicata": ParserXmlBasilicata,
        "<autore>Regione Lombardia": ParserXmlLombardia,
        "<autore>LOM": ParserXmlLombardia,
    }
    for pattern, parser_class in parsers.items():
        if pattern in xml_content:
            return parser_class
    return None
