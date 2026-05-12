import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { rpc } from '@web/core/network/rpc';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {

    // #=== DOM MANIPULATION ===#

    /**
     * Switch to the 'direct' flow when M-Pesa is selected.
     *
     * @override
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'mpesa_daraja') {
            await super._prepareInlineForm(...arguments);
            return;
        }
        if (flow === 'token') {
            return;
        }
        this._setPaymentFlow('direct');
    },

    // #=== PAYMENT FLOW ===#

    /**
     * Validate the phone input, trigger the STK Push, then poll for the result.
     *
     * @override
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'mpesa_daraja') {
            await super._processDirectFlow(...arguments);
            return;
        }

        const phone = this._getMpesaPhone();
        if (!phone) {
            this._displayErrorDialog(
                _t('Phone number required'),
                _t('Please enter your Safaricom phone number to pay with M-Pesa.')
            );
            this._enableButton();
            return;
        }

        // Show a "sending" message while the RPC is in flight.
        this._setMpesaStatus('info', _t('Sending STK Push to %s…', phone));

        let initiateResult;
        try {
            initiateResult = await rpc('/payment/mpesa/initiate', {
                reference: processingValues.reference,
                phone: phone,
            });
        } catch (e) {
            this._setMpesaStatus('danger', e.message || String(e));
            this._enableButton();
            return;
        }

        if (initiateResult.error) {
            this._setMpesaStatus('danger', initiateResult.error);
            this._enableButton();
            return;
        }

        // Push delivered — tell the user to check their phone.
        this._setMpesaStatus(
            'info',
            _t('STK Push sent! Check your phone and enter your M-Pesa PIN to complete the payment.')
        );

        // Start polling for the callback result.
        await this._pollMpesaStatus(processingValues.reference);
    },

    // #=== HELPERS ===#

    /**
     * Read and normalise the phone number from the inline form.
     * @return {string|null}
     */
    _getMpesaPhone() {
        const input = document.getElementById('o_mpesa_phone');
        if (!input) return null;
        const raw = (input.value || '').replace(/\s+/g, '');
        if (!raw) return null;
        // Normalise 07xxx → 2547xxx
        if (/^0[17]\d{8}$/.test(raw)) {
            return '254' + raw.slice(1);
        }
        // Already internationalised
        if (/^254[17]\d{8}$/.test(raw)) {
            return raw;
        }
        return raw; // Pass through — server will validate
    },

    /**
     * Show a coloured status message inside the inline form.
     * @param {'info'|'success'|'danger'} type
     * @param {string} msg
     */
    _setMpesaStatus(type, msg) {
        const el = document.getElementById('o_mpesa_status');
        if (!el) return;
        el.className = `alert alert-${type}`;
        el.textContent = msg;
        el.classList.remove('d-none');
    },

    /**
     * Poll /payment/mpesa/status every 3 s until a terminal state is reached.
     * Maximum wait: 90 seconds (30 polls).
     *
     * @param {string} reference
     */
    async _pollMpesaStatus(reference) {
        // Poll for up to 70 s — slightly beyond Safaricom's 60 s STK timeout
        // so the server has time to detect and record the expiry first.
        const MAX_POLLS = 23;
        const INTERVAL_MS = 3000;

        for (let i = 0; i < MAX_POLLS; i++) {
            await new Promise(resolve => setTimeout(resolve, INTERVAL_MS));

            // Update elapsed time every 15 s so the user knows we're still waiting.
            const elapsed = Math.round(((i + 1) * INTERVAL_MS) / 1000);
            if (elapsed % 15 === 0) {
                this._setMpesaStatus(
                    'info',
                    _t('Still waiting for your M-Pesa PIN… (%ss)', elapsed)
                );
            }

            let result;
            try {
                result = await rpc('/payment/mpesa/status', { reference });
            } catch (e) {
                // Network hiccup — keep polling
                continue;
            }

            const state = result.state;
            if (state === 'done') {
                this._setMpesaStatus('success', _t('Payment confirmed! Redirecting…'));
                window.location = '/payment/status';
                return;
            } else if (state === 'cancel' || state === 'error') {
                const desc = result.result_desc || _t('Payment was not completed.');
                this._setMpesaStatus('danger', desc);
                this._enableButton();
                return;
            }
            // state === 'pending' → keep polling
        }

        // Timed out on the client side — the server will have already marked
        // the mpesa.transaction as failed after Safaricom's 60 s STK expiry.
        this._setMpesaStatus(
            'danger',
            _t('The M-Pesa prompt expired (60s). Please try again.')
        );
        this._enableButton();
    },
});
