def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS ktx_isr_trim_account_id INTEGER;
    """)
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS ktx_iso_trim_account_id INTEGER;
    """)
    cr.execute("""
        ALTER TABLE account_account
        ADD COLUMN IF NOT EXISTS ktx_non_deductible BOOLEAN DEFAULT FALSE;
    """)
