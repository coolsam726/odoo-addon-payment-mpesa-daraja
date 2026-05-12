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

        // Show a "waiting for PIN" message.
        this._setMpesaStatus('info', _t('Sending STK Push to %s… Enter your M-Pesa PIN.', phone));

        let initiateResult;
        try {
            initiateResult = await rpc('/payment/mpesa/initiate', {
                reference: processingValues.reference,
                phone: phone,
            });
        } catch (e) {
            this._displayErrorDialog(_t('M-Pesa error'), e.message || String(e));
            this._enableButton();
            return;
        }

        if (initiateResult.error) {
            this._displayErrorDialog(_t('M-Pesa error'), initiateResult.error);
            this._enableButton();
            return;
        }

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
        const MAX_POLLS = 30;
        const INTERVAL_MS = 3000;

        for (let i = 0; i < MAX_POLLS; i++) {
            await new Promise(resolve => setTimeout(resolve, INTERVAL_MS));
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

        // Timed out waiting for PIN
        this._setMpesaStatus(
            'danger',
            _t('M-Pesa payment timed out. Please try again.')
        );
        this._enableButton();
    },
});
