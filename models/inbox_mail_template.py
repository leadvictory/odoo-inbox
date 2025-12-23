# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

from odoo import fields, models


class InbxoMailTemplate(models.Model):
    _name = 'inbox.mail.template'
    _description = "Inbox mail template"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
