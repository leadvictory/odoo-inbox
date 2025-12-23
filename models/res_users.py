# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    inbox_default_pane_view_type = fields.Selection([('none', 'No Split'), ('vertical', 'Vertical Split'), ('horizontal', 'Horizontal')], default="none")
    inbox_theme_backgroud_image = fields.Char('Inbox Theme Background')
    inbox_theme_backgroud_color = fields.Char('Inbox Theme Background Color')
    child_partner_ids = fields.Many2many("res.partner", string="Child Partners")

    def set_inbox_setting_user(self, **kwargs):
        user = self.env.user
        values = {}
        if kwargs.get('inbox_default_pane_view_type'):
            values.update({'inbox_default_pane_view_type': kwargs.get('inbox_default_pane_view_type')})
        if kwargs.get('inbox_theme_backgroud_image'):
            values.update({'inbox_theme_backgroud_image': kwargs.get('inbox_theme_backgroud_image'),
                           'inbox_theme_backgroud_color': False})
        if kwargs.get('inbox_theme_backgroud_color'):
            values.update({'inbox_theme_backgroud_color': kwargs.get('inbox_theme_backgroud_color'),
                           'inbox_theme_backgroud_image': False})
        if values:
            user.sudo().write(values)
        return True
