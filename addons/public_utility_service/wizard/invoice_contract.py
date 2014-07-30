# -*- coding: utf-8 -*-
from osv import fields,osv
from tools.translate import _
from openerp import netsvc

class wiz_invoice_contract(osv.osv_memory):
    _name = 'pus.wiz_invoice_contract'

    _columns = {
        'do_validate': fields.boolean('Validate invoice'),
    }

    def execute(self, cr, uid, ids, context=None):
        contract_obj = self.pool.get('account.analytic.account')
        invoice_obj = self.pool.get('account.invoice')
        wf_service = netsvc.LocalService("workflow")

        for wiz in self.browse(cr, uid, ids, context=context):

            # Generate invoices.
            contract_obj.generate_invoice(cr, uid)

            # Take invoices to be validate.
            inv_ids = contract_obj.get_draft_invoices(cr, uid)

            # Validate invoices
            if inv_ids:
                # Trigger workflow events
                if wiz.do_validate:
                    invoice_obj.write(cr, uid, inv_ids, {'state': 'open'})
                    for inv_id in inv_ids:
                        wf_service.trg_write(uid, 'account.invoice', inv_id, cr)

        pass

wiz_invoice_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
