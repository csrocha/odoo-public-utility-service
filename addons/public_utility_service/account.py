# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP Module, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Service Utility Module
#    Copyright (C) 2004-2010 CT Moldeo Interactive L (<http://moldeo.coop>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
import datetime

class utility_product_lines(osv.osv):
    _name = 'utility.product.line'

    _columns = {
        'account_id': fields.many2one('account.analytic.account', 'Contract', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='restrict'),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=False, ondelete='set null'),
        'date_begin': fields.date('Service begin', required=True),
        'date_end': fields.date('Service end'),
    }

    _sql_constraints = [
        ('unique_product_line', 'unique(account_id, product_id, date_begin)', 'Exists this product for this contract'),
    ]

utility_product_lines()

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    def _get_day_of_months(self, cr, uid, context=None):
        return [ ('%i' % i, '%i' % i) for i in range(1,30) ]

    _columns = {
        'use_utilities': fields.boolean('Utilities'),
        'address_utilities_id': fields.many2one( 'res.partner', 'Delivery Address'),
        'day_of_month_invoice': fields.selection(_get_day_of_months, 'Day of month to invoice'),
        'invoice_address': fields.selection([('to_partner', 'To partner address'),
                                             ('to_invoice_address', 'To invoice address'),
                                             ('to_delivery_address','To delivery address')], 'Invoice Address'),
        'utility_line_ids': fields.one2many( 'utility.product.line', 'account_id', 'Utility Service List'),
	}

    def generate_invoice(self, cr, uid, ids, context=None):
        inv_obj = self.pool.get('account.invoice')

        context = context or {}
        base_date = context.get('base_date', datetime.date.today())
        base_date = datetime.datetime.strptime(base_date , '%Y-%m-%d').date() if isinstance(base_date, str) else base_date

        ids = self.search(cr, uid, [ ('id','in',ids),
                                     ('state','=','open') ])

        for con in self.browse(cr, uid, ids):
            date_invoice = (base_date + datetime.timedelta(days=30)).replace(day=int(con.day_of_month_invoice))

            def test_date(b, e):
                b = datetime.datetime.strptime(b , '%Y-%m-%d').date() if isinstance(b, str) else b
                e = datetime.datetime.strptime(e , '%Y-%m-%d').date() if isinstance(e, str) else e
                return b < date_invoice and ((e and date_invoice < e) or (not e))

            value = {
                'partner_id': con.partner_id.id,
                'account_id': con.partner_id.property_account_receivable.id,
                'company_id': con.company_id.id,
                'date_invoice': date_invoice.strftime("%Y-%m-%d"),
                'origin': con.name,
                'type': 'out_invoice',
                'invoice_line': [
                    (0,0,{
                        'name': line.product_id.name,
                        'product_id': line.product_id.id,
                    }) for line in con.utility_line_ids if test_date(line.date_begin, line.date_end)
                ],
            }

            inv_id = inv_obj.create(cr, uid, value)
            pass


account_analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
