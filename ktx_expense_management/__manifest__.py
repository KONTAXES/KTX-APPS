# -*- coding: utf-8 -*-
{
    "name": "KTX Expense Settlements",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "summary": "Full expense settlement workflow: staging, multi-level approval, automatic journal entries, payment wizard and KPI dashboard",
    "description": """
KTX Expense Settlements
========================
Complete expense reimbursement workflow for Odoo 19.

Key features:
- Expense staging (group vendor bills / journal entries)
- Multi-level approval flow: Draft → Confirmed → Approved → Posted → Paid
- Automatic journal entries on posting (multicompany, multicurrency)
- Payment wizard with journal, date, amount, write-off handling
- Odoo activities + email notifications at each state change
- Per-employee spending limits
- Rejection with mandatory reason note
- KPI dashboard: totals by state, pending amount, monthly chart, top employees
- Export to Excel with one click
- Intercompany: assign a different paying company per settlement

Compatible with Odoo 19 Community and Enterprise, on-premise only.
    """,
    "author": "KONTAXES",
    "website": "https://app.kontaxes.com",
    "license": "LGPL-3",
    "price": 0,
    "currency": "USD",
    "depends": [
        "account",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "report/settlement_report.xml",
        "views/settlement_staging_views.xml",
        "views/settlement_views.xml",
        "views/settlement_payment_wizard_views.xml",
        "views/settlement_reject_wizard_views.xml",
        "views/staging_selection_wizard_views.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "views/dashboard_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "images": [
        "static/description/banner.png",
    ],
    "web_icon": "ktx_expense_management,static/description/icon.png",
}
