# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# All models pre-enabled for Claude, grouped by functional area.
# Tuple: (read, create, write, action) — unlink is always OFF by default.
# Only models whose app is actually installed are seeded (skipped otherwise).
# These are UPPER BOUNDS: every operation still runs under the calling user's
# own Odoo ACL rules, so users can only do what their profile already permits.
COMMON_MODELS = {

    # ── Core / company ───────────────────────────────────────────────────────
    "res.company":                  (1, 0, 0, 0),
    "res.partner":                  (1, 1, 1, 0),
    "res.partner.bank":             (1, 0, 0, 0),
    "res.partner.category":         (1, 0, 0, 0),
    "res.users":                    (1, 0, 0, 0),
    "res.currency":                 (1, 0, 0, 0),
    "res.currency.rate":            (1, 0, 0, 0),
    "res.country":                  (1, 0, 0, 0),
    "res.country.state":            (1, 0, 0, 0),
    "res.bank":                     (1, 0, 0, 0),
    "res.lang":                     (1, 0, 0, 0),

    # ── Products & pricing ───────────────────────────────────────────────────
    "product.template":             (1, 1, 1, 0),
    "product.product":              (1, 0, 0, 0),
    "product.category":             (1, 0, 0, 0),
    "product.supplierinfo":         (1, 0, 0, 0),
    "product.pricelist":            (1, 0, 0, 0),
    "product.pricelist.item":       (1, 0, 0, 0),
    "uom.uom":                      (1, 0, 0, 0),
    "uom.category":                 (1, 0, 0, 0),

    # ── Accounting — chart of accounts & configuration ───────────────────────
    "account.account":              (1, 0, 0, 0),
    "account.account.type":         (1, 0, 0, 0),
    "account.account.tag":          (1, 0, 0, 0),
    "account.group":                (1, 0, 0, 0),
    "account.tax":                  (1, 0, 0, 0),
    "account.tax.group":            (1, 0, 0, 0),
    "account.tax.tag":              (1, 0, 0, 0),
    "account.fiscal.position":      (1, 0, 0, 0),
    "account.fiscal.position.tax":  (1, 0, 0, 0),
    "account.payment.term":         (1, 0, 0, 0),
    "account.payment.term.line":    (1, 0, 0, 0),
    "account.journal":              (1, 0, 0, 0),

    # ── Accounting — transactional ───────────────────────────────────────────
    "account.move":                 (1, 1, 1, 1),
    "account.move.line":            (1, 0, 0, 0),
    "account.payment":              (1, 1, 1, 1),
    "account.bank.statement":       (1, 0, 0, 0),
    "account.bank.statement.line":  (1, 0, 0, 0),
    "account.partial.reconcile":    (1, 0, 0, 0),
    "account.reconcile.model":      (1, 0, 0, 0),

    # ── Accounting — analytics ───────────────────────────────────────────────
    "account.analytic.account":     (1, 0, 0, 0),
    "account.analytic.line":        (1, 0, 0, 0),
    "account.analytic.plan":        (1, 0, 0, 0),

    # ── Accounting — assets (enterprise) ────────────────────────────────────
    "account.asset":                (1, 0, 0, 0),
    "account.asset.asset":          (1, 0, 0, 0),   # v16 name kept for compat

    # ── Sales ────────────────────────────────────────────────────────────────
    "sale.order":                   (1, 1, 1, 1),
    "sale.order.line":              (1, 1, 1, 0),
    "crm.team":                     (1, 0, 0, 0),

    # ── Purchases ────────────────────────────────────────────────────────────
    "purchase.order":               (1, 1, 1, 1),
    "purchase.order.line":          (1, 1, 1, 0),

    # ── CRM ─────────────────────────────────────────────────────────────────
    "crm.lead":                     (1, 1, 1, 1),
    "crm.stage":                    (1, 0, 0, 0),
    "crm.activity.report":          (1, 0, 0, 0),

    # ── Projects ─────────────────────────────────────────────────────────────
    "project.project":              (1, 1, 1, 0),
    "project.task":                 (1, 1, 1, 1),
    "project.task.type":            (1, 0, 0, 0),
    "project.milestone":            (1, 0, 0, 0),
    "project.tags":                 (1, 0, 0, 0),

    # ── Inventory / stock ────────────────────────────────────────────────────
    "stock.warehouse":              (1, 0, 0, 0),
    "stock.location":               (1, 0, 0, 0),
    "stock.picking":                (1, 0, 1, 1),
    "stock.picking.type":           (1, 0, 0, 0),
    "stock.move":                   (1, 0, 0, 0),
    "stock.move.line":              (1, 0, 0, 0),
    "stock.quant":                  (1, 0, 0, 0),
    "stock.lot":                    (1, 0, 0, 0),
    "stock.scrap":                  (1, 0, 0, 0),
    "stock.valuation.layer":        (1, 0, 0, 0),
    "stock.landed.cost":            (1, 0, 0, 0),
    "stock.route":                  (1, 0, 0, 0),
    "stock.rule":                   (1, 0, 0, 0),
    "stock.orderpoint":             (1, 0, 0, 0),

    # ── Manufacturing / MRP ──────────────────────────────────────────────────
    "mrp.production":               (1, 0, 0, 1),
    "mrp.bom":                      (1, 0, 0, 0),
    "mrp.bom.line":                 (1, 0, 0, 0),
    "mrp.workcenter":               (1, 0, 0, 0),
    "mrp.routing.workcenter":       (1, 0, 0, 0),

    # ── HR — personnel ───────────────────────────────────────────────────────
    "hr.employee":                  (1, 0, 1, 0),
    "hr.department":                (1, 0, 0, 0),
    "hr.job":                       (1, 0, 0, 0),
    "hr.contract":                  (1, 0, 0, 0),

    # ── HR — attendance & leaves ─────────────────────────────────────────────
    "hr.attendance":                (1, 0, 0, 0),
    "hr.leave":                     (1, 0, 0, 1),
    "hr.leave.allocation":          (1, 0, 0, 1),
    "hr.leave.type":                (1, 0, 0, 0),

    # ── HR — payroll ─────────────────────────────────────────────────────────
    "hr.payslip":                   (1, 0, 0, 1),
    "hr.payslip.line":              (1, 0, 0, 0),
    "hr.payslip.run":               (1, 0, 0, 1),
    "hr.salary.rule":               (1, 0, 0, 0),
    "hr.salary.rule.category":      (1, 0, 0, 0),

    # ── Expenses ─────────────────────────────────────────────────────────────
    "hr.expense":                   (1, 0, 0, 1),
    "hr.expense.sheet":             (1, 0, 0, 1),

    # ── Helpdesk (enterprise) ────────────────────────────────────────────────
    "helpdesk.ticket":              (1, 0, 1, 1),
    "helpdesk.stage":               (1, 0, 0, 0),
    "helpdesk.team":                (1, 0, 0, 0),

    # ── Maintenance ──────────────────────────────────────────────────────────
    "maintenance.equipment":        (1, 0, 0, 0),
    "maintenance.request":          (1, 0, 0, 1),

    # ── Fleet ────────────────────────────────────────────────────────────────
    "fleet.vehicle":                (1, 0, 0, 0),
    "fleet.vehicle.log.fuel":       (1, 0, 0, 0),
    "fleet.vehicle.log.services":   (1, 0, 0, 0),
    "fleet.vehicle.cost":           (1, 0, 0, 0),

    # ── Calendar / communication ─────────────────────────────────────────────
    "calendar.event":               (1, 1, 1, 0),
    "mail.activity":                (1, 1, 1, 0),
    "mail.message":                 (1, 0, 0, 0),

    # ── System / audit (read-only) ───────────────────────────────────────────
    "ir.rule":                      (1, 0, 0, 0),
    "ir.model.access":              (1, 0, 0, 0),
    "res.groups":                   (1, 0, 0, 0),
}


