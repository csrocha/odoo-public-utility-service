# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
import datetime

class product_product(osv.osv):
    _inherit = 'product.product'

    _columns = {
        'is_under_contract': fields.boolean('Service under contract', help="This product must be invoiced under a contract"),
    }

product_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
