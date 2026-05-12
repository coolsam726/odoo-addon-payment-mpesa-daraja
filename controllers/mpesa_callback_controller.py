# -*- coding: utf-8 -*-
"""
Controller for the payment_mpesa_daraja web payment provider.

Endpoints
---------
POST /payment/mpesa/initiate
    Receives the customer's phone number and transaction reference from the
    inline checkout form, triggers the STK Push, and returns the
    checkout_request_id so the frontend can start polling.

GET  /payment/mpesa/status?reference=<ref>
    Lightweight status poll.  The frontend JS calls this every few seconds
    while waiting for the customer's PIN entry.  Returns
    {'state': <payment.transaction.state>, 'result_desc': ...}.

The actual Daraja HTTP callbacks (STK result, C2B confirmation) are handled
by mpesa_daraja/controllers/mpesa_callbacks.py.  When mpesa.transaction is
updated there, _notify_pos() is called — no override is needed here because
_mpesa_poll_status() picks up the updated state on the next poll cycle.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'mpesa_daraja'


class MpesaPaymentController(http.Controller):

    @http.route(
        '/payment/mpesa_daraja/initiate',
        type='jsonrpc',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def mpesa_initiate(self, reference, phone, **kwargs):
        """Trigger the STK Push for the given payment transaction.

        Called by the JS payment_form patch after the customer enters their
        phone number on the checkout page.

        :param str reference: The payment.transaction reference (e.g. 'S00123').
        :param str phone: The customer's Safaricom phone number.
        :return: dict with 'checkout_request_id' and 'mpesa_tx_id'.
        :raises: werkzeug.exceptions.Forbidden if the transaction cannot be
                 found or is not in a valid state for payment.
        """
        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', PROVIDER_CODE)],
            limit=1,
        )
        if not tx_sudo or tx_sudo.state not in ('draft', 'pending'):
            return {'error': 'Transaction not found or not in a payable state.'}
        try:
            result = tx_sudo._mpesa_initiate_stk_push(phone=phone)
        except Exception as exc:
            _logger.warning('M-Pesa initiate failed for %s: %s', reference, exc)
            return {'error': str(exc)}
        return result

    @http.route(
        '/payment/mpesa_daraja/status',
        type='jsonrpc',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def mpesa_status(self, reference, **kwargs):
        """Poll the current state of a payment transaction.

        Called by the JS poller every few seconds while the customer is
        entering their PIN.

        :param str reference: The payment.transaction reference.
        :return: dict with 'state' and 'result_desc'.
        """
        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', PROVIDER_CODE)],
            limit=1,
        )
        if not tx_sudo:
            return {'state': 'error', 'result_desc': 'Transaction not found.'}
        return tx_sudo._mpesa_poll_status()

