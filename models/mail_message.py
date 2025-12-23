# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).
import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Message(models.Model):
    _inherit = 'mail.message'

    msg_unread = fields.Boolean('Message Read')
    message_label = fields.Selection([('inbox', 'Inbox'), ('starred', 'Starred'), ('done', 'Done'), ('snoozed', 'Snoozed'), ('draft', 'Draft'), ('sent', 'SENT'), ('trash', 'TRASH')], string='Message Label', default="inbox")
    draft_message_id = fields.Char(string='Draft Message ID')
    snoozed_time = fields.Datetime('Snoozed Time')
    partner_followers = fields.Many2many('res.partner', 'mail_message_partner_rel', 'mail_id', 'partner_id', string='Partners')
    tag_ids = fields.Many2many('message.tag', 'mail_message_tags_rel', 'mail_id', 'tag_id', string='Tag')
    folder_id = fields.Many2one('message.folder', string='Folder')
    email_cc_ids = fields.Many2many('res.partner', 'mail_notification_cc', 'message_id', 'partner_id', string='CC',
                                    help='Partners that have a notification pushing this message in their mailboxes')
    email_bcc_ids = fields.Many2many('res.partner', 'mail_notification_bcc', 'message_id', 'partner_id', string='BCC',
                                     help='Partners that have a notification pushing this message in their mailboxes')

    def get_messages_time(self, your_time=None):
        if your_time == 'tomorrow':
            snooze = fields.Datetime.context_timestamp(self, datetime.now() + timedelta(days=1)).strftime("%a %I:%M %p")
        else:
            snooze = fields.Datetime.context_timestamp(self, datetime.now() + timedelta(hours=2)).strftime("%I:%M %p")
        return snooze

    @api.model
    def set_to_inbox(self):
        domain = [('message_label', '=', 'snoozed')]
        all_message = self.sudo().search(domain)
        for msg in all_message:
            now = fields.Datetime.from_string(fields.Datetime.now())
            snoozed_time = fields.Datetime.from_string(msg.snoozed_time)
            if snoozed_time and snoozed_time <= now:
                msg.message_label = 'inbox'

    @api.model
    def message_fetch(self, domain, limit=20):
        domain += [('message_type', '!=', 'email')]
        return self.search(domain, limit=limit).message_format()

    def get_message_rec_name(self):
        rac_name = False
        if self.model and self.res_id:
            record = self.env[self.model].browse(self.res_id)
            rac_name = record.display_name
        return rac_name
