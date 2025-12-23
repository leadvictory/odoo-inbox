# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

import logging
from odoo import api, models, fields
import datetime

_logger = logging.getLogger(__name__)

class InhFetchmailServer(models.Model):
    """Incoming POP/IMAP mail server account"""

    _inherit = 'fetchmail.server'

    author_id = fields.Many2one('res.partner', string="Author", default=lambda self: self.env.user.partner_id.id)

    @api.model
    def _fetch_sent_mails(self):
        """ Method called by cron to fetch mails from servers """
        return self.search([('state', '=', 'done'), ('server_type', 'in', ['pop', 'imap'])]).fetch_sent_mail()

    def fetch_sent_mail(self):
        """ WARNING: meant for cron usage only - will commit() after each email! """
        additionnal_context = {
            'fetchmail_cron_running': True
        }
        MailThread = self.env['mail.thread']
        for server in self:
            _logger.info('start checking for new emails on %s server %s', server.server_type, server.name)
            additionnal_context['default_fetchmail_server_id'] = server.id
            count, failed = 0, 0
            imap_server = None
            pop_server = None
            days = self.env['ir.config_parameter'].sudo().get_param('odoo_inbox.sent_mail_days')
            previous_date = datetime.datetime.today() - datetime.timedelta(days=int(days))
            if server.server_type == 'imap':
                try:
                    imap_server = server.connect()
                    imap_server.select('"[Gmail]/Sent Mail"')
                    result, data = imap_server.search(None, "(ALL)", f'(SENTSINCE {previous_date.strftime("%d-%b-%Y")})')
                    for num in data[0].split():
                        res_id = None
                        result, data = imap_server.fetch(num, '(RFC822)')
                        imap_server.store(num, '-FLAGS', '\\Seen')
                        try:
                            res_id = MailThread.with_context(**additionnal_context).sent_message_process(server.object_id.model, data[0][1], save_original=server.original, strip_attachments=(not server.attach), author_id=server.author_id)
                        except Exception:
                            _logger.info('Failed to process mail from %s server %s.', server.server_type, server.name, exc_info=True)
                            failed += 1
                        imap_server.store(num, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1
                    _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", count, server.server_type, server.name, (count - failed), failed)
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.server_type, server.name, exc_info=True)
                finally:
                    if imap_server:
                        imap_server.close()
                        imap_server.logout()
            server.write({'date': fields.Datetime.now()})
        return True

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sent_mail_days = fields.Integer(string="Fetch Sent Mail Days", config_parameter='odoo_inbox.sent_mail_days')