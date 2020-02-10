# -*- coding: utf-8 -*-
# Copyright 2018 Halltic eSolutions S.L.
# © 2018 Halltic eSolutions S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo.addons.component.core import Component
from odoo.addons.component_event import skip_if


class AmazonBindingProductSupplierInfoListener(Component):
    _name = 'amazon.binding.amazon.product.supplierinfo.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['product.supplierinfo']

    def throw_recalculate_stock(self, record):
        product_binding_model = self.env['amazon.product.product']
        delayable = product_binding_model.with_delay(priority=5, eta=datetime.now())
        vals = {'method':'recompute_stocks_product', 'product_id':record.product_id}
        delayable.description = '%s.%s' % (self._name, 'recompute_amazon_stocks_product()')
        delayable.export_record(self.env['amazon.backend'].search([], limit=1), vals)

    def throw_change_price(self, record):
        for amazon_prod in record.product_id.amazon_bind_ids:
            delayable = amazon_prod.with_delay(priority=5, eta=datetime.now())
            vals = {'method': 'recompute_prices_product', 'product_id': amazon_prod.odoo_id, 'force_change': False}
            delayable.description = '%s.%s' % (self._name, 'recompute_prices_product(%s)' % amazon_prod.sku)
            delayable.export_record(amazon_prod.backend_id, vals)

    def on_record_create(self, record, fields=None):
        """
        When the product.supplierinfo is write we are going to change the price and stock of the product
        :param record:
        :param fields:
        :return:
        """
        if record.product_id.amazon_bind_ids:
            # TODO We need to diference between stock recalculate and change price
            # Throw recalculate job
            self.throw_recalculate_stock(record)
            # Throw the change price
            self.throw_change_price(record)

    def on_record_write(self, record, fields=None):
        """
        When the product.supplierinfo is write we are going to change the price and stock of the product
        :param record:
        :param fields:
        :return:
        """
        # TODO Test if it
        if record.product_id.amazon_bind_ids and isinstance(fields, dict):
            if fields.get('price'):
                self.throw_change_price(record)
            elif fields.get('supplier_stock'):
                self.throw_recalculate_stock(record)

        return

    def on_record_unlink(self, record, fields=None):
        # TODO throw change stock job
        return


class AmazonProductProductListener(Component):
    _name = 'amazon.binding.amazon.product.product.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['amazon.product.product']

    def on_record_create(self, record, fields=None):
        self.env['amazon.report.product.to.create'].search([('product_id', '=', record.odoo_id.product_tmpl_id.id)]).unlink()


class AmazonBindingProductSupplierInfoListener(Component):
    _name = 'amazon.binding.amazon.product.detail.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['amazon.product.product.detail']

    def on_record_create(self, record, fields=None):
        try:
            None
            """
            fee = self._get_my_estimate_fee(marketplace_id=rec.id_mws,
                                            type_sku_asin='SellerSKU',
                                            id_type=data_prod_market['sku'],
                                            price=data_prod_market['price_unit'],
                                            currency=data_prod_market['currency_price_unit'])
            if fee:
                data_prod_market['fee'] = fee
            """
        except Exception as e:
            None

    def on_record_write(self, record, fields=None):
        # If we had saved the data of product change, we are going to change the price of detail
        if fields and ('min_margin' in fields or 'max_margin' in fields or 'change_prices' in fields):
            record._change_price()

        if fields and 'price' in fields:
            # We are going to change the price in Amazon
            data = {'sku':record.sku,
                    'Price':("%.2f" % record.price).replace('.', record.marketplace_id.decimal_currency_separator) if record.price else '',
                    'Quantity':str(record.stock),
                    'handling-time':str(record.product_id.handling_time),
                    'id_mws':record.marketplace_id.id_mws}

            vals = {'backend_id':record.product_id.backend_id.id,
                    'type':'Update_stock_price',
                    'model':record._name,
                    'identificator':record.id,
                    'marketplace_id':record.marketplace_id.id,
                    'data':data,
                    }
            self.env['amazon.feed.tothrow'].create(vals)
        return


class AmazonBindingProductSupplierInfoListener(Component):
    _name = 'amazon.binding.amazon.product.product.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['amazon.product.product']

    def on_record_write(self, record, fields=None):
        # If we had saved the data of product change, we are going to change the price of detail
        if fields and ('min_margin' in fields or 'max_margin' in fields or 'change_prices' in fields):
            product_binding_model = self.env['amazon.product.product']
            delayable = product_binding_model.with_delay(priority=5, eta=datetime.now())
            vals = {'method':'recompute_prices_product', 'product_id':record, 'force_change':False}
            delayable.description = '%s.%s' % (self._name, 'recompute_prices_product(%s)' % record.sku)
            delayable.export_record(record.backend_id, vals)


class AmazonBindingSaleOrderListener(Component):
    _name = 'amazon.binding.sale.order.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['sale.order']

    def _recompute_stocks_sale(self, record):
        """
        :param record: sale
        :return:
        """
        for line in record.order_line:
            product = line.product_id
            product_binding_model = self.env['amazon.product.product']
            delayable = product_binding_model.with_delay(priority=5, eta=datetime.now())
            vals = {'method':'recompute_stocks_product', 'product_id':product}
            delayable.description = '%s.%s' % (self._name, 'recompute_amazon_stocks_product()')
            delayable.export_record(self.env['amazon.backend'].search([], limit=1), vals)
        return

    def on_record_create(self, record, fields=None):
        if record.state == 'sale':
            self._recompute_stocks_sale(record)

    def on_record_write(self, record, fields=None):
        if 'state' in fields and record.state == 'sale':
            self._recompute_stocks_sale(record)


class AmazonBindingPurchaseOrderListener(Component):
    _name = 'amazon.binding.purchase.order.listener'
    _inherit = 'base.connector.listener'
    _apply_on = ['purchase.order']

    def _recompute_stocks_purchase(self, record):
        """
        :param record: sale
        :return:
        """
        for line in record.order_line:
            product = line.product_id
            product_binding_model = self.env['amazon.product.product']
            delayable = product_binding_model.with_delay(priority=5, eta=datetime.now())
            vals = {'method':'recompute_stocks_product', 'product_id':product}
            delayable.description = '%s.%s' % (self._name, 'recompute_amazon_stocks_product()')
            delayable.export_record(self.env['amazon.backend'].search([], limit=1), vals)
        return

    def on_record_create(self, record, fields=None):
        if record.state == 'purchase':
            self._recompute_stocks_purchase(record)

    def on_record_write(self, record, fields=None):
        if 'state' in fields and record.state == 'purchase':
            self._recompute_stocks_purchase(record)