def _seed_models_sql(cr):
    """Seed COMMON_MODELS into claude_enabled_model using raw SQL.

    Uses INSERT ... ON CONFLICT DO UPDATE so it is fully idempotent and
    survives any ORM-level savepoint or transaction issue.

    Conflict resolution (existing record found):
    - ``active`` is always set to TRUE (reactivates archived records).
    - Permissions in COMMON_MODELS are applied only when they are TRUE — we
      never lower a permission the admin has already raised manually.
    - ``allow_unlink`` is never touched here (always stays at whatever the
      admin chose; defaults to FALSE on insert).
    """
    updated = skipped = 0
    _logger.info("ktx_claude_ai: _seed_models_sql start (%s models)", len(COMMON_MODELS))
    for model_name, (r, c, w, a) in COMMON_MODELS.items():
        try:
            cr.execute("""
                INSERT INTO claude_enabled_model
                    (model_id, model_name, active,
                     allow_read, allow_create, allow_write, allow_unlink, allow_action,
                     create_uid, write_uid, create_date, write_date)
                SELECT
                    m.id, m.model, TRUE,
                    %s, %s, %s, FALSE, %s,
                    1, 1, NOW(), NOW()
                FROM ir_model m
                WHERE m.model = %s
                ON CONFLICT (model_id) DO UPDATE SET
                    active       = TRUE,
                    allow_read   = CASE WHEN %s THEN TRUE
                                        ELSE claude_enabled_model.allow_read END,
                    allow_create = CASE WHEN %s THEN TRUE
                                        ELSE claude_enabled_model.allow_create END,
                    allow_write  = CASE WHEN %s THEN TRUE
                                        ELSE claude_enabled_model.allow_write END,
                    allow_action = CASE WHEN %s THEN TRUE
                                        ELSE claude_enabled_model.allow_action END,
                    write_uid    = 1,
                    write_date   = NOW()
            """, (bool(r), bool(c), bool(w), bool(a), model_name,
                  bool(r), bool(c), bool(w), bool(a)))
            if cr.rowcount:
                updated += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
            _logger.debug("ktx_claude_ai: skipped model %s (not installed or error)", model_name,
                          exc_info=True)
    _logger.info(
        "ktx_claude_ai: _seed_models_sql done — upserted=%s skipped=%s",
        updated, skipped,
    )


