# -*- coding: utf-8 -*-
from osv import fields,osv
from tools.translate import _
from openerp import netsvc

class wiz_invoice_contract(osv.osv_memory):
    _name = 'pus.wiz_invoice_contract'
    _description = 'pus.wiz_invoice_contract'

    def execute(self, cr, uid, ids, context=None):
        contract_obj = self.pool.get('account.analytic.account')
        invoice_obj = self.pool.get('account.invoice')
        wf_service = netsvc.LocalService("workflow")

        # Generate invoices
        draft_ids = contract_obj.generate_invoice(cr, uid)

        # Generate action
        if len(draft_ids) > 1:
            view_type = 'tree,form'
            domain = "[('id','in',["+','.join(map(str, draft_ids))+"]),('user_id', '=', uid)]"
        elif len(ids)==1:
            domain = "[('user_id', '=', uid)]"
        else:
            domain = "[('user_id', '=', uid)]"
        value = {
            'domain': domain,
            'name': _('Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'type': 'ir.actions.act_window'
        }
        if len(ids) == 1:
            value['res_id'] = draft_ids[0]
        return value

wiz_invoice_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
