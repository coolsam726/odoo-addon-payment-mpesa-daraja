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
    # payment module helper: creates/enables the provider record.
    # Signature: create_or_enable_payment_provider(env, provider_code)
    # Available in Odoo 17+; adjust for your exact Odoo version if needed.
    _logger.info('payment_mpesa_daraja: running post_init_hook')
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
    reset_payment_provider(env, PROVIDER_CODE)
