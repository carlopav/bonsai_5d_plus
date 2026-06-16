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

"""SIX schema price-list parser (Emilia/FVG/Trento-xml/DEI-BC)."""

from .base import PriceListParser, apply_resource_category, classify_section


class ParserXmlSix(PriceListParser):
    """Parser per formato XML SIX."""

    def __init__(self, language=None):
        super().__init__()
        self.language = language
        self.default_list_id = None

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        prezzario = root.find("prezzario")
        if prezzario is None:
            return

        prz_desc = prezzario.find("przDescrizione")
        if prz_desc is not None:
            self.title = self.clean_string(prz_desc.attrib.get("breve", ""))

        self.default_list_id = self._get_default_quotazione_id(prezzario)
        units = self.get_units(prezzario)
        specie_categories = self.get_specie_categories(prezzario)
        products = prezzario.findall("prodotto")
        products = sorted(products, key=lambda p: p.attrib.get("prdId", ""))

        index = 0
        prdId_to_index = {}
        prdId_to_category = {}

        for product in products:
            prdId = product.attrib.get("prdId", "")
            level = self.get_level_from_prdId(product)
            is_parent = self.is_parent(product)

            if is_parent:
                prdId_to_index[prdId] = str(index)

            parts = prdId.split(".")
            ancestors = [".".join(parts[:i]) for i in range(1, len(parts))]
            parents = ",".join(prdId_to_index[p] for p in ancestors if p in prdId_to_index)

            desc = product.find("prdDescrizione")
            name = self.clean_string(desc.attrib.get("breve", "")) if desc is not None else ""
            description = self.clean_string(desc.attrib.get("estesa", "")) if desc is not None else ""
            cost_value = self.get_value(product)

            # Resource category: from the product's <specie> when present
            # (Manodopera / Noli / Materiali → single category, Opere Compiute →
            # composite); otherwise inherit from the nearest classified section
            # title (PAT/Emilia have no specie, only MANODOPERA/NOLI/... titles).
            # Leaves never self-classify by name, to avoid composite works whose
            # description merely mentions a resource being mis-attributed.
            specie_id = product.attrib.get("specieId")
            if specie_id and specie_id in specie_categories:
                own_category = specie_categories[specie_id]
            elif is_parent or product.attrib.get("titolo") == "true":
                own_category = classify_section(name)
            else:
                own_category = ""
            parent_category = prdId_to_category.get(ancestors[-1], "") if ancestors else ""
            category = own_category or parent_category
            prdId_to_category[prdId] = category

            item = {
                "index": index,
                "level": level,
                "is_parent": is_parent,
                "parents": parents,
                "id": prdId,
                "name": name,
                "desc": description,
                "unit": self.get_unit(units, product),
                "value": cost_value,
                "labor": self.get_value_component(product, cost_value, "incidenzaManodopera"),
                "equipment": self.get_value_component(product, cost_value, "incidenzaAttrezzatura"),
                "materials": self.get_value_component(product, cost_value, "incidenzaMateriali"),
                "safety": self._get_safety(product, cost_value),
                "category": category,
            }
            # Pure-resource items → 100% to their category; composite works keep
            # the incidenza-derived breakdown parsed above.
            apply_resource_category(item)
            self.xml_rate_list.append(item)
            index += 1

    def _get_default_quotazione_id(self, prezzario):
        lista = prezzario.find("listaQuotazione")
        if lista is not None:
            return lista.attrib.get("listaQuotazioneId")
        return None

    # SIX standard 'specie' codes, used as a fallback when the specie has no
    # description: 10 = Materiali, 20 = Manodopera, 30 = Noli. Composite
    # ('Opere Compiute', usually 60) and others map to "" (no override).
    _SIX_SPCID_CATEGORY = {"10": "Material", "20": "Labor", "30": "Equipment"}

    @staticmethod
    def get_specie_categories(prezzario):
        """Map specieId → IFC category from the prezzario's <specie> table.

        SIX groups products by 'specie' (Manodopera / Noli / Materiali / Opere
        Compiute …). Classify by the specie description, falling back to the
        standard spcId code; composite species resolve to "" (no override).
        """
        categories = {}
        for specie in prezzario.findall("specie"):
            sid = specie.attrib.get("specieId")
            if not sid:
                continue
            desc_el = specie.find("spcDescrizione")
            desc = desc_el.attrib.get("breve", "") if desc_el is not None else ""
            categories[sid] = classify_section(desc) or ParserXmlSix._SIX_SPCID_CATEGORY.get(
                specie.attrib.get("spcId", ""), ""
            )
        return categories

    @staticmethod
    def _get_safety(product, cost_value):
        try:
            return float(product.attrib.get("onereSicurezza", 0)) * cost_value / 100
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def get_units(prezzario):
        units = {}
        umList = prezzario.findall("unitaDiMisura")
        for um in umList:
            attr = um.attrib
            try:
                sym = attr.get("simbolo", attr.get("udmId", ""))
                units[attr["unitaDiMisuraId"]] = sym
            except KeyError:
                pass
        return units

    @staticmethod
    def get_unit(units, product):
        try:
            return units.get(product.attrib.get("unitaDiMisuraId", ""), "")
        except Exception:
            return ""

    def get_value(self, product):
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return 0.0

        for el in quotazioni:
            if self.default_list_id and el.attrib.get("listaQuotazioneId") == self.default_list_id:
                try:
                    return float(el.attrib.get("valore", 0.0))
                except ValueError:
                    return 0.0

        try:
            return float(quotazioni[0].attrib.get("valore", 0.0))
        except ValueError:
            return 0.0

    @staticmethod
    def get_value_component(product, cost_value, component_type):
        if component_type not in ("incidenzaManodopera", "incidenzaMateriali", "incidenzaAttrezzatura"):
            return 0.0
        component_ratio = product.find(component_type)
        try:
            return float(getattr(component_ratio, "text", 0.0)) * cost_value / 100
        except Exception:
            return 0.0

    @staticmethod
    def get_level_from_prdId(product):
        return len(product.attrib.get("prdId", "").split(".")) - 1

    @staticmethod
    def is_parent(product):
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return True

        def _valore(q):
            try:
                return float(q.attrib.get("valore", 0) or 0)
            except (ValueError, TypeError):
                return 0.0

        return all(_valore(q) == 0.0 for q in quotazioni)


