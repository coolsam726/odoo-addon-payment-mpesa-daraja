# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

PROVIDER_CODE = 'mpesa_daraja'


class MpesaTransaction(models.Model):
    """payment_mpesa_daraja extension of mpesa.daraja.transaction.

    Adds the ability to manually link a confirmed M-Pesa transaction to an
    existing payment.transaction (web checkout) so that the account.payment
    is created and the e-commerce order is fulfilled even when the Daraja
    callback was never received.
    """

    _inherit = 'mpesa.daraja.transaction'

    # ------------------------------------------------------------------
    # Manual payment.transaction link
    # ------------------------------------------------------------------

    def action_apply_payment_link(self):
        """Link this transaction to a payment.transaction and complete it.

        Workflow (callback was missed):
        1. Back-office opens the stuck ``mpesa.daraja.transaction`` form.
        2. Optionally clicks "Force Confirm" first if it's still ``pending``.
        3. Selects the matching ``payment_transaction_id`` in the
           "Link to Accounting Payment" section and saves.
        4. Clicks "Apply Payment Link" — this button:
           a. Sets the back-reference on ``payment.transaction``.
           b. Calls ``_apply_updates`` with ``state='success'`` which
              triggers ``_set_done()`` + ``_post_process()``, creating the
              ``account.payment`` and marking the daraja transaction as consumed.
        """
        for rec in self:
            if not rec.payment_transaction_id:
                raise UserError(_(
                    'Please select a Payment Transaction to link before applying.'
                ))
            pay_tx = rec.payment_transaction_id.sudo()
            if pay_tx.provider_code != PROVIDER_CODE:
                raise UserError(_(
                    'Payment Transaction %(ref)s does not use the M-Pesa Daraja provider.',
                    ref=pay_tx.reference,
                ))
            if pay_tx.state == 'done':
                raise UserError(_(
                    'Payment Transaction %(ref)s is already in "Done" state — '
                    'no action needed.',
                    ref=pay_tx.reference,
                ))
            if pay_tx.state == 'cancel':
                raise UserError(_(
                    'Payment Transaction %(ref)s is cancelled and cannot be completed.',
                    ref=pay_tx.reference,
                ))
            # Check if another daraja tx is already linked to avoid conflicts.
            if pay_tx.daraja_transaction_id and pay_tx.daraja_transaction_id != rec:
                raise UserError(_(
                    'Payment Transaction %(ref)s is already linked to a different '
                    'M-Pesa transaction (#%(id)s).',
                    ref=pay_tx.reference,
                    id=pay_tx.daraja_transaction_id.id,
                ))

            # Set the back-reference on payment.transaction if not already set.
            if not pay_tx.daraja_transaction_id:
                pay_tx.daraja_transaction_id = rec.id

            # Advance the payment.transaction through _set_done → _post_process.
            # _apply_updates with state='success' handles setting provider_reference,
            # calling _set_done(), and triggering _post_process() (account.payment).
            pay_tx._apply_updates({
                'state': 'success',
                'provider_reference': rec.mpesa_receipt or pay_tx.provider_reference,
                'result_desc': 'Manually confirmed by back-office.',
                'customer_name': ' '.join(filter(None, [
                    rec.first_name, rec.middle_name, rec.last_name
                ])) or None,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment Link Applied'),
                'message': _(
                    'The payment transaction has been completed and the accounting '
                    'payment record has been created.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
