# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

{
    'name': 'Mailbox (Odoo Inbox)',
    'version': '16.0.1.6',
    'category': 'Website/Website',
    'summary': 'This module is used to send or receive mail through the recipient, user can do the following types of message-send message, inbox message, starred or unstarred message, etc.',
    'description':
        """
Mailbox (Odoo Inbox)
====================
    """,
    'license': 'OPL-1',
    'author': 'Kanak Infosystems LLP.',
    'website': 'https://www.kanakinfosystems.com',
    'depends': ['portal', 'mail', 'contacts'],
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/template.xml',
        'views/mail_message.xml',
        'views/res_users_views.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'bootstrap': True,  # load translations for login screen
    'application': True,
    'assets': {
        'web.assets_frontend': [
            '/odoo_inbox/static/lib/summernote-0.8.18/summernote-bs5.css',
            '/odoo_inbox/static/lib/select/css/select2.css',
            '/odoo_inbox/static/lib/select2_boostrap/select2-bootstrap.css',
            '/odoo_inbox/static/src/scss/odoo_inbox.scss',
            '/odoo_inbox/static/lib/summernote-0.8.18/summernote-bs5.js',
            '/odoo_inbox/static/src/js/file_attachment.js',
            '/odoo_inbox/static/lib/jquery-resizable.js',
            '/odoo_inbox/static/src/js/odoo_inbox.js',
            ('remove', '/web/static/lib/select2/select2.js'),
            '/odoo_inbox/static/lib/select/js/select2.js',
            '/odoo_inbox/static/src/xml/website.xml',
        ],
        'web.assets_common': [
            ('remove', '/web/static/lib/select2/select2.js'),
            '/odoo_inbox/static/lib/select/js/select2.js',
        ],
    },
    'price': 250,
    'currency': 'EUR',
}
