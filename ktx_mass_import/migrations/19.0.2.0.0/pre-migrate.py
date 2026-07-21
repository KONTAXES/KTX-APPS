# -*- coding: utf-8 -*-
"""Migracion a 19.0.2.0.0 - multi-empresa via company_dependent.

Convierte ktx.tax.mapping.tax_id y ktx.phrase.config.tax_id de Many2one
normal (columna integer) a company_dependent (columna jsonb).

Limpia restos de versiones intermedias con bugs:
- columna company_id que se llego a agregar a ktx_tax_mapping
- regla de registro (ir.rule) que referenciaba esa columna
- constraints SQL antiguos (ahora se definen con models.Constraint)

Nota: los valores tax_id anteriores no se migran automaticamente porque
el campo ahora es por empresa (cada empresa debe configurar el suyo).
"""


def _col_type(cr, table, column):
    cr.execute(
        """SELECT data_type FROM information_schema.columns
           WHERE table_name = %s AND column_name = %s""",
        (table, column),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    # 1. Eliminar regla de registro huerfana de versiones intermedias.
    cr.execute(
        """DELETE FROM ir_rule r
           USING ir_model_data d
           WHERE d.model = 'ir.rule' AND d.res_id = r.id
             AND d.module = 'ktx_mass_import'
             AND d.name = 'ktx_tax_mapping_company_rule'"""
    )
    cr.execute("DELETE FROM ir_rule WHERE name = 'KTX Tax Mapping: multi-empresa'")

    # 2. Eliminar columna company_id sobrante en ktx_tax_mapping (bug previo).
    cr.execute("ALTER TABLE ktx_tax_mapping DROP COLUMN IF EXISTS company_id")

    # 3. Eliminar la columna tax_id integer para que Odoo la recree como jsonb
    #    (company_dependent). Si ya es jsonb o no existe, no hacer nada.
    if _col_type(cr, 'ktx_tax_mapping', 'tax_id') == 'integer':
        cr.execute("ALTER TABLE ktx_tax_mapping DROP COLUMN tax_id")

    if _col_type(cr, 'ktx_phrase_config', 'tax_id') == 'integer':
        cr.execute("ALTER TABLE ktx_phrase_config DROP COLUMN tax_id")

    # 4. Eliminar constraints SQL antiguos; se recrean via models.Constraint.
    cr.execute("ALTER TABLE ktx_tax_mapping DROP CONSTRAINT IF EXISTS ktx_tax_mapping_unique_mapping")
    cr.execute("ALTER TABLE ktx_phrase_config DROP CONSTRAINT IF EXISTS ktx_phrase_config_unique_phrase")
