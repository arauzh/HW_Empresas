# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class account_password(models.Model):
    _name = 'account_password.account_password'
    _description = 'Supplier payment passwords'
    _order = 'id desc'
    _check_company_auto = True

    user_id = fields.Many2one(
        'res.users', string='Buyer', index=True,
        default=lambda self: self.env.user, check_company=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    name = fields.Char("Reference code", default="New",copy=False)
    observation = fields.Text(copy=False)
    partner_id = fields.Many2one(
        'res.partner',
        string='Provider',
        required=True,
        check_company=True,
        index=True
    )
    # account_move_ids = fields.Many2many(
    #     'account.move', 
    #     string='Invoice', 
    #     domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('move_type', '=', 'in_invoice'), '&', ('partner_id', '=', partner_id)]"
    #     )
    # ------------------------------------------------------
    # 1) Campo many2many con dominio ESTÁTICO que utiliza la bandera
    # ------------------------------------------------------
    account_move_ids = fields.Many2many(
        'account.move', 
        string='Invoice', copy=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('move_type', '=', 'in_invoice'), '&', ('partner_id', '=', partner_id), '&', ('password_assigned', '=', False)]"
        )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            
            vals['name'] = self.env['ir.sequence'].next_by_code('invoices_password') or 'New'
            if vals.get('name') == 'New':
                raise ValidationError(_("The string with the code 'invoices_password' was not found for the company you work for.\n Ask the person in charge to create the sequence with the 'Sequence code' field with the value 'invoices_password' and try again.")) 
            
        records = super(account_password, self).create(vals_list)
        
        for rec in records:
            if rec.account_move_ids:
                # Marcar como True todas las facturas que se acaban de asociar
                rec.account_move_ids.write({'password_assigned': True})
                
        return records
    
    def write(self, vals):
        """
        Al escribir (editar) un registro existente:
         - Detectamos si cambiará account_move_ids.
         - Marcamos las nuevas facturas asociadas con password_assigned = True.
         - Desmarcamos (password_assigned = False) las facturas que hayan sido removidas.
        """
        for rec in self:
            # Obtenemos IDs actuales antes del write
            old_invoice_ids = rec.account_move_ids.ids

            # Ejecutamos el write normal
            super(account_password, rec).write(vals)

            # Obtenemos IDs nuevos tras el write (si se cambió account_move_ids)
            new_invoice_ids = rec.account_move_ids.ids

            # Facturas que se quitaron: estaban antes y ya no están
            removed_ids = list(set(old_invoice_ids) - set(new_invoice_ids))
            if removed_ids:
                rec.env['account.move'].browse(removed_ids).write({'password_assigned': False})

            # Facturas que se agregaron: están ahora y antes no estaban
            added_ids = list(set(new_invoice_ids) - set(old_invoice_ids))
            if added_ids:
                rec.env['account.move'].browse(added_ids).write({'password_assigned': True})

        return True  # write ya fue aplicado con super

    def unlink(self):
        """
        Al borrar un account_password:
         - Antes de eliminarlo, desmarcamos (password_assigned = False) en todas las facturas asociadas.
        """
        for rec in self:
            if rec.account_move_ids:
                rec.account_move_ids.write({'password_assigned': False})
        return super(account_password, self).unlink()

class AccountMove(models.Model):
    _inherit = 'account.move'

    password_assigned = fields.Boolean(
        string='Already associated with Supplier Password',
        default=False, copy=False,
        help='Check if this invoice has already been assigned in any record account.Password'
    )