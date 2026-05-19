# -*- coding: utf-8 -*-
def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_partner
        ADD COLUMN IF NOT EXISTS ktx_expense_limit double precision DEFAULT 0.0;
    """)
    cr.execute("""
        ALTER TABLE ktx_settlement
        ADD COLUMN IF NOT EXISTS intercompany_receivable_id integer;
    """)
