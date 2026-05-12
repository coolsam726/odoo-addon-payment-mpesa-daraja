# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Provider code registered with Odoo's payment framework.
PROVIDER_CODE = 'mpesa_daraja'


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[(PROVIDER_CODE, 'M-Pesa (Daraja)')],
        ondelete={PROVIDER_CODE: 'set default'},
    )

    # Link every provider instance to one mpesa.config so the STK Push and
    # callback URLs are taken from there rather than duplicating credentials here.
    mpesa_config_id = fields.Many2one(
        'mpesa.config',
        string='M-Pesa Configuration',
        domain="[('company_id', '=', company_id)]",
        help='The Daraja API configuration to use for this payment provider.',
    )

    # ------------------------------------------------------------------ #
    #  Overridable helpers                                                 #
    # ------------------------------------------------------------------ #

    def _get_supported_currencies(self):
        """M-Pesa only processes KES."""
        supported = super()._get_supported_currencies()
        if self.code == PROVIDER_CODE:
            supported = supported.filtered(lambda c: c.name == 'KES')
        return supported

    def _get_default_payment_method_codes(self):
        codes = super()._get_default_payment_method_codes()
        if self.code == PROVIDER_CODE:
            return [PROVIDER_CODE]
        return codes

    # ------------------------------------------------------------------ #
    #  Validation                                                          #
    # ------------------------------------------------------------------ #

    @api.constrains('mpesa_config_id', 'code', 'state')
    def _check_mpesa_config(self):
        for rec in self:
            if (
                rec.code == PROVIDER_CODE
                and rec.state != 'disabled'
                and not rec.mpesa_config_id
            ):
                raise ValidationError(_(
                    'An M-Pesa Daraja configuration is required for this payment provider.'
                ))
