def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS ktx_iva_exencion_account_id INTEGER;
    """)
