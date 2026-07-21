def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS ktx_contador VARCHAR,
        ADD COLUMN IF NOT EXISTS ktx_contador_nit VARCHAR,
        ADD COLUMN IF NOT EXISTS ktx_contador_reg VARCHAR,
        ADD COLUMN IF NOT EXISTS ktx_rep_legal VARCHAR,
        ADD COLUMN IF NOT EXISTS ktx_rep_legal_nit VARCHAR;
    """)
