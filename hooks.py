# -*- coding: utf-8 -*-
"""
Post-install and uninstall hooks for payment_mpesa_daraja.

post_init_hook  — creates the default payment.provider record so the
                  admin doesn't have to do it manually.
uninstall_hook  — archives the provider record (does not delete it, to
                  preserve transaction history).
"""
import logging

from odoo.addons.payment import reset_payment_provider

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'mpesa_daraja'


def post_init_hook(env):
    """Create the default M-Pesa Daraja payment provider if absent."""
    _logger.info('payment_mpesa_daraja: running post_init_hook')
    # _setup_provider creates the account.payment.method record (code=mpesa_daraja,
    # payment_type=inbound) that _ensure_payment_method_line requires to create the
    # inbound payment method line on the journal.
    env['payment.provider']._setup_provider(PROVIDER_CODE)
    existing = env['payment.provider'].search([('code', '=', PROVIDER_CODE)], limit=1)
    if not existing:
        env['payment.provider'].create({
            'name': 'M-Pesa',
            'code': PROVIDER_CODE,
            'state': 'disabled',
        })


def uninstall_hook(env):
    """Archive (not delete) the M-Pesa payment provider on uninstall."""
    _logger.info('payment_mpesa_daraja: running uninstall_hook')
    env['payment.provider']._remove_provider(PROVIDER_CODE)
    reset_payment_provider(env, PROVIDER_CODE)
