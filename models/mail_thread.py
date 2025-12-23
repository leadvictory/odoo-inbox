# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

import logging
import threading
from xmlrpc import client as xmlrpclib
import email
from odoo import api, models, registry, SUPERUSER_ID, Command, tools
from odoo.tools.misc import clean_context, split_every
import re

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'


    def add_email_reciepient(self, partner_ids):
        result_ids = []
        for user in self.env['res.users'].search([('child_partner_ids','!=',False)]):
            if partner_ids[0] in user.child_partner_ids.ids:
                result_ids.extend(user.partner_id.ids)
                result_ids.extend(self.add_email_reciepient(user.partner_id.ids))

        return result_ids 
                

    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        catchall_alias = self.env['ir.config_parameter'].sudo().get_param("mail.catchall.alias")
        bounce_alias = self.env['ir.config_parameter'].sudo().get_param("mail.bounce.alias")
        thread_references = message_dict['references'] or message_dict['in_reply_to']
        msg_references = [
            re.sub(r'[\r\n\t ]+', r'', ref)  # "Unfold" buggy references
            for ref in tools.mail_header_msgid_re.findall(thread_references)
            if 'reply_to' not in ref
        ]
        mail_messages = self.env['mail.message'].sudo().search([('message_id', 'in', msg_references)], limit=1, order='id desc, message_id')
        is_a_reply = bool(mail_messages)
        reply_model, reply_thread_id = mail_messages.model, mail_messages.res_id
        rcpt_tos_localparts = [
            e.split('@')[0].lower()
            for e in tools.email_split(message_dict['recipients'])
        ]
        email_from = message_dict['email_from']
        email_from_localpart = (tools.email_split(email_from) or [''])[0].split('@', 1)[0].lower()
        email_to = message_dict['to']
        email_to_localparts = [
            e.split('@', 1)[0].lower()
            for e in (tools.email_split(email_to) or [''])
        ]

        if len(message_dict['partner_ids']) > 0:
            message_dict['partner_ids'] += self.add_email_reciepient(message_dict['partner_ids'])


        rcpt_tos_valid_localparts = [to for to in rcpt_tos_localparts]
        if reply_model and reply_thread_id:
            reply_model_id = self.env['ir.model']._get_id(reply_model)
            other_model_aliases = self.env['mail.alias'].search([
                '&', '&',
                ('alias_name', '!=', False),
                ('alias_name', 'in', email_to_localparts),
                ('alias_model_id', '!=', reply_model_id),
            ])
            if other_model_aliases:
                is_a_reply = False
                rcpt_tos_valid_localparts = [to for to in rcpt_tos_valid_localparts if to in other_model_aliases.mapped('alias_name')]
        if rcpt_tos_localparts:
            # no route found for a matching reference (or reply), so parent is invalid
            message_dict.pop('parent_id', None)

            # check it does not directly contact catchall
            if catchall_alias and email_to_localparts and all(email_localpart == catchall_alias for email_localpart in email_to_localparts):
                _logger.info('Routing mail from %s to %s with Message-Id %s: direct write to catchall, bounce', email_from, email_to, message_id)
                body = self.env.ref('mail.mail_bounce_catchall')._render({
                    'message': message,
                }, engine='ir.qweb')
                self._routing_create_bounce_email(email_from, body, message, references=message_id, reply_to=self.env.company.email)
                return []

            dest_aliases = self.env['mail.alias'].search([('alias_name', 'in', rcpt_tos_valid_localparts)])
            if not dest_aliases:
                if 'default_fetchmail_server_id' in self.env.context:
                    mail_server_id = self.env['fetchmail.server'].browse(int(self.env.context.get('default_fetchmail_server_id')))
                    if mail_server_id.author_id:
                        self.env['mail.followers']._insert_followers(
                        mail_server_id.author_id._name, mail_server_id.author_id.ids,
                        mail_server_id.author_id.ids, subtypes=None, check_existing=True, existing_policy='skip')
                        return [(mail_server_id.author_id._name, mail_server_id.author_id.id, {}, mail_server_id.author_id.id, False)]
        return super(MailThread, self).message_route(message, message_dict, model, thread_id, custom_values)

    @api.model
    def sent_message_process(self, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None, author_id=False):
        if isinstance(message, xmlrpclib.Binary):
            message = bytes(message.data)
        if isinstance(message, str):
            message = message.encode('utf-8')
        message = email.message_from_bytes(message, policy=email.policy.SMTP)

        # parse the message, verify we are not in a loop by checking message_id is not duplicated
        msg_dict = self.message_parse(message, save_original=save_original)
        if strip_attachments:
            msg_dict.pop('attachments', None)

        existing_msg_ids = self.env['mail.message'].search([('message_id', '=', msg_dict['message_id'])], limit=1)
        if existing_msg_ids:
            _logger.info('Ignored mail from %s to %s with Message-Id %s: found duplicated Message-Id during processing',
                         msg_dict.get('email_from'), msg_dict.get('to'), msg_dict.get('message_id'))
            return False
        partner_id = False
        if msg_dict.get('cc'):
            partner_id = self.env['res.partner'].sudo().search([('name', '=', msg_dict.get('cc').split('@')[0]), ('email', '=', msg_dict.get('cc'))])
            if not partner_id:
                partner_id = self.env['res.partner'].sudo().create({
                    'name': msg_dict.get('cc').split('@')[0],
                    'email': msg_dict.get('cc')
                    })
        author_id = author_id or self.env.user.partner_id
        values = ({
                'record_name': msg_dict.get('subject'),
                'model': author_id._name,
                'res_id': author_id.id,
                'body': msg_dict.get('body'),
                'subject': msg_dict.get('subject'),
                'email_from': msg_dict.get('email_from'),
                'author_id': author_id.id,
                'message_id': msg_dict.get('message_id'),
                'email_cc_ids': [(6, 0, partner_id.ids)] if partner_id else False,
                'message_label': 'sent',
                'message_type': 'email',
            })
        attachments = msg_dict.get('attachments') or []
        attachement_values = self._message_post_process_attachments(attachments, [], values)
        values.update(attachement_values)
        m = self._message_create(values)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        kwargs.update({'email_cc_ids': [(6, 0, kwargs.get('email_cc_ids'))] if kwargs.get('email_cc_ids') else False,
                       'email_bcc_ids': [(6, 0, kwargs.get('email_bcc_ids'))] if kwargs.get('email_bcc_ids') else False})
        

        return super(MailThread, self).message_post(**kwargs)


    def _notify_thread_by_email(self, message, recipients_data, msg_vals=False,
                                mail_auto_delete=True,  # mail.mail
                                model_description=False, force_email_company=False, force_email_lang=False,  # rendering
                                resend_existing=False, force_send=True, send_after_commit=True,  # email send
                                subtitles=None, **kwargs):
        """ Method to send email linked to notified messages.

        :param message: ``mail.message`` record to notify;
        :param recipients_data: list of recipients information (based on res.partner
          records), formatted like
            [{'active': partner.active;
              'id': id of the res.partner being recipient to notify;
              'groups': res.group IDs if linked to a user;
              'notif': 'inbox', 'email', 'sms' (SMS App);
              'share': partner.partner_share;
              'type': 'customer', 'portal', 'user;'
             }, {...}].
          See ``MailThread._notify_get_recipients``;
        :param msg_vals: dictionary of values used to create the message. If given it
          may be used to access values related to ``message`` without accessing it
          directly. It lessens query count in some optimized use cases by avoiding
          access message content in db;

        :param mail_auto_delete: delete notification emails once sent;

        :param model_description: model description used in email notification process
          (computed if not given);
        :param force_email_company: see ``_notify_by_email_prepare_rendering_context``;
        :param force_email_lang: see ``_notify_by_email_prepare_rendering_context``;

        :param resend_existing: check for existing notifications to update based on
          mailed recipient, otherwise create new notifications;
        :param force_send: send emails directly instead of using queue;
        :param send_after_commit: if force_send, tells whether to send emails after
          the transaction has been committed using a post-commit hook;
        :param subtitles: optional list that will be set as template value "subtitles"
        """
        partners_data = [r for r in recipients_data if r['notif'] == 'email']
        if not partners_data:
            return True

        model = msg_vals.get('model') if msg_vals else message.model
        model_name = model_description or (self.env['ir.model']._get(model).display_name if model else False) # one query for display name
        recipients_groups_data = self._notify_get_recipients_classify(partners_data, model_name, msg_vals=msg_vals)

        if not recipients_groups_data:
            return True
        force_send = self.env.context.get('mail_notify_force_send', force_send)

        template_values = self._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, model_description=model_description,
            force_email_company=force_email_company,
            force_email_lang=force_email_lang,
        ) # 10 queries
        if subtitles:
            template_values['subtitles'] = subtitles

        email_layout_xmlid = msg_vals.get('email_layout_xmlid') if msg_vals else message.email_layout_xmlid
        template_xmlid = email_layout_xmlid if email_layout_xmlid else 'mail.mail_notification_layout'
        base_mail_values = self._notify_by_email_get_base_mail_values(message, additional_values={'auto_delete': mail_auto_delete})
        headers = self._notify_by_email_get_headers()
        if headers:
            base_mail_values['headers'] = headers
        cc_email_list = message.email_cc_ids.mapped('email')
        bcc_email_list = message.email_bcc_ids.mapped('email')
        cc_bcc = {
            'email_cc': ",".join(cc_email_list),
            'email_bcc': ",".join(bcc_email_list),
        }
        base_mail_values.update(cc_bcc)
        # Clean the context to get rid of residual default_* keys that could cause issues during
        # the mail.mail creation.
        # Example: 'default_state' would refer to the default state of a previously created record
        # from another model that in turns triggers an assignation notification that ends up here.
        # This will lead to a traceback when trying to create a mail.mail with this state value that
        # doesn't exist.
        SafeMail = self.env['mail.mail'].sudo().with_context(clean_context(self._context))
        SafeNotification = self.env['mail.notification'].sudo().with_context(clean_context(self._context))
        emails = self.env['mail.mail'].sudo()

        # loop on groups (customer, portal, user,  ... + model specific like group_sale_salesman)
        notif_create_values = []
        recipients_max = 50
        for recipients_group_data in recipients_groups_data:
            # generate notification email content
            recipients_ids = recipients_group_data.pop('recipients')
            render_values = {**template_values, **recipients_group_data}
            # {company, is_discussion, lang, message, model_description, record, record_name, signature, subtype, tracking_values, website_url}
            # {actions, button_access, has_button_access, recipients}

            mail_body = self.env['ir.qweb']._render(template_xmlid, render_values, minimal_qcontext=True, raise_if_not_found=False, lang=template_values['lang'])
            if not mail_body:
                _logger.warning('QWeb template %s not found or is empty when sending notification emails. Sending without layouting.', template_xmlid)
                mail_body = message.body
            mail_body = self.env['mail.render.mixin']._replace_local_links(mail_body)

            # create email
            for recipients_ids_chunk in split_every(recipients_max, recipients_ids):
                mail_values = self._notify_by_email_get_final_mail_values(
                    recipients_ids_chunk,
                    base_mail_values,
                    additional_values={'body_html': mail_body}
                )
                new_email = SafeMail.create(mail_values)

                if new_email and recipients_ids_chunk:
                    tocreate_recipient_ids = list(recipients_ids_chunk)
                    if resend_existing:
                        existing_notifications = self.env['mail.notification'].sudo().search([
                            ('mail_message_id', '=', message.id),
                            ('notification_type', '=', 'email'),
                            ('res_partner_id', 'in', tocreate_recipient_ids)
                        ])
                        if existing_notifications:
                            tocreate_recipient_ids = [rid for rid in recipients_ids_chunk if rid not in existing_notifications.mapped('res_partner_id.id')]
                            existing_notifications.write({
                                'notification_status': 'ready',
                                'mail_mail_id': new_email.id,
                            })
                    notif_create_values += [{
                        'author_id': message.author_id.id,
                        'mail_message_id': message.id,
                        'res_partner_id': recipient_id,
                        'notification_type': 'email',
                        'mail_mail_id': new_email.id,
                        'is_read': True,  # discard Inbox notification
                        'notification_status': 'ready',
                    } for recipient_id in tocreate_recipient_ids]
                emails += new_email

        if notif_create_values:
            SafeNotification.create(notif_create_values)

        # NOTE:
        #   1. for more than 50 followers, use the queue system
        #   2. do not send emails immediately if the registry is not loaded,
        #      to prevent sending email during a simple update of the database
        #      using the command-line.
        test_mode = getattr(threading.current_thread(), 'testing', False)
        if force_send and len(emails) < recipients_max and (not self.pool._init or test_mode):
            # unless asked specifically, send emails after the transaction to
            # avoid side effects due to emails being sent while the transaction fails
            if not test_mode and send_after_commit:
                email_ids = emails.ids
                dbname = self.env.cr.dbname
                _context = self._context

                @self.env.cr.postcommit.add
                def send_notifications():
                    db_registry = registry(dbname)
                    with db_registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, _context)
                        env['mail.mail'].browse(email_ids).send()
            else:
                emails.send()

        return True
