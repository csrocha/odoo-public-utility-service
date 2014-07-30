# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import netsvc
from datetime import datetime

def today():
    return datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

class sale_order(osv.osv):
    _inherit = 'sale.order'

    def generate_contract(self, cr, uid, ids, context=None):
        """
        Generate contracts with products of type contract.
        """
        con_obj = self.pool.get('account.analytic.account')
        ord_line_obj = self.pool.get('sale.order.line')
        context = context if context else {}

        for order in self.browse(cr, uid, ids, context=context):
            if any( ol.product_id.is_under_contract for ol in order.order_line ):
                con_vals = {
                    'state': 'draft',
                    'name': order.name,
                    'type': 'contract',
                    #'chart_account_id': False,
                    #'period_length': False,
                    #'period_from': False,
                    #'period_to': False,
                    #'result_selection': False,
                    'company_id': order.company_id.id,
                    #'journal_ids': False,
                    #'filter': False,
                    #'fiscalyear_id': False,
                    #'direction_selection': False,
                    #'target_move': False,
                    'partner_id': order.partner_id.id,
                    #
                    # Utility service properties
                    #
                    'use_utilities': True,
                    'address_utilities_id': order.partner_shipping_id.id,
                    'invoice_address': 'to_partner',
                    #'day_of_month_invoice': False,
                    'utility_product_line_ids': [ (0,0,{ 'product_id': _pl_.product_id.id, }) for _pl_ in order.order_line if _pl_.product_id.is_under_contract ],
                }
                con_id = con_obj.create(cr, uid, con_vals)

                # Set done all items as contract.
                if con_id:
                    for _pl_ in [ _pl_ for _pl_ in order.order_line if _pl_.product_id.is_under_contract ]:
                        ord_line_obj.write(cr, uid, _pl_.id, {'state': 'done'})
        return True

    def action_wait(self, cr, uid, ids, context=None):
        """
        Action executed when input to router activity.
        """
        self.generate_contract(cr, uid, ids, context=context)

        def any_line(order):
            return any(l.state != 'done' for l in order.order_line)

        wait_ids = [ order.id for order in self.browse(cr, uid, ids) if any_line(order) ]
        no_wait_ids = [ order.id for order in self.browse(cr, uid, ids) if not any_line(order) ]

        r = True
        if wait_ids:
            r = r and super(sale_order, self).action_wait(cr, uid, ids, context=context)
        if no_wait_ids:
            r = r and self.action_done(cr, uid, ids, context=context)

        return r

sale_order()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    def invoice_line_create(self, cr, uid, ids, context=None):
        # Remove all products of kind utility service.
        ids = [ li.id for li in self.browse(cr, uid, ids) if not li.product_id.is_under_contract ]
        r = super(sale_order_line, self).invoice_line_create(cr, uid, ids, context=context)
        return r

sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
