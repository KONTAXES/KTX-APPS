# -*- coding: utf-8 -*-
"""Post-migracion a 19.0.2.0.0.

El campo tax_id ahora es company_dependent. Cada empresa debe asignar
su propio impuesto desde Configuracion > Mapeo de Impuestos SAT.
No se migran automaticamente los valores anteriores.
"""


def migrate(cr, version):
    # Limpiar tablas temporales de versiones de migracion anteriores, si existen.
    cr.execute("DROP TABLE IF EXISTS ktx_tmp_taxmap")
    cr.execute("DROP TABLE IF EXISTS ktx_tmp_phrase")
