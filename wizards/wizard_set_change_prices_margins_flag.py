# -*- coding: utf-8 -*-
# Copyright 2018 Halltic eSolutions S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime
from datetime import datetime, timedelta

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class WizardSetChangePricesMargins(models.TransientModel):
    _name = 'amazon.change.prices.flag.margins.wizard'
    _description = 'Wizard to set flag for change prices and margins'

    @api.model
    def _get_change_prices(self):
        return self.env['amazon.product.product']._fields['change_prices'].selection

    change_prices = fields.Selection('_get_change_prices', string='Change prices')
    min_margin = fields.Float('Minimal margin', default=None)
    max_margin = fields.Float('Maximal margin', default=None)

    @api.model
    def _default_suppliers(self):
        res = False
        context = self.env.context
        if (context.get('active_model') == 'res.partner' and
                context.get('active_ids')):
            res = context['active_ids']
        return res

    @api.multi
    def compute_change_margins(self, product, product_computed=[]):
        if product.id not in product_computed:
            product_computed.append(product.id)
            # First, we are going up on the LoM relationship
            if product.bom_ids:
                for bom in product.bom_ids:
                    for line_bom in bom.bom_line_ids:
                        self.compute_change_margins(line_bom.product_id, product_computed=product_computed)
            # Second, we are going to search if any product have this product on LoM
            bom_childs = self.env['mrp.bom.line'].search([('product_id', '=', product.id)])
            for line_bom in bom_childs:
                self.compute_change_margins(line_bom.bom_id.product_tmpl_id.product_variant_id, product_computed=product_computed)

            if product.amazon_bind_ids and len(product.amazon_bind_ids) == 1:
                amazon_product = product.amazon_bind_ids
                amazon_product.change_prices = self.change_prices
                amazon_product.min_margin = self.min_margin
                amazon_product.max_margin = self.max_margin

    @api.multi
    def change_price_margins(self):
        suppliers = self.env['res.partner'].browse(self._default_suppliers())
        product_computed = []
        for supplier in suppliers:
            products = self.env['product.supplierinfo'].search([('name', '=', supplier.id)]).mapped('product_id')
            for product in products:
                self.compute_change_margins(product, product_computed=product_computed)
        return {'type':'ir.actions.act_window_close'}
