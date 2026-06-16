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

"""Shared base class and category helpers for the price-list parsers."""

from typing import List, NotRequired, TypedDict


class XmlRateItem(TypedDict):
    index: int
    level: int
    is_parent: bool
    parents: str
    id: str
    name: str
    desc: str
    unit: str
    value: float
    labor: float
    equipment: float
    materials: float
    safety: float
    # IFC IfcCostValue.Category this item maps to: "Labor" / "Equipment" /
    # "Material" / "Safety" for pure resources, or "" for composite items
    # (opere compiute), which instead carry a multi-category breakdown.
    category: NotRequired[str]


# Section-description keywords → IFC cost category. Classifies whole price-list
# sections so the items under them are attributed entirely to one
# IfcCostValue.Category. Terminology varies by region (Veneto: MANODOPERA /
# NOLI / MATERIALI; Toscana: RISORSE UMANE / NOLEGGIO / PRODOTTI DA
# COSTRUZIONE). Keywords are matched as uppercase substrings; keep them
# specific enough not to collide with composite-work section names.
_SECTION_CATEGORY_KEYWORDS = (
    ("MANODOPERA", "Labor"),
    ("MANO D'OPERA", "Labor"),  # DEI XPWE spells it with a space
    ("RISORSE UMANE", "Labor"),
    ("NOLI", "Equipment"),
    ("NOLEGGI", "Equipment"),
    ("SEMILAVORATI", "Material"),
    ("MATERIALI", "Material"),
    ("PRODOTTI DA COSTRUZIONE", "Material"),
    # Specific phrasing — bare "SICUREZZA" would catch composite works such as
    # "barriere di sicurezza" (guardrails); the resource sections are the
    # explicit "SALUTE E SICUREZZA" (Toscana) / "COSTI DELLA SICUREZZA" (PAT).
    ("SALUTE E SICUREZZA", "Safety"),
    ("COSTI DELLA SICUREZZA", "Safety"),
)

# IFC category → XmlRateItem incidence field.
_CATEGORY_FIELD = {
    "Labor": "labor",
    "Equipment": "equipment",
    "Material": "materials",
    "Safety": "safety",
}


def classify_section(desc):
    """Return the IFC cost category for a section description, or "" (composite)."""
    d = (desc or "").upper()
    # Normalise curly/back apostrophes so "MANO D'OPERA" matches regardless of
    # how the source encodes the quote.
    for ch in ("’", "‘", "´", "`"):
        d = d.replace(ch, "'")
    for keyword, category in _SECTION_CATEGORY_KEYWORDS:
        if keyword in d:
            return category
    return ""


def apply_resource_category(item):
    """For a pure-resource item, put 100% of its value in its IFC category.

    No-op for composite items (category ""), whose breakdown is left as parsed.
    """
    field = _CATEGORY_FIELD.get(item.get("category", ""))
    if not field:
        return
    val = item.get("value", 0.0) or 0.0
    for fld in _CATEGORY_FIELD.values():
        item[fld] = val if fld == field else 0.0


class PriceListParser:
    title: str
    desc: str
    year: str
    language: []
    xml_rate_list: List[XmlRateItem]

    def __init__(self):
        self.xml_rate_list = []
        self.title = ""
        self.year = ""

    @staticmethod
    def get_xml_content(filename):
        with open(filename, "r", errors="ignore", encoding="utf8") as file:
            data = file.read()
        return data

    def parse_header(self, root):
        pass

    def parse_items(self, xml_content):
        pass

    def clean_xml_content(self, data):
        import re
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", data)

    def get_stripped_xml_namespaces_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        it = ET.iterparse(StringIO(data))
        for _, el in it:
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.rpartition("}")[-1]
        return it.root

    def get_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        tree = ET.parse(StringIO(data))
        return tree.getroot()

    def clean_string(self, text):
        # sistema_cose (da Leeno)
        text = text.replace("\t", " ").replace("Ã¨", "è").replace("", "")
        text = text.replace("Â°", "°").replace("Ã", "à").replace(" $", "")
        text = text.replace("Ó", "à").replace("Þ", "é").replace("&#x13;", "")
        text = text.replace("&#xD;&#xA;", "").replace("&#xA;", "")
        text = text.replace("&apos;", "'").replace("&#x3;&#x1;", "")
        text = text.replace("\n \n", "\n")
        while "  " in text:
            text = text.replace("  ", " ")
        while "\n\n" in text:
            text = text.replace("\n\n", "\n")
        return text.strip()
