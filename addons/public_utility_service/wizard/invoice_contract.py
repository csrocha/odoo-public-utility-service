# -*- coding: utf-8 -*-
from openerp import models, fields, api, _


class wiz_invoice_contract(models.TransientModel):
    _name = 'pus.wiz_invoice_contract'
    _description = 'pus.wiz_invoice_contract'

    period_id = fields.Many2one(
        'account.period',
        string='Period')
    validation_signal = fields.Selection(
        selection=[
            ('invoice_open', 'Validate'),
            ('invoice_delay', 'Wait for Validation')
        ],
        string='State')

    @api.multi
    def execute(self):
        self.ensure_one()

        contract_obj = self.env['account.analytic.account']
        view_type = 'form,tree'

        context = self.env.context
        c_ids = context.get('active_ids', [context.get('active_id', None)])

        res_ids = contract_obj.browse(c_ids).pus_generate_invoice(
            period_id=wiz.period_id.id,
            validation_signal=wiz.validation_signal
        ))

        # Generate action

        if len(res_ids) > 1:
            view_type = 'tree,form'
            domain = "[('id','in',["+','.join(map(str, res_ids))+"])," \
                "('user_id', '=', uid)]"
        elif len(res_ids) == 1:
            domain = "[('user_id', '=', uid)]"
        else:
            view_type = 'tree,form'
            domain = "[('id','in',[]),('user_id', '=', uid)]"
        value = {
            'domain': domain,
            'name': _('Generated Invoices'),
            'view_type': 'form',
            'view_mode': view_type,
            'res_model': 'account.invoice',
            'view_id': False,
            'type': 'ir.actions.act_window'
        }
        if len(res_ids) == 1:
            value['res_id'] = res_ids[0]
        return value

wiz_invoice_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
