def migrate(cr, version):
    # Add new Many2one (INTEGER) columns for contador and rep_legal.
    # Old VARCHAR columns (ktx_contador, ktx_contador_nit, ktx_rep_legal,
    # ktx_rep_legal_nit) are left as unused dead columns to avoid any
    # ALTER TABLE DROP COLUMN lock issues that would corrupt the cursor.
    cr.execute("ALTER TABLE res_company ADD COLUMN IF NOT EXISTS ktx_contador_id INTEGER")
    cr.execute("ALTER TABLE res_company ADD COLUMN IF NOT EXISTS ktx_rep_legal_id INTEGER")