def _seed_models(env, update_existing=False):
    """Sync claude.enabled.model with COMMON_MODELS via the ORM.

    Kept as a secondary path called from post_init_hook (fresh install only).
    Migrations use _seed_models_sql which is more reliable across all Odoo
    transaction states.
    """
    _seed_models_sql(env.cr)


def post_init_hook(env):
    """Pre-enable common models for Claude on first install."""
    _seed_models(env, update_existing=False)
    _seed_all_models(env)


def _seed_all_models(env):
    """Create *archived* claude.enabled.model entries for every installed
    ir.model not already covered by COMMON_MODELS, using raw SQL.

    Entries are created with all permissions OFF and ``active=False`` so they
    don't clutter the admin list; the admin can unarchive and enable them.
    Only INSERTs — existing records (whether active or archived) are skipped.
    """
    cr = env.cr
    common_set_literal = ", ".join("'%s'" % m.replace("'", "''") for m in COMMON_MODELS)
    try:
        cr.execute("""
            INSERT INTO claude_enabled_model
                (model_id, model_name, active,
                 allow_read, allow_create, allow_write, allow_unlink, allow_action,
                 create_uid, write_uid, create_date, write_date)
            SELECT
                m.id, m.model, FALSE,
                FALSE, FALSE, FALSE, FALSE, FALSE,
                1, 1, NOW(), NOW()
            FROM ir_model m
            WHERE m.model NOT IN (%s)
              AND m.id NOT IN (
                  SELECT model_id FROM claude_enabled_model
              )
        """ % common_set_literal)
        _logger.info("ktx_claude_ai: _seed_all_models inserted %s archived model entries",
                     cr.rowcount)
    except Exception:
        _logger.exception("ktx_claude_ai: _seed_all_models failed")


def post_migrate_hook(env):
    """Sync common models for Claude on install AND on every upgrade.

    Passing update_existing=True ensures that permission changes in
    COMMON_MODELS (e.g. enabling allow_create for account.payment) are
    applied to existing installations without requiring a reinstall.
    """
    _seed_models(env, update_existing=True)
    _seed_all_models(env)
