# -*- coding: utf-8 -*-
from osv import fields,osv
from tools.translate import _
from openerp import netsvc

class wiz_invoice_contract(osv.osv_memory):
    _name = 'pus.wiz_invoice_contract'
    _description = 'pus.wiz_invoice_contract'

    _columns = {
        'period_id': fields.many2one('account.period', 'Period'),
    }

    def execute(self, cr, uid, ids, context=None):
        contract_obj = self.pool.get('account.analytic.account')
        context = context or {}
        view_type = 'form,tree'

        res_ids = []
        for wiz in self.browse(cr, uid, ids):
            c_ids = context.get('active_ids', [context.get('active_id', None)])
            res_ids.extend(contract_obj.pus_generate_invoice(cr, uid, c_ids, context=context, period_id=wiz.period_id.id))
            
        # Generate action
        if len(res_ids) > 1:
            view_type = 'tree,form'
            domain = "[('id','in',["+','.join(map(str, res_ids))+"]),('user_id', '=', uid)]"
        elif len(res_ids)==1:
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
