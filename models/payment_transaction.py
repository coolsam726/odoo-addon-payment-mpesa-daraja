# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'mpesa_daraja'


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # Link to the underlying mpesa.transaction so we can track the STK
    # callback state using the same infrastructure as pos_mpesa_daraja.
    mpesa_transaction_id = fields.Many2one(
        'mpesa.daraja.transaction',
        string='M-Pesa Transaction',
        readonly=True, ondelete='restrict', copy=False,
    )

    # ------------------------------------------------------------------ #
    #  Inline form rendering values (direct flow)                         #
    # ------------------------------------------------------------------ #

    def _get_specific_rendering_values(self, processing_values):
        """Return extra values for the inline form template."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != PROVIDER_CODE:
            return res
        res.update({
            'reference': self.reference,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'partner_phone': self.partner_id.mobile or self.partner_id.phone or '',
        })
        return res

    # ------------------------------------------------------------------ #
    #  Reference extraction (for _process callback dispatch)              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_reference(provider_code, payment_data):
        if provider_code == PROVIDER_CODE:
            return payment_data.get('reference')
        return super(PaymentTransaction, PaymentTransaction)._extract_reference(
            provider_code, payment_data
        )

    # ------------------------------------------------------------------ #
    #  Amount validation — skip (mpesa_daraja already validates)          #
    # ------------------------------------------------------------------ #

    def _extract_amount_data(self, payment_data):
        if self.provider_code == PROVIDER_CODE:
            return None  # opt out of framework amount check
        return super()._extract_amount_data(payment_data)

    # ------------------------------------------------------------------ #
    #  STK Push initiation (called from controller via JSON-RPC)          #
    # ------------------------------------------------------------------ #

    def _mpesa_initiate_stk_push(self, phone):
        """Initiate an STK Push for this transaction.

        Called by the controller when the customer submits the inline form.
        Returns the mpesa.transaction dict (from _for_pos) for the frontend
        to poll against.

        :param str phone: Customer Safaricom phone number.
        :return: dict with keys 'checkout_request_id' and 'mpesa_tx_id',
                 or raises UserError on failure.
        """
        self.ensure_one()
        config = self.provider_id.mpesa_config_id
        if not config:
            raise UserError(_('No M-Pesa configuration linked to this payment provider.'))
        if not phone:
            raise UserError(_('A phone number is required for M-Pesa STK Push.'))
        try:
            data = config.stk_push(
                phone=phone,
                amount=self.amount,
                account_ref=(self.reference or 'Payment')[:12],
                description='Online Payment',
            )
        except Exception as exc:
            _logger.error('M-Pesa STK Push failed for tx %s: %s', self.reference, exc)
            raise UserError(_('M-Pesa STK Push failed: %s') % str(exc)) from exc

        checkout_id = data.get('CheckoutRequestID')
        if not checkout_id:
            raise UserError(_('M-Pesa did not return a CheckoutRequestID.'))

        # Link the newly-created mpesa.daraja.transaction record.
        mpesa_tx = self.env['mpesa.daraja.transaction'].sudo().search(
            [('checkout_request_id', '=', checkout_id)], limit=1
        )
        if mpesa_tx:
            self.sudo().mpesa_transaction_id = mpesa_tx
        self._set_pending()
        return {
            'checkout_request_id': checkout_id,
            'mpesa_tx_id': mpesa_tx.id if mpesa_tx else False,
        }

    # ------------------------------------------------------------------ #
    #  Status polling (called by the frontend JS every few seconds)       #
    # ------------------------------------------------------------------ #

    # Safaricom's built-in STK Push timeout (seconds). After this period
    # with no callback the push has definitely expired.
    _MPESA_STK_TIMEOUT = 60

    def _mpesa_poll_status(self):
        """Return the current payment state for the frontend poller.

        Reconciles the payment.transaction state with the linked
        mpesa.transaction state so the checkout page knows when to redirect.
        Automatically cancels the transaction if Safaricom's 60-second STK
        timeout has elapsed with no callback.

        :return: dict {'state': str, 'result_desc': str|False}
        """
        self.ensure_one()
        mpesa_tx = self.mpesa_transaction_id
        if not mpesa_tx:
            return {'state': self.state, 'result_desc': False}

        mpesa_state = mpesa_tx.state

        if mpesa_state in ('success', 'matched', 'partial') and self.state == 'pending':
            # Daraja confirmed payment — advance the provider transaction.
            self.sudo()._apply_updates({'state': 'success'})

        elif mpesa_state == 'failed' and self.state == 'pending':
            self.sudo()._apply_updates({
                'state': 'failed',
                'result_desc': mpesa_tx.result_desc or 'STK Push failed.',
            })

        elif mpesa_state == 'pending' and self.state == 'pending':
            # Check whether Safaricom's STK timeout has elapsed.
            age = fields.Datetime.now() - mpesa_tx.create_date
            if age > timedelta(seconds=self._MPESA_STK_TIMEOUT):
                timeout_msg = _('M-Pesa STK Push timed out. The prompt expired — please try again.')
                mpesa_tx.sudo().write({'state': 'failed', 'result_desc': timeout_msg})
                self.sudo()._apply_updates({'state': 'failed', 'result_desc': timeout_msg})

        return {
            'state': self.state,
            'result_desc': mpesa_tx.result_desc or False,
        }

    # ------------------------------------------------------------------ #
    #  _apply_updates: advance state from notification data               #
    # ------------------------------------------------------------------ #

    def _apply_updates(self, payment_data):
        if self.provider_code != PROVIDER_CODE:
            return super()._apply_updates(payment_data)
        state = payment_data.get('state')
        if state in ('success', 'matched', 'partial'):
            self._set_done()
        elif state in ('failed', 'error'):
            self._set_canceled(
                state_message=payment_data.get('result_desc') or 'STK Push failed.'
            )
        # 'pending' — leave pending; poller will retry
