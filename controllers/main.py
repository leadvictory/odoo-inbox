# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

import base64
import logging
import json
import werkzeug
from datetime import datetime, timedelta
from odoo.addons.portal.controllers.portal import pager
from odoo import http, tools, models
from odoo import http, fields
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import AccessError
import email
from datetime import datetime, timedelta, timezone
import base64
import imapclient
from email.message import EmailMessage
import re
import email.policy
import imaplib
from imapclient import IMAPClient
from email.message import EmailMessage
from email.utils import make_msgid, formatdate

_logger = logging.getLogger(__name__)


class WebsiteOdooInbox(http.Controller):

    _message_per_page = 20

    def pager(self, url, total, page=1, step=30, scope=5, url_args=None):
        return pager(url, total, page=page, step=step, scope=scope, url_args=url_args)

    def get_message_counter_domain(self, model_object, domain):
        query = model_object._where_calc(domain)
        from_clause, where_clause, where_clause_params = query.get_sql()
        where_str = where_clause and (" WHERE %s" % where_clause) or ''
        query_str = 'SELECT "%s".id FROM ' % 'mail_message' + from_clause + where_str
        request._cr.execute(query_str, where_clause_params)
        message_ids = request._cr.fetchall()
        message_ids = message_ids and [x[0] for x in message_ids] or []
        return message_ids

    def _render_odoo_message(
            self, domain=None, link='/mail', page=1, label=None, color='bluecolor',
            search=None, existing_tag=None, existing_folder=None,
            partner=None, index=0, start=None, end=None, size_filter=None):

        if domain is None:
            domain = []

        if not label:
            label = 'inbox'

        MailMessage = request.env['mail.message'].sudo()
        MailThread = request.env['mail.thread']

        user = request.env.user
        messages = []
        unread_count = 0
        counter_domain = []

        partner_id = partner if partner else user.partner_id

        if partner_id and label not in ('sent', 'trash'):
            domain += [('partner_ids', 'in', partner_id.ids)]

        if label == 'trash':
            domain += [('author_id', '=', partner_id.id)]

        counter_domain += ['|', '|',
            ('partner_ids', 'in', partner_id.ids),
            ('notified_partner_ids', 'in', partner_id.ids),
            ('starred_partner_ids', 'in', partner_id.ids)
        ]

        # ------------------------------------------------
        # IMAP connection (IMAPClient)
        # ------------------------------------------------

        fetchmail_server = request.env['fetchmail.server'].search([
            ('user_id', '=', user.id),
            ('server_type', '=', 'imap')
        ])

        if not fetchmail_server:
            return request.not_found()

        if index >= len(fetchmail_server):
            index = 0

        server = fetchmail_server[index]

        try:
            imap_server = IMAPClient(
                server.server,
                port=server.port or 993,
                ssl=server.is_ssl
            )

            imap_server.login(server.user, server.password)

        except Exception as e:
            _logger.error("IMAP connection failed: %s", e)
            return request.make_response("<h3>IMAP connection failed</h3>")

        _logger.warning(
            "IMAP DEBUG → host=%s port=%s user=%s",
            server.server,
            server.port,
            server.user
        )

        # ------------------------------------------------
        # Select mailbox
        # ------------------------------------------------

        if label.lower() == "inbox":
            mailbox = "INBOX"
        elif label.lower() == "sent":
            mailbox = "Sent"
        elif label.lower() == "trash":
            mailbox = "Trash"
        else:
            mailbox = label

        try:
            imap_server.select_folder(mailbox)
        except Exception as e:
            _logger.error("Cannot open mailbox: %s", e)
            return request.make_response("<h3>Cannot open mailbox</h3>")

        # ------------------------------------------------
        # Search messages
        # ------------------------------------------------

        search_criteria = ['ALL']

        if search:
            search_criteria = ['TEXT', search]

        if start:
            d = datetime.strptime(start, "%Y-%m-%d")
            search_criteria += ['SINCE', d]

        if end:
            d = datetime.strptime(end, "%Y-%m-%d")
            search_criteria += ['BEFORE', d]

        try:
            message_ids = imap_server.sort(['REVERSE DATE'], search_criteria)
        except Exception as e:
            _logger.error("Search failed: %s", e)
            return request.make_response("<h3>Search failed</h3>")

        # message_ids.reverse()

        total_count = len(message_ids)

        start_i = self._message_per_page * (page - 1)
        end_i = self._message_per_page * page

        page_ids = message_ids[start_i:end_i]

        # ------------------------------------------------
        # Fetch messages (batch fetch = faster)
        # ------------------------------------------------

        try:
            response = imap_server.fetch(page_ids, ['RFC822', 'FLAGS'])
        except Exception as e:
            _logger.error("Fetch failed: %s", e)
            response = {}

        for uid in page_ids:

            data = response.get(uid)
            if not data:
                continue

            raw_msg = data[b'RFC822']

            try:
                msg = email.message_from_bytes(raw_msg, policy=email.policy.SMTP)

                msg_dict = MailThread.message_parse(msg)

                flags = data[b'FLAGS']

                msg_dict['is_read'] = b'\\Seen' in flags

                if not msg_dict['is_read']:
                    unread_count += 1

                messages.append(msg_dict)

            except Exception as e:
                _logger.warning("Email parse failed: %s", e)
        # messages.sort(key=lambda x: x.get('date') or datetime.min, reverse=True)
        # ------------------------------------------------
        # Folder loading (IMAPClient)
        # ------------------------------------------------

        folder_tree = {}
        counter_fd_msgs = {}

        folders = imap_server.list_folders()

        def insert_folder(path):

            parts = path.split('/')
            node = folder_tree

            for p in parts:
                node = node.setdefault(p, {})

        seen_short = set()

        for flags, delim, name in folders:

            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")

            if isinstance(delim, bytes):
                delim = delim.decode("utf-8", errors="ignore")

            short = name.split(delim)[-1].lower()

            if short in seen_short and not name.startswith("INBOX"):
                continue

            seen_short.add(short)

            insert_folder(name)

            counter_fd_msgs[name] = "0"

        # ------------------------------------------------
        # Convert folder tree
        # ------------------------------------------------

        def flatten_tree(tree, parent=None):

            result = []

            for name, children in sorted(tree.items()):

                full = f"{parent}/{name}" if parent else name

                result.append({
                    "name": name,
                    "id": full,
                    "children": flatten_tree(children, full)
                })

            return result

        folder_ids = flatten_tree(folder_tree)

        # ------------------------------------------------
        # Counters
        # ------------------------------------------------

        tag_ids = request.env['message.tag'].sudo().search([
            ('user_id', '=', user.id)
        ])

        starred_domain = counter_domain + [('message_label', '=', 'starred')]
        starred_mssg_count = len(self.get_message_counter_domain(MailMessage, starred_domain))

        snoozed_domain = counter_domain + [('message_label', '=', 'snoozed')]
        snoozed_mssg_count = len(self.get_message_counter_domain(MailMessage, snoozed_domain))

        total = total_count

        url_args = {
            'search': search or '',
            'start': start or '',
            'end': end or '',
            'size': size_filter or ''
        }

        pager = self.pager(
            url=link,
            total=total,
            page=page,
            step=self._message_per_page,
            url_args=url_args
        )

        document_models = request.env['ir.model'].sudo().search([
            ('is_mail_thread', '=', True)
        ])

        imap_server.logout()

        # ------------------------------------------------
        # Render
        # ------------------------------------------------

        return request.render('odoo_inbox.inbox', {

            'messages': messages,
            'pager': pager,
            'total': total,
            'label': label,
            'color': color,
            'search': search,

            'current_partner': partner if partner else request.env.user.partner_id,
            'user_child_partner_ids': request.env.user.child_partner_ids,

            'tag_ids': tag_ids,
            'existing_tag': existing_tag,
            'folder_ids': folder_ids,
            'existing_folder': existing_folder,
            'counter_fd_msgs': counter_fd_msgs,

            'document_models': document_models,
            'default_inbox_pane_type': request.env.user.inbox_default_pane_view_type,

            'index': index,
            'servers': fetchmail_server,
            'link': link,
            'unread_count': unread_count,

            'start': start,
            'end': end,
            'size': size_filter
        })
            
    @http.route(['/mail/<int:index>/message_read'], type='json', auth="user", website=True)
    def odoo_message_read(self, index, **kw):

        message_id = kw.get('message')

        fetchmail_server = request.env['fetchmail.server'].search([
            ('user_id', '=', request.env.user.id),
            ('server_type', '=', 'imap')
        ])

        server = fetchmail_server[index]

        try:
            imap_server = IMAPClient(
                server.server,
                port=server.port or 993,
                ssl=server.is_ssl
            )

            imap_server.login(server.user, server.password)

        except Exception as e:
            _logger.error("IMAP connection failed: %s", e)
            return {'error': True}

        found = False

        MailThread = request.env['mail.thread']

        folders = imap_server.list_folders()

        visited = set()

        for flags, delim, name in folders:

            # ensure str (some servers return bytes)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")

            if isinstance(delim, bytes):
                delim = delim.decode("utf-8", errors="ignore")

            short = name.split(delim)[-1].lower()

            if short in visited and not name.startswith("INBOX"):
                continue

            visited.add(short)

            _logger.info(f"Checking folder: {name}")

            try:
                imap_server.select_folder(name)
            except Exception as e:
                _logger.warning(f"Cannot select folder {name}: {e}")
                continue

            try:
                msg_ids = imap_server.search(['HEADER', 'Message-ID', message_id])
            except Exception:
                msg_ids = []

            if not msg_ids:
                continue

            found = True

            response = imap_server.fetch(msg_ids, ['RFC822', 'FLAGS'])

            for uid, data in response.items():

                raw_msg = data[b'RFC822']

                imap_server.add_flags(uid, ['\\Seen'])

                message = email.message_from_bytes(raw_msg, policy=email.policy.SMTP)

                msg_dict = MailThread.message_parse(message)

                attachments = []

                for att in msg_dict['attachments']:

                    context = dict(request.env.context)
                    context['image_no_postprocess'] = True

                    try:

                        if hasattr(att.content, "get_payload"):
                            content_bytes = att.content.get_payload(decode=True)

                        elif isinstance(att.content, str):
                            content_bytes = att.content.encode()

                        else:
                            content_bytes = att.content

                        encoded_data = base64.b64encode(content_bytes)

                        attachment = request.env['ir.attachment'].with_context(context).create({
                            'name': att.fname,
                            'type': 'binary',
                            'datas': encoded_data,
                            'res_model': 'mail.message',
                            'public': True,
                        })

                        attachments.append(attachment)

                    except Exception as e:
                        _logger.error(f"Attachment save error: {e}")

                msg_dict['attachments'] = attachments

                mail_time = fields.Datetime.from_string(msg_dict['date'])

                message_body = request.env['ir.ui.view']._render_template(
                    "odoo_inbox.inbox_message_detail",
                    {
                        'mail': msg_dict,
                        'index': index,
                        'mail_time': mail_time
                    }
                )

                imap_server.logout()

                return {
                    'msg_unread': True,
                    'inbox_mssg_count': 0,
                    'starred_mssg_count': 0,
                    'snoozed_mssg_count': 0,
                    'folder_mssg_count': 0,
                    'counter_fd_msgs': {},
                    'message_body': message_body,
                    'index': index
                }

        imap_server.logout()

        if not found:

            return {
                'error': True,
                'message_body': "<div style='padding:20px;color:red;'>Message not found. It may have been moved or deleted.</div>",
                'index': index
            }

            
    @http.route(['/mail/all_mssg_unread'], type='json', auth="user", website=True)
    def odoo_all_message_unread(self, messg_ids, **kw):
        for mssg in messg_ids:
            message = request.env['mail.message'].sudo().browse(int(mssg))
            message.msg_unread = False
        return True

    @http.route(['/mail/all_mssg_read'], type='json', auth="user", website=True)
    def odoo_all_message_read(self, messg_ids, **kw):
        for mssg in messg_ids:
            message = request.env['mail.message'].sudo().browse(int(mssg))
            message.msg_unread = True
        return True

    @http.route(['/mail/<int:index>/inbox',
                 '/mail/<int:index>/inbox/page/<int:page>',
                 '/mail/<int:index>/inbox/search_message'
                 ], type='http', auth="user", website=True)
    def odoo_inbox(self, index=0, page=1, **kw):
        search = None
        start = None
        end = None
        size_filter = None
        if kw.get('from'):
            start = kw.get('from')
        if kw.get('to'):
            end = kw.get('to')
        if kw.get('size'):
            size_filter = kw.get('size')
        if kw.get('search'):
            domain = ['|', '|', '|',
                      ('subject', 'ilike', kw.get('search')),
                      ('email_from', 'ilike', kw.get('search')),
                      ('body', 'ilike', kw.get('search')),
                      ('tag_ids.name', 'ilike', kw.get('search'))]
            search = kw.get('search')
        else:
            domain = [('message_label', 'in', ['starred', 'inbox'])]
        return self._render_odoo_message(
            domain, '/mail/'+str(index)+'/inbox', page, search=search, color='bluecolor', index=index, start=start, end=end, size_filter=size_filter)

    @http.route(['/mail/<int:index>/message_post'], type='http', auth="user", website=True)
    def message_post_send(self, index=0, **post):

        subject = (post.get('subject') or '').strip()
        body = (post.get('body') or '').strip()
        email_to_raw = (post.get('email') or '').strip()

        if not subject or not body:
            return request.redirect(f'/mail/{index}/inbox')

        # ------------------------------------------------------
        # Clean email format
        # ------------------------------------------------------
        if "<" in email_to_raw and ">" in email_to_raw:
            try:
                email_to_raw = email_to_raw.split("<")[1].replace(">", "").strip()
            except Exception:
                pass

        # ------------------------------------------------------
        # Ensure main partner exists
        # ------------------------------------------------------
        partner_ids = []

        if email_to_raw:
            partner = request.env['res.partner'].sudo().search(
                [('email', 'ilike', email_to_raw)],
                limit=1
            )

            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'email': email_to_raw,
                    'name': email_to_raw,
                    'lang': 'de_DE'
                })

            if partner.id > 0:
                partner_ids.append(partner.id)

        # ------------------------------------------------------
        # Extra recipients (safe)
        # ------------------------------------------------------
        extra_partners = request.httprequest.form.getlist('partners')

        for p in extra_partners:
            try:
                pid = int(p)
                if pid > 0:
                    partner_ids.append(pid)
            except Exception:
                if p:
                    new_partner = request.env['res.partner'].sudo().create({
                        'email': p,
                        'name': p,
                        'lang': 'de_DE'
                    })
                    partner_ids.append(new_partner.id)

        # Remove invalid / duplicates
        partner_ids = list(set(pid for pid in partner_ids if pid > 0))
        partner_ids = request.env['res.partner'].sudo().browse(partner_ids).exists().ids

        # ------------------------------------------------------
        # Attachments (safe multi-upload)
        # ------------------------------------------------------
        attachment_ids = []
        files = request.httprequest.files.getlist('compose_attachments[]')

        for f in files:
            if f and f.filename:
                try:
                    data = base64.b64encode(f.read())
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': f.filename,
                        'datas': data,
                        'res_model': 'res.partner',
                        'res_id': request.env.user.partner_id.id,
                        'mimetype': f.content_type,
                    })
                    attachment_ids.append(attachment.id)
                except Exception as e:
                    _logger.error(f"Attachment error: {e}")

        # ------------------------------------------------------
        # CC / BCC (safe)
        # ------------------------------------------------------
        def safe_partner_ids(raw_list):
            ids = []
            for item in raw_list:
                try:
                    pid = int(item)
                    if pid > 0:
                        ids.append(pid)
                except:
                    pass
            return request.env['res.partner'].sudo().browse(ids).exists().ids

        cc_ids = safe_partner_ids(request.httprequest.form.getlist('cc_partners'))
        bcc_ids = safe_partner_ids(request.httprequest.form.getlist('bcc_partners'))
        _logger.warning(f"1FINAL partner_ids: {partner_ids}")
        _logger.warning(f"FINAL cc_ids: {cc_ids}")
        _logger.warning(f"FINAL bcc_ids: {bcc_ids}")



        # ------------------------------------------------------
        # Get outgoing server safely
        # ------------------------------------------------------
        fetchmail_servers = request.env['fetchmail.server'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('server_type', '=', 'imap')
        ])

        server = fetchmail_servers[index] if len(fetchmail_servers) > index else False

        email_from = request.env.user.email
        reply_to = request.env.user.email

        if server:
            email_from = f"{server.name} <{server.user}>"
            reply_to = email_from

        # ------------------------------------------------------
        # Log internally
        # ------------------------------------------------------
        request.env.user.partner_id.sudo().message_post(
            body=body,
            subject=subject,
            attachment_ids=attachment_ids,
        )

        # ------------------------------------------------------
        # Send actual SMTP email
        # ------------------------------------------------------
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': ','.join(
                request.env['res.partner'].browse(partner_ids).mapped('email')
            ),
            'email_from': email_from,
            'reply_to': reply_to,
            'attachment_ids': [(6, 0, attachment_ids)],
        }

        if cc_ids:
            _logger.warning(f"CC id::{cc_ids}")
            mail_values['email_cc'] = ','.join(
                request.env['res.partner'].browse(cc_ids).mapped('email')
            )

        if bcc_ids:
            mail_values['email_bcc'] = ','.join(
                request.env['res.partner'].browse(bcc_ids).mapped('email')
            )

        mail = request.env['mail.mail'].sudo().create(mail_values)
        _logger.warning(f"Mail Value::{mail_values}")
        mail.send()
        try:

            imap_server = server.connect()

            msg = EmailMessage()
            msg['Message-ID'] = make_msgid()
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = subject
            msg['From'] = email_from
            msg['To'] = mail_values['email_to']

            if mail_values.get('email_cc'):
                msg['Cc'] = mail_values['email_cc']

            msg.set_content("This email requires HTML support")
            msg.add_alternative(body, subtype="html")

            raw_message = msg.as_bytes()

            sent_folders = ["Sent", "INBOX/Sent", "Sent Items"]

            for folder in sent_folders:
                try:
                    imap_server.append(folder, ['\\Seen'], datetime.now(timezone.utc), raw_message)
                    break
                except:
                    continue

        except Exception as e:
            _logger.warning(f"Could not save message to Sent folder: {e}")
        return request.redirect(f'/mail/{index}/inbox')

    @http.route(['/'], type='http', auth="user", website=True)
    def redirect_inbox(self):
        return request.redirect('/mail/0/inbox')

    @http.route(['/sent_mail/<int:index>/mail'], type='http', auth="user", website=True)
    def mail_send(self, index=0, **post):

        subject = (post.get('subject') or '').strip()
        body = (post.get('body') or '').strip()

        if not subject or not body:
            return request.redirect(f'/mail/{index}/inbox')

        # --------------------------------------------------
        # Partner handling
        # --------------------------------------------------
        raw_partners = request.httprequest.form.getlist('partners')
        partner_ids = []

        for p in raw_partners:
            try:
                pid = int(p)
                if pid > 0:
                    partner_ids.append(pid)
            except:
                if p:
                    new_partner = request.env['res.partner'].sudo().create({
                        'email': p,
                        'name': p,
                        'lang': 'de_DE'
                    })
                    partner_ids.append(new_partner.id)

        partner_ids = list(set(pid for pid in partner_ids if pid > 0))
        partner_ids = request.env['res.partner'].sudo().browse(partner_ids).exists().ids

        # --------------------------------------------------
        # CC / BCC
        # --------------------------------------------------
        def safe_ids(raw_list):
            ids = []
            for item in raw_list:
                try:
                    pid = int(item)
                    if pid > 0:
                        ids.append(pid)
                except:
                    pass
            return request.env['res.partner'].sudo().browse(ids).exists().ids

        cc_ids = safe_ids(request.httprequest.form.getlist('cc_partners'))
        bcc_ids = safe_ids(request.httprequest.form.getlist('bcc_partners'))

        # --------------------------------------------------
        # Attachments
        # --------------------------------------------------
        attachment_ids = []
        files = request.httprequest.files.getlist('compose_attachments[]')

        for f in files:
            if f and f.filename:
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': f.filename,
                    'datas': base64.b64encode(f.read()),
                    'res_model': 'res.partner',
                    'res_id': request.env.user.partner_id.id,
                    'mimetype': f.content_type,
                })
                attachment_ids.append(attachment.id)

        # --------------------------------------------------
        # Server config
        # --------------------------------------------------
        fetchmail_servers = request.env['fetchmail.server'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('server_type', '=', 'imap')
        ])

        server = fetchmail_servers[index] if len(fetchmail_servers) > index else False

        email_from = request.env.user.email
        reply_to = request.env.user.email

        if server:
            email_from = f"{server.name} <{server.user}>"
            reply_to = email_from

        # --------------------------------------------------
        # Send email via Odoo
        # --------------------------------------------------
        message = request.env.user.partner_id.message_post(
            body=body,
            subject=subject,
            email_from=email_from,
            reply_to=reply_to,
            author_id=request.env.user.partner_id.id,
            attachment_ids=attachment_ids,
            partner_ids=partner_ids,
            message_type='email',
            subtype_id=request.env.ref('mail.mt_comment').id,
        )

        message.write({'msg_unread': False})

        # --------------------------------------------------
        # Save email to IMAP Sent folder (IMAPClient)
        # --------------------------------------------------
        try:
            if server:

                from imapclient import IMAPClient
                from email.message import EmailMessage
                from email.utils import make_msgid, formatdate
                from datetime import datetime, timezone

                imap_server = IMAPClient(
                    server.server,
                    port=server.port or 993,
                    ssl=server.is_ssl
                )

                imap_server.login(server.user, server.password)

                # --------------------------------
                # Detect Sent folder automatically
                # --------------------------------
                sent_folder = None

                folders = imap_server.list_folders()

                for flags, delim, name in folders:
                    if b'\\Sent' in flags:
                        sent_folder = name
                        break

                if not sent_folder:
                    sent_folder = "Sent"

                # --------------------------------
                # Build RFC email
                # --------------------------------
                msg = EmailMessage()

                msg['Message-ID'] = make_msgid()
                msg['Date'] = formatdate(localtime=True)
                msg['Subject'] = subject
                msg['From'] = email_from

                to_emails = request.env['res.partner'].browse(partner_ids).mapped('email')
                msg['To'] = ", ".join(to_emails)

                if cc_ids:
                    cc_emails = request.env['res.partner'].browse(cc_ids).mapped('email')
                    msg['Cc'] = ", ".join(cc_emails)

                msg.set_content("Plain text fallback")
                msg.add_alternative(body, subtype="html")

                # Attachments
                for attachment_id in attachment_ids:
                    attachment = request.env['ir.attachment'].sudo().browse(attachment_id)

                    msg.add_attachment(
                        base64.b64decode(attachment.datas),
                        maintype='application',
                        subtype='octet-stream',
                        filename=attachment.name
                    )

                raw_message = msg.as_bytes()

                # --------------------------------
                # Append message to Sent folder
                # --------------------------------
                imap_server.append(
                    sent_folder,
                    raw_message,
                    flags=['\\Seen'],
                    msg_time=datetime.now(timezone.utc)
                )

                _logger.warning(f"Saved email to IMAP Sent folder: {sent_folder}")

                imap_server.logout()

        except Exception as e:
            _logger.warning(f"Could not save email to Sent folder: {e}")

        return request.redirect(f'/mail/{index}/inbox')

    @http.route(['/mail/send/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def odoo_move_send(self, message=None, **post):
        message = request.env['odoo.inbox'].move_to_send(message)
        return request.redirect('/mail/send')

    @http.route(['/mail/send',
                 '/mail/send/page/<int:page>'
                 ], type='http', auth="user", website=True)
    def odoo_send(self, page=1, **kw):
        domain = [('author_id', '=', request.env.user.partner_id.id), ('message_type', 'in', ['email', 'comment']), ('message_label', '!=', 'trash')]
        return self._render_odoo_message(domain, '/mail/send', page, 'sent', 'sentcolor')

    @http.route(['/mail/filter/partner/<int:partner_id>'], type="http", auth="user", website=True)
    def mail_filter_partner(self, page=1, **kw):
        partner = request.env['res.partner'].sudo().browse(int(kw.get('partner_id')))
        domain = []
        if kw.get('search'):
            domain = ['|', '|', '|',
                      ('subject', 'ilike', kw.get('search')),
                      ('email_from', 'ilike', kw.get('search')),
                      ('body', 'ilike', kw.get('search')),
                      ('tag_ids.name', 'ilike', kw.get('search'))]
            search = kw.get('search')
        else:
            domain = [('message_label', 'in', ['starred', 'inbox'])]

        return self._render_odoo_message(domain, '/mail/inbox', page, 'filter', 'bluecolor', partner=partner)

    @http.route(['/mail/starred/message',
                 ], type='json', auth="user", website=True)
    def message_starred(self, **kw):
        message = request.env['mail.message'].sudo().browse(kw.get('message'))
        if kw.get('action') == 'add':
            message.starred_partner_ids = [(4, request.env.user.partner_id.id)]
            request.env['odoo.inbox'].set_star(kw.get('action'), message)
        if kw.get('action') == 'remove':
            message.starred_partner_ids = [(3, request.env.user.partner_id.id)]
            request.env['odoo.inbox'].set_star(kw.get('action'), message)

    @http.route('/mail/all_mssg_starred', type="json", auth="user", website=True)
    def odoo_all_mssg_starred(self, messg_ids, **kw):
        for mssg in messg_ids:
            message = request.env['mail.message'].sudo().browse(int(mssg))
            if kw.get('action') == 'add':
                message.starred_partner_ids = [(4, request.env.user.partner_id.id)]
                request.env['odoo.inbox'].set_star(kw.get('action'), message)
        return True

    @http.route('/mail/all_mssg_unstarred', type="json", auth="user", website=True)
    def odoo_all_mssg_unstarred(self, messg_ids, **kw):
        for mssg in messg_ids:
            message = request.env['mail.message'].sudo().browse(int(mssg))
            if kw.get('action') == 'remove':
                message.starred_partner_ids = [(3, request.env.user.partner_id.id)]
                request.env['odoo.inbox'].set_star(kw.get('action'), message)
        return True

    @http.route(['/mail/starred',
                 '/mail/starred/page/<int:page>'
                 ], type='http', auth="user", website=True)
    def odoo_starred(self, page=1, **kw):
        domain = [('message_label', '=', 'starred')]
        return self._render_odoo_message(domain, '/mail/starred', page, 'starred', 'starredcolor')

    @http.route(['/mail/starred_move_to_inbox/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def starred_move_to_inbox(self, message=None, **kw):
        message.message_label = 'inbox'
        return request.redirect('/mail/starred')

    @http.route(['/mail/snoozed',
                 '/mail/snoozed/page/<int:page>'
                 ], type='http', auth="user", website=True)
    def odoo_snoozed(self, page=1, **kw):
        domain = [('message_label', '=', 'snoozed')]
        return self._render_odoo_message(domain, '/mail/snoozed', page, 'snoozed', 'snoozedcolor')

    @http.route(['/mail/snoozed/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def set_snoozed(self, message=None, your_time=None, **post):
        message.message_label = 'snoozed'
        your_time = str(your_time)
        if your_time == 'today':
            message.snoozed_time = datetime.now() + timedelta(hours=2)
        elif your_time == 'tomorrow':
            message.snoozed_time = datetime.now() + timedelta(days=1)
        elif your_time == 'nexweek':
            message.snoozed_time = datetime.now() + timedelta(days=7)
        if post.get('date'):
            message.snoozed_time = datetime.strptime(str(post.get('date')), "%m/%d/%Y %I:%M %p").strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return request.redirect('/mail/inbox')

    @http.route(['/mail/all_mssg_snoozed',
                 ], type='json', auth="user", website=True)
    def all_set_snoozed(self, mssg_snooze=None, your_time=None, **post):
        for mssg in mssg_snooze:
            message_id = request.env['mail.message'].sudo().browse(int(mssg))
            message_id.message_label = 'snoozed'
            if your_time == 'today':
                message_id.snoozed_time = datetime.now() + timedelta(hours=2)
            elif your_time == 'tomorrow':
                message_id.snoozed_time = datetime.now() + timedelta(days=1)
            elif your_time == 'nexweek':
                message_id.snoozed_time = datetime.now() + timedelta(days=7)
            # if snooze_date:
            #     message_id.snoozed_time = datetime.strptime(snooze_date, "%m/%d/%Y %I:%M %p").strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return True

    @http.route(['/mail/all_mssg_snoozed_submit',
                 ], type='json', auth="user", website=True)
    def all_set_snoozed_submit(self, mssg_snooze=None, snooze_date=None, **post):
        for mssg in mssg_snooze:
            message_id = request.env['mail.message'].sudo().browse(int(mssg))
            message_id.message_label = 'snoozed'
            if snooze_date:
                message_id.snoozed_time = datetime.strptime(snooze_date, "%m/%d/%Y %I:%M %p").strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return True

    @http.route(['/mail/set_done/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def message_done(self, message=None, **kw):
        request.env['odoo.inbox'].set_done(message)
        return request.redirect('/mail/inbox')

    @http.route(['/mail/done',
                 '/mail/done/page/<int:page>'
                 ], type='http', auth="user", website=True)
    def mail_done(self, page=1, **kw):
        domain = [('message_label', '=', 'done')]
        return self._render_odoo_message(domain, '/mail/done', page, 'done', 'donecolor')

    @http.route(['/mail/move_to_inbox/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def move_to_inbox(self, message=None, **kw):
        message.message_label = 'inbox'
        return request.redirect('/mail/inbox')

    @http.route([
        '/mail/move_to_trash/<model("mail.message"):message>',
    ], type='http', auth="user", website=True)
    def odoo_move_trash(self, message=None, **post):
        request.env['odoo.inbox'].move_to_trash(message)
        return request.redirect('/mail/inbox')

    @http.route(['/mail/trash',
                 '/mail/trash/page/<int:page>'
                 ], type='http', auth="user", website=True)
    def odoo_trash(self, page=1, **kw):
        domain = [('message_label', '=', 'trash')]
        return self._render_odoo_message(domain, '/mail/trash', page, 'trash', 'trashcolor')

    @http.route(['/mail/delete_forever/<model("mail.message"):message>',
                 ], type='http', auth="user", website=True)
    def delete_forever(self, message=None, **kw):
        message.sudo().unlink()
        return request.redirect('/mail/trash')

    def odoo_all_mssg_trash(self, index=0, messg_ids=[], **post):

        from imapclient import IMAPClient

        fetchmail_server = request.env['fetchmail.server'].search([
            ('user_id', '=', request.env.user.id),
            ('server_type', '=', 'imap')
        ])

        if not fetchmail_server:
            return False

        server = fetchmail_server[index]

        try:
            imap_server = IMAPClient(
                server.server,
                port=server.port or 993,
                ssl=server.is_ssl
            )

            imap_server.login(server.user, server.password)

        except Exception as e:
            _logger.error(f"IMAP connection failed: {e}")
            return False


        folders = imap_server.list_folders()

        trash_folder = None

        # ------------------------------------------------
        # Detect trash folder (supports German / Outlook / Gmail)
        # ------------------------------------------------

        for flags, delim, name in folders:

            if isinstance(name, bytes):
                name = name.decode()

            lower = name.lower()

            if (
                'trash' in lower
                or 'gelöscht' in lower
                or 'geloscht' in lower
                or 'deleted' in lower
            ):
                trash_folder = name
                break

        if not trash_folder:
            _logger.error("Trash folder not found")
            imap_server.logout()
            return False


        # ------------------------------------------------
        # Scan folders for messages
        # ------------------------------------------------

        for flags, delim, name in folders:

            if isinstance(name, bytes):
                name = name.decode()

            try:
                imap_server.select_folder(name)

            except Exception as e:
                _logger.warning(f"Cannot open folder {name}: {e}")
                continue

            for mssg in messg_ids:

                try:
                    msg_ids = imap_server.search(['HEADER', 'Message-ID', mssg])
                except Exception:
                    msg_ids = []

                if not msg_ids:
                    continue

                try:

                    # Copy message to trash
                    imap_server.copy(msg_ids, trash_folder)

                    # Mark deleted
                    imap_server.delete_messages(msg_ids)

                    # Permanently remove
                    imap_server.expunge()

                except Exception as e:
                    _logger.error(f"Trash move failed: {e}")


        imap_server.logout()

        return True

    @http.route('/mail/all_mssg_done', type="json", auth="user", website=True)
    def odoo_all_mssg_done(self, messg_ids, **post):
        for mssg in messg_ids:
            message_id = request.env['mail.message'].sudo().browse(int(mssg))
            if message_id or message_id.folder_id:
                message_id.write({'message_label': 'done'
                                  })
        return True

    # @http.route('/mail/attachment/<model("ir.attachment"):attachment>/download', type='http', website=True)
    # def slide_download(self, attachment):
    #     filecontent = base64.b64decode(attachment.datas)
    #     main_type, sub_type = attachment.mimetype.split('/', 1)
    #     disposition = 'attachment; filename=%s.%s' % (werkzeug.urls.url_quote(attachment.name), sub_type)
    #     return request.make_response(
    #         filecontent,
    #         [('Content-Type', attachment.mimetype),
    #          ('Content-Length', len(filecontent)),
    #          ('Content-Disposition', disposition)])
    #     return request.render("website.403")

    @http.route(
        '/mail/attachment/<int:attachment_id>/download',
        type='http',
        auth='user',
        website=True
    )
    def download_attachment(self, attachment_id, **kw):
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)

        if not attachment.exists():
            return request.not_found()

        # Decode binary content
        filecontent = base64.b64decode(attachment.datas or b'')

        filename = attachment.name or "file"
        mimetype = attachment.mimetype or "application/octet-stream"

        return request.make_response(
            filecontent,
            headers=[
                ('Content-Type', mimetype),
                ('Content-Length', str(len(filecontent))),
                ('Content-Disposition', 'attachment; filename="%s"' % filename)
            ]
        )

    @http.route('/mail/partner_create', type="json", auth="user", website=True)
    def odoo_partner_create(self, email_address, **post):
        if email_address:
            partner_id = request.env['res.partner'].sudo().search([('name', '=', email_address.split('@')[0]), ('email', '=', email_address)])
            if not partner_id:
                partner_id = request.env['res.partner'].sudo().create({
                    'name': email_address.split('@')[0],
                    'email': email_address
                    })
            return {'success': True, 'partner_id': partner_id.id, 'partner_name': partner_id.name, 'email': partner_id.email}
        else:
            return {'error': 'email address is wrong'}
        
    @http.route('/mail/get_partner_from_category', type="json", auth="user", website=True)
    def odoo_partner_create(self, category_id, **post):
        if category_id:
            partner_ids = request.env['res.partner'].sudo().search([('category_id', 'in', category_id)])
            partners_list = []
            for partner in partner_ids:
                partners_list.append({
                    'id': partner.id,
                    'name': partner.name,
                    'email': partner.email,
                })
            return partners_list
        else:
            return {'error': 'email address is wrong'}

    @http.route('/mail/message_tag_assign', type="json", auth="user", website=True)
    def odoo_message_tag_assign(self, message_id, tag_ids=[], create_tag_input=None, **post):
        if message_id:
            message = request.env['mail.message'].sudo().browse(message_id)
            user_id = request.env.user
            if create_tag_input:
                new_tag_id = request.env['message.tag'].create({'name': create_tag_input,
                                                                'user_id': user_id.id})
                tag_ids += [new_tag_id.id]
            message.tag_ids = [(6, 0, tag_ids)]
            main_tag_ids = request.env['message.tag'].sudo().search([('user_id', '=', user_id.id)])
            message_tag_list_template = request.env['ir.ui.view']._render_template('odoo_inbox.message_tag_list', {'mail_message': message})
            message_tag_dropdown = request.env['ir.ui.view']._render_template('odoo_inbox.tag_dropdown', {'mail_message': message, 'tag_ids': main_tag_ids})
            return {'success': True, 'message_tag_list': message_tag_list_template, 'message_tag_dropdown': message_tag_dropdown}
        else:
            return {'error': 'Message is not find'}

    @http.route('/mail/message_tag_assign/all', type="json", auth="user", website=True)
    def odoo_message_tag_assign_all(self, message_id=[], tag_ids=[], create_tag_input=None, **post):
        if message_id:
            message_ids = request.env['mail.message'].sudo().browse(message_id)
            user_id = request.env.user
            if create_tag_input:
                new_tag_id = request.env['message.tag'].create({'name': create_tag_input,
                                                                'user_id': user_id.id})
                tag_ids += [new_tag_id.id]
            for message in message_ids:
                tttag_ids = list(set(tag_ids + message.tag_ids.ids))
                message.tag_ids = [(6, 0, tttag_ids)]
            return True
        else:
            return {'error': 'Message is not find'}

    @http.route('/mail/message_tag_delete', type="json", auth="user", website=True)
    def odoo_message_tag_delete(self, message_id, tag_id, **post):
        if message_id and tag_id:
            user_id = request.env.user
            message = request.env['mail.message'].sudo().browse(message_id)
            message.tag_ids = [(3, tag_id)]
            main_tag_ids = request.env['message.tag'].sudo().search([('user_id', '=', user_id.id)])
            message_tag_list_template = request.env['ir.ui.view']._render_template('odoo_inbox.message_tag_list', {'mail_message': message})
            message_tag_dropdown = request.env['ir.ui.view']._render_template('odoo_inbox.tag_dropdown', {'mail_message': message, 'tag_ids': main_tag_ids})
            return {'success': True, 'message_tag_list': message_tag_list_template, 'message_tag_dropdown': message_tag_dropdown}
        else:
            return {'success': False, 'error': 'Message is not find'}

    @http.route(['/mail/tag/<model("message.tag"):tag>',
                 '/mail/tag/<model("message.tag"):tag>/page/<int:page>'], type='http', auth="user", website=True)
    def odoo_tags(self, tag, page=1, **kw):
        domain = [('tag_ids', '=', tag.id)]
        return self._render_odoo_message(domain, '/mail/tag/' + str(tag.id), page, tag.name, 'bluecolor', existing_tag=tag.id)

    @http.route(['/mail/tag_edit'], type='http', auth="user", methods=['POST'], website=True)
    def odoo_tags_edit(self, **kw):
        if kw.get('tag_id') and kw.get('tag_name'):
            tag_id = request.env['message.tag'].sudo().browse(int(kw.get('tag_id')))
            tag_id.name = kw.get('tag_name')
        return request.redirect(request.httprequest.referrer or '/mail/inbox')

    @http.route(['/mail/tag_delete'], type='http', auth="user", methods=['POST'], website=True)
    def odoo_tags_delete(self, **kw):
        if kw.get('tag_id'):
            tag_id = request.env['message.tag'].sudo().browse(int(kw.get('tag_id')))
            tag_id.unlink()
        return request.redirect('/mail/inbox')

    @http.route(['/mail/<int:index>/folder/<model("message.folder"):folder>',
                 '/mail/<int:index>/folder/<model("message.folder"):folder>/page/<int:page>', '/mail/<int:index>/folder/<string:folder>', '/mail/<int:index>/folder/<string:folder>/page/<int:page>', '/mail/<int:index>/folder/<string:folder>/search_message'], type='http', auth="user", website=True)
    def odoo_folders(self, index=0, folder="", page=1, **kw):
        search = None
        start = None
        end = None
        size_filter = None
        if kw.get('search'):
            search = kw.get('search')
        if kw.get('from'):
            start = kw.get('from')
        if kw.get('to'):
            end = kw.get('to')
        if kw.get('size'):
            size = kw.get('size')
        domain = [('folder_id', '=', folder)]
        folder = { 'id': folder, 'name': folder }
        return self._render_odoo_message(domain, '/mail/'+str(index)+'/folder/' + str(folder['id']), page, folder['name'], 'bluecolor', existing_folder=folder, index=index, search=search, start=start, end=end, size_filter=size_filter)

    @http.route(['/mail/<int:index>/folder_edit'], type='http', auth="user", methods=['POST'], website=True)
    def odoo_folder_edit(self, index=0, **kw):
        old_raw = kw.get('folder_id')
        new_short = kw.get('folder_name')

        if not old_raw or not new_short:
            return request.redirect(request.httprequest.referrer or '/mail/inbox')

        # Build new full folder name
        parts = old_raw.split('.')
        parts[-1] = new_short
        full_new_name = '.'.join(parts)

        fetchmail_server = request.env['fetchmail.server'].search([
            ('user_id', '=', request.env.user.id),
            ('server_type', '=', 'imap')
        ])
        server = fetchmail_server[index]
        imap_server = server.connect()

        # Encode names for IMAP
        old_encoded = imapclient.imap_utf7.encode(old_raw)
        new_encoded = imapclient.imap_utf7.encode(full_new_name)

        # _logger.info(f"Renaming IMAP folder: {old_raw} → {full_new_name}")

        try:
            imap_server.rename(old_encoded, new_encoded)
            # _logger.info(f"Rename OK: {old_raw} → {full_new_name}")
        except Exception as e:
            _logger.error(f"IMAP rename failed: {e}")
            return request.redirect(request.httprequest.referrer)

        # 🔥 IMPORTANT: REFRESH IMAP LIST SO ODOO SEES THE NEW FOLDER
        imap_server.select("INBOX")
        imap_server.list()     # <--- REFRESH CACHE

        # 🔥 Update Odoo database folder record
        folder_rec = request.env['message.folder'].sudo().search([('name', '=', old_raw)], limit=1)
        if folder_rec:
            folder_rec.name = full_new_name

        # Redirect to correct URL
        new_url = f"/mail/{index}/folder/{full_new_name}"
        return request.redirect(new_url)



    @http.route(['/mail/<int:index>/folder_delete'], type='http', auth="user", methods=['POST'], website=True)
    def odoo_folder_delete(self, index=0, **kw):
        if kw.get('folder_id'):
            user_email = request.env.user.email
            fetchmail_server = request.env['fetchmail.server'].search([
                ('user_id', '=', request.env.user.id),
                ('server_type', '=', 'imap')
            ])
            server = fetchmail_server[index]
            imap_server = server.connect()
            imap_server.delete(kw.get('folder_id'))
        return request.redirect('/mail/inbox')

    @http.route(['/mail/move_to_folder/<model("message.folder"):folder>/<model("mail.message"):message>'], type='http', auth="user", website=True)
    def odoo_move_to_folder(self, folder, message, **kw):
        if folder and message:
            message.folder_id = folder.id
        return request.redirect(request.httprequest.referrer or '/mail/inbox')

    @http.route('/mail/<int:index>/all_move_to_folder', type="json", auth="user", website=True)
    def odoo_all_move_to_folder(self, index, folder_id, messg_ids, **post):
        fetchmail_server = request.env['fetchmail.server'].search([
                ('user_id', '=', request.env.user.id),
                ('server_type', '=', 'imap')
            ])
        server = fetchmail_server[index]
        imap_server = server.connect()
        status, folders = imap_server.list()
        folder_id = f'"{folder_id}"'
        for folder in folders:
            # real_name = folder.decode().split(' "." ')[1]
            # imap_server.select(real_name)
            raw_name = folder.decode().split(' "." ')[1].replace('"', '')
            encoded_name = imapclient.imap_utf7.encode(raw_name)
            status, _ = imap_server.select(encoded_name)
            if status != "OK":
                _logger.error(f"Cannot select folder: {raw_name}")
                continue
            moved = False
            for mssg in messg_ids:
                result, data = imap_server.search(None, f'HEADER Message-ID "{mssg}"')
                if data[0]:
                    moved = True
                    for num in data[0].split():
                        status, response = imap_server.copy(num, folder_id)
                        # Mark the email for deletion
                        imap_server.store(num, '+FLAGS', '\\Deleted')
                        imap_server.expunge()
            if moved:
                return True
        return True

    @http.route(['/mail/folder/create'], type='http', auth="user", methods=["POST"], website=True)
    def odoo_new_folder(self, **kw):
        if kw.get('create_folder'):
            user_id = request.env.user.id
            folder_id = request.env['message.folder'].create({'name': kw.get('create_folder'),
                                                              'user_id': user_id})
            if kw.get('message_id') and folder_id:
                message_id = request.env['mail.message'].sudo().browse(int(kw.get('message_id')))
                message_id.folder_id = folder_id.id
        return request.redirect(request.httprequest.referrer or '/mail/inbox')

    @http.route('/mail/get_document_records', type="json", auth="user", website=True)
    def get_document_model_records(self, **kw):
        records_dict = {}
        document_model = kw.get('document_model') if kw.get('document_model') != '0' else False
        if document_model:
            records = request.env[kw.get('document_model')].search([], order="id")
            records_dict = records.name_get()
        return records_dict

    @http.route('/mail/get_document_followers', type="json", auth="user", website=True)
    def get_document_followers(self, **kw):
        followers_dict = []
        if kw.get('document_model') and kw.get('res_id'):
            followers = request.env['mail.followers'].sudo().search([
                        ('res_model', '=', kw.get('document_model')),
                        ('res_id', '=', int(kw.get('res_id')))])
            for follower in followers:
                if follower.partner_id:
                    followers_dict.append({'id': follower.partner_id.id, 'name': follower.partner_id.name})
        return followers_dict

    @http.route('/mail/get_res_partners', type="json", auth="user", methods=['POST', 'GET'], website=True, csrf=False)
    def get_mail_res_partners(self, q=None, **kw):
        partner_values = {}
        partner_list = []
        domain = [('email', '!=', False)]
        # _logger.info(f"res_partner_query is {q}")
        if q:
            domain += ['|', ('name', 'ilike', q), ('email', 'ilike', q)]
            partner_ids = request.env['res.partner'].search(domain)
            # _logger.info(f"res_partner_query is {str(partner_ids)}")
            for partner in partner_ids:
                text_name = ''
                if partner.name:
                    text_name += partner.name
                if partner.email:
                    email_name = ' <' + partner.email + '>'
                    text_name += email_name
                partner_list.append({'id': partner.id,
                                     'text': text_name})
        partner_values = {"items": partner_list}
        return partner_values

    @http.route('/mail/get_mail_templates', type="json", auth="user", website=True)
    def get_mail_templates(self, **kw):
        templates_dict = []
        mail_template_ids = request.env['mail.template'].sudo().search([('model', 'in', ('inbox.mail.template', kw.get('document_model', False)))])
        for mail_template in mail_template_ids:
            templates_dict.append({'id': mail_template.id, 'name': mail_template.name})
        return templates_dict

    @http.route('/mail/get_mail_template_body', type="json", auth="user", website=True)
    def get_mail_template_body(self, **kw):
        template_value = {}
        if kw.get('mail_template_id'):
            template = request.env['mail.template'].with_context(tpl_partners_only=True).browse(int(kw.get('mail_template_id')))
        if kw.get('res_id'):
            res_id = int(kw.get('res_id'))
        else:
            if template and template.model_id and template.model_id.model == 'inbox.mail.template':
                res_id = request.env.ref('odoo_inbox.data_inbox_mail_template').id
        if res_id and template:
            if template:
                fields = ['subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc',  'reply_to', 'attachment_ids', 'mail_server_id']
                template_values = template.generate_email([res_id], fields=fields)
                template_value = template_values[res_id]
        return template_value

    @http.route('/mail/create_mail_template', type="json", auth="user", website=True)
    def create_mail_template(self, **kw):
        if kw.get('model_name'):
            document_model_name = kw.get('model_name')
        else:
            document_model_name = 'inbox.mail.template'
        subject = kw.get('subject')
        body_html = kw.get('body_html')
        model = request.env['ir.model'].sudo()._get(document_model_name)
        model_name = model.name or ''
        template_name = "%s: %s" % (model_name, tools.ustr(subject))
        values = {
            'name': template_name,
            'subject': subject or False,
            'body_html': body_html or False,
            'model_id': model.id or False,
            # 'attachment_ids': [(6, 0, [att.id for att in record.attachment_ids])],
        }
        template = request.env['mail.template'].create(values)
        # _logger.info("Mail Template is created: %s" % [template])
        return True
