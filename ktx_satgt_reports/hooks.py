# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

_RETENTION_WORDS = ('retenci', 'retencion', 'ret ', 'isr', 'renta')
_PC_WORDS        = ('peque', 'cuota', 'contribuy', 'regimen esp', 'régimen esp')
_EXENTA_WORDS    = ('exent', 'libre', 'exenci', 'no grav', 'no afect')


def _guess_category(tax):
    name   = (tax.name or '').lower()
    amount = tax.amount
    use    = tax.type_tax_use  # 'purchase', 'sale', 'none', 'all'

    if amount == 12 and use == 'purchase':
        if not any(w in name for w in _RETENTION_WORDS):
            return 'iva_compras'
    if amount == 12 and use == 'sale':
        if not any(w in name for w in _RETENTION_WORDS):
            return 'iva_ventas'
    if amount == 12 and use == 'all':
        if not any(w in name for w in _RETENTION_WORDS):
            return 'iva_ventas' if ('venta' in name or 'sale' in name) else 'iva_compras'

    # PC: keywords in name
    if any(w in name for w in _PC_WORDS):
        return 'pequeno_cont'
    # PC: 5% non-retention
    if amount == 5 and use in ('purchase', 'sale', 'all'):
        if not any(w in name for w in _RETENTION_WORDS):
            return 'pequeno_cont'
    # PC: 0% non-retention non-exenta (cuota informativa del comprador)
    if amount == 0 and use in ('purchase', 'sale', 'all'):
        if not any(w in name for w in list(_RETENTION_WORDS) + list(_EXENTA_WORDS)):
            grp_name = (tax.tax_group_id.name or '').lower() if tax.tax_group_id else ''
            if not any(w in grp_name for w in _EXENTA_WORDS):
                return 'pequeno_cont'

    if any(w in name for w in ('retenci', 'retencion', 'ret ')):
        if 'iva' in name:
            return 'iva_retencion'
        if 'isr' in name or 'renta' in name:
            return 'isr_retencion'

    if ('isr' in name or 'renta' in name) and 'ret' in name:
        return 'isr_retencion'

    return None


def auto_detect_sat_categories(env, update_existing=False):
    """Create or update SAT category mappings for all taxes.

    update_existing=True will overwrite previously auto-detected entries
    (does NOT touch taxes that have ktx_satgt_category already set by the user).
    """
    TaxConfig = env['ktx.satgt.tax.config']
    companies = env['res.company'].search([])
    created = updated = 0

    for company in companies:
        taxes = env['account.tax'].search([
            ('company_id', '=', company.id),
            ('active', 'in', [True, False]),
        ])
        existing_map = {
            cfg.tax_id.id: cfg
            for cfg in TaxConfig.search([('company_id', '=', company.id)])
        }
        for tax in taxes:
            category = _guess_category(tax)
            if not category:
                continue
            # Always set field directly on tax if not yet set by user
            if not tax.ktx_satgt_category:
                tax.ktx_satgt_category = category
            # Create or update config record
            if tax.id in existing_map:
                if update_existing and existing_map[tax.id].category != category:
                    existing_map[tax.id].category = category
                    updated += 1
                    _logger.info('SAT GT re-classify: %s %s->%s (%s)',
                                 tax.name, existing_map[tax.id].category, category, company.name)
            else:
                TaxConfig.create({'company_id': company.id, 'category': category, 'tax_id': tax.id})
                created += 1
                _logger.info('SAT GT auto-config: %s -> %s (%s)', tax.name, category, company.name)

    _logger.info('SAT GT auto-config: created=%d updated=%d', created, updated)
    return created + updated


def post_init_hook(env):
    auto_detect_sat_categories(env)
