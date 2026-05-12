# -*- coding: utf-8 -*-
{
    'name': 'M-Pesa Payment Provider',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'M-Pesa Daraja payment provider for web / eCommerce checkout',
    'description': """
M-Pesa Daraja — Web Payment Provider
=====================================
Integrates M-Pesa with Odoo's standard payment provider framework so that
customers can pay via M-Pesa STK Push on:

* eCommerce checkout (website_sale)
* Payment links (account_payment)
* Invoice online payment (account)

Flow
----
1. Customer enters their Safaricom phone number on the checkout page.
2. The provider initiates an STK Push via mpesa.config.stk_push().
3. A polling endpoint (or bus) waits for the Daraja callback that arrives
   in mpesa.transaction via the mpesa_daraja callback controller.
4. On success the provider confirms the payment and creates the journal entry.

Status
------
**Work in progress.** The scaffold below inherits from payment.provider and
wires up to the mpesa_daraja base module.  Full implementation of the
controller, form rendering, and transaction lifecycle is pending.
""",
    'author': 'Your Company',
    'website': 'https://example.com',
    'license': 'LGPL-3',
    'depends': [
        'mpesa_daraja',
        'payment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'views/payment_mpesa_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_mpesa_daraja/static/src/interactions/payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
