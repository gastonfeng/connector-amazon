# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging
import re
import math
from collections import Counter
from datetime import datetime
from xml.etree import cElementTree as ET

from odoo.addons.component.core import Component

from odoo import api
from odoo.exceptions import MissingError
from ..config.common import AMAZON_DEFAULT_PERCENTAGE_FEE, AMAZON_COSINE_NAME_MIN_VALUE

WORD = re.compile(r'\w+')

_logger = logging.getLogger(__name__)


class ProductStockExporter(Component):
    _name = 'amazon.product.stock.exporter'
    _inherit = 'amazon.exporter'
    _usage = 'amazon.product.stock.export'
    _apply_on = ['amazon.product.product']

    @api.multi
    def recompute_amazon_stocks_product(self, product, product_computed=[]):
        """
        Recompute de stock on Amazon of product and all products on upper or lower relationship LoM
                         -- Prod1 --
                         |          |
                       Prod2      Prod3 --
                                          |
                                        Prod4 --> sale this
                                          |
                                        Prod5
        We need to update the stock on Amazon of all products from Prod1 to Prod5
        :param product: product of sale
        :param product_computed: control of product's computed for doesn't go to infinite loop
        :return:
        """

        if product.id not in product_computed:
            product_computed.append(product.id)
            # First, we are going up on the LoM relationship
            if product.bom_ids:
                for bom in product.bom_ids:
                    for line_bom in bom.bom_line_ids:
                        self.recompute_amazon_stocks_product(line_bom.product_id, product_computed=product_computed)
            # Second, we are going to search if any product have this product on LoM
            bom_childs = self.env['mrp.bom.line'].search([('product_id', '=', product.id)])
            for line_bom in bom_childs:
                self.recompute_amazon_stocks_product(line_bom.bom_id.product_tmpl_id.product_variant_id, product_computed=product_computed)

            if product.amazon_bind_ids:
                for amazon_product in product.amazon_bind_ids:
                    backend = amazon_product.backend_id
                    if amazon_product.stock_sync or backend.stock_sync:
                        for detail in amazon_product.product_product_market_ids:
                            virtual_available = detail.product_id.odoo_id._compute_amazon_stock(products_amazon_stock_computed=[])
                            handling_time = detail.product_id.odoo_id._compute_amazon_handling_time()

                            if handling_time != None and virtual_available != None:
                                data = {'sku':detail.product_id.sku,
                                        'Quantity':'0' if virtual_available < 0 or not handling_time else str(
                                            int(virtual_available)),
                                        'id_mws':detail.marketplace_id.id_mws}

                                vals = {'backend_id':backend.id,
                                        'type':'Update_stock',
                                        'model':detail._name,
                                        'identificator':detail.id,
                                        'data':data,
                                        }
                                self.env['amazon.feed.tothrow'].create(vals)

    def run(self, prod_stock):
        """ Change the stock on Amazon.

        :param records: list of dictionaries of products with structure [{'sku': sku1, 'Quantity': 3, 'id_mws': market_id},{...}]
        """
        feed_binding_model = self.env['amazon.feed']
        feed_binding_model.export_batch(backend=self.backend_record,
                                        filters={'method':'submit_stock_update', 'arguments':[prod_stock]})


class ProductStockPriceExporter(Component):
    _name = 'amazon.product.stock.price.exporter'
    _inherit = 'amazon.exporter'
    _usage = 'amazon.product.stock.price.export'
    _apply_on = 'amazon.product.product'

    @api.multi
    def recompute_amazon_prices_product(self, product, product_computed=[]):
        """
        Recompute de price and stock on Amazon of product and all products on upper or lower relationship LoM
                         -- Prod1 --
                         |          |
                       Prod2      Prod3 --
                                          |
                                        Prod4 --> sale this
                                          |
                                        Prod5
        We need to update the price and stock on Amazon of all products from Prod1 to Prod5
        :param product: product of sale
        :param product_computed: control of product's computed for doesn't go to infinite loop
        :return:
        """
        if product.id not in product_computed:
            product_computed.append(product.id)
            # First, we are going up on the LoM relationship
            if product.bom_ids:
                for bom in product.bom_ids:
                    for line_bom in bom.bom_line_ids:
                        self.recompute_amazon_prices_product(line_bom.product_id, product_computed=product_computed)
            # Second, we are going to search if any product have this product on LoM
            bom_childs = self.env['mrp.bom.line'].search([('product_id', '=', product.id)])
            for line_bom in bom_childs:
                self.recompute_amazon_prices_product(line_bom.bom_id.product_tmpl_id.product_variant_id, product_computed=product_computed)

            if product.amazon_bind_ids:
                for amazon_product in product.amazon_bind_ids:
                    backend = amazon_product.backend_id
                    if amazon_product.stock_sync or backend.stock_sync:
                        for detail in amazon_product.product_product_market_ids:
                            # Change price
                            self.calc_price_to_export(id_detail=detail.id)

    @api.multi
    def up_price_with_buybox(self, detail):
        """
        The method is going to consider the next cases to up the prices:
                    Yesterday offer     Today offer
        Seller 1            9,5              9,5
        Seller 2            10               12
        Seller 3            13               13

                    Yesterday offer     Today offer
        Seller 1            9,5              10
        Seller 2            10               12
        Seller 3            13               13

        If our last price is lower than the current price the change is not executed

        :param detail:
        :return:
        """
        # We need to know if it is posible up the price
        our_offer = detail.offer_ids.filtered('is_our_offer')
        if not our_offer:
            our_offer = detail.offer_ids.filtered(lambda offer:offer.id_seller == detail.product_id.backend_id.seller)
        last_our_offer = None
        # Check if we have two or more historic offers
        if detail.historic_offer_ids and len(detail.historic_offer_ids) > 1:
            last_our_offer = detail.historic_offer_ids.sorted('offer_date', reverse=True)[1].offer_ids.filtered('is_our_offer')
            if not last_our_offer:
                last_our_offer = detail.historic_offer_ids.sorted('offer_date', reverse=True)[1].offer_ids.filtered(
                    lambda offer:offer.id_seller == detail.product_id.backend_id.seller)
        # If we need to low the offer, we don't do anything
        if not last_our_offer or last_our_offer.total_price > our_offer.total_price:
            return

        # Get the best offer from other sellers
        lower_current_compet_offer = None
        for offer in detail.offer_ids:
            if not offer.is_our_offer and (not lower_current_compet_offer or lower_current_compet_offer > offer.total_price):
                lower_current_compet_offer = offer.total_price

        # When we have the competitive other seller offer
        if lower_current_compet_offer:
            lower_last_compet_offer = None
            # We get the last offers of the ad
            if detail.historic_offer_ids and len(detail.historic_offer_ids) > 1:
                last_offers = detail.historic_offer_ids.sorted('offer_date', reverse=True)[1].offer_ids

            # We get the lower competitive offer from other seller on the last ad
            for offer in last_offers:
                if not offer.is_our_offer and (not lower_last_compet_offer or lower_last_compet_offer > offer.total_price):
                    lower_last_compet_offer = offer.total_price

            # If we have the lower last price from other seller and the difference between current competitive offer and last competivice offer from
            # others sellers is higher than 0, we up our price this difference if it is between our margins
            if lower_last_compet_offer and lower_current_compet_offer - lower_last_compet_offer > 0:
                try_price = detail.price + (lower_current_compet_offer - lower_last_compet_offer) - (our_offer.total_price - last_our_offer.total_price)
                margin_price = detail._get_margin_price(price=try_price, price_ship=detail.price_ship)
                margin_min = detail.min_margin or detail.product_id.min_margin or detail.product_id.backend_id.min_margin
                margin_max = detail.max_margin or detail.product_id.max_margin or detail.product_id.backend_id.max_margin
                if margin_min and margin_price and margin_price[1] >= margin_min and margin_price[1] <= margin_max:
                    # The price will be changed on listener TODO test it
                    detail.price = try_price
                    return True

    @api.multi
    def change_price_to_get_buybox(self, detail):
        buybox_price = 0
        buybox_ship_price = 0
        for offer in detail.offer_ids:
            if offer.is_buybox:
                buybox_price = offer.price
                buybox_ship_price = offer.price_ship

        # If there aren't buybox price it is posible that there are an error getting data offer
        if not buybox_price:
            return False

        margin_min = detail.min_margin or detail.product_id.min_margin or detail.product_id.backend_id.min_margin
        margin_max = detail.max_margin or detail.product_id.max_margin or detail.product_id.backend_id.max_margin

        type_unit_to_change = detail.type_unit_to_change or detail.product_id.type_unit_to_change or detail.product_id.backend_id.type_unit_to_change
        units_to_change = detail.units_to_change or detail.product_id.units_to_change or detail.product_id.backend_id.units_to_change
        minus_price = units_to_change if type_unit_to_change == 'price' else ((units_to_change * buybox_price) + buybox_ship_price) / 100
        # If the buybox price is lower than our price
        if not detail.has_buybox and (buybox_price + buybox_ship_price) < (detail.price + detail.price_ship):
            try_price = buybox_price + buybox_ship_price - detail.price_ship - minus_price
        elif not detail.has_buybox:
            try_price = detail.price - minus_price
        # It is posible that we haven't the buybox price for multiple reasons and try_price will be negative in this case
        if try_price <= 0:
            try_price = detail.price
        margin_price = detail._get_margin_price(price=try_price, price_ship=detail.price_ship)

        throw_try_price = False
        # If margin min is higher than margin of try_price we use that
        if margin_min and margin_price and margin_price[1] > margin_min:
            throw_try_price = True
        elif margin_price and margin_price[1] > margin_max:
            try_price = detail.product_id.product_variant_id._calc_amazon_price(backend=detail.product_id.backend_id,
                                                                                margin=margin_max,
                                                                                marketplace=detail.marketplace_id,
                                                                                percentage_fee=detail.percentage_fee or AMAZON_DEFAULT_PERCENTAGE_FEE,
                                                                                ship_price=detail.price_ship) or detail.price
            throw_try_price = True
        if throw_try_price:
            # The price will be changed on listener TODO test it
            detail.price = try_price
            return True

        return False

    @api.model
    def calc_price_to_export(self, id_detail, force_change=False):
        """
        Method to change the prices of the detail product
        :return:
        """
        # If on product detail change_prices is 'yes'
        # If product detail change_prices is not 'no' and product change_prices is 'yes'
        # If product detail and product change_prices is not 'no' and backend change_prices is 'yes'
        detail = self.env['amazon.product.product.detail'].browse(id_detail)

        # We check if we can change prices
        if force_change or ((detail.change_prices == '1' or detail.product_id.change_prices == '1' or detail.product_id.backend_id.change_prices == '1') and \
                            (detail.change_prices != '0' and detail.product_id.change_prices != '0' and detail.product_id.backend_id.change_prices != '0')):

            # If we have the buybox now
            if self.change_price_to_get_buybox(detail) or not detail.has_buybox:
                return
            # If we have the buybox and we are not get this now, we to try to up the price
            self.up_price_with_buybox(detail)

    def run(self, records):
        """ Change the stock, prices and handling time on Amazon.
        :param records: list of dictionaries of products with structure [{'sku': sku1, 'price': 3.99, 'currency': 'EUR', 'id_mws': market_id},{...}]
        """
        feed_binding_model = self.env['amazon.feed']
        feed_binding_model.export_batch(backend=self.backend_record,
                                        filters={'method':'submit_stock_price_update', 'arguments':records})


class ProductInventoryExporter(Component):
    _name = 'amazon.inventory.product.exporter'
    _inherit = 'base.exporter'
    _usage = 'amazon.product.inventory.export'
    _apply_on = 'amazon.product.product'

    def run(self, records):
        """ Change the prices on Amazon.
        :param records: list of dictionaries of products with structure
        """
        feed_exporter = self.env['amazon.feed']
        return feed_exporter.export_batch(backend=self.backend_record,
                                          filters={'method':'submit_add_inventory_request',
                                                   'arguments':[records]})


class ProductExporter(Component):
    _name = 'amazon.product.product.exporter'
    _inherit = 'amazon.exporter'
    _apply_on = 'amazon.product.product'

    def get_cosine(self, a, b):
        vec1 = self.text_to_vector(a)
        vec2 = self.text_to_vector(b)

        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])

        sum1 = sum([vec1[x] ** 2 for x in vec1.keys()])
        sum2 = sum([vec2[x] ** 2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0
        else:
            return float(numerator) / denominator

    @api.model
    def text_to_vector(self, text):
        words = WORD.findall(text)
        return Counter(words)

    @api.model
    def _get_asin_product(self, product, marketplace, filter_title_coincidence=True):
        """
        :param product:
        :param marketplace:
        :param filter_title_coincidence: filter the cosine coincidence of
        :return:
        """

        importer_product_forid = self.work.component(model_name='amazon.product.product', usage='amazon.product.data.import')
        amazon_products = importer_product_forid.run_products_for_id(ids=[product.barcode or product.product_variant_id.barcode],
                                                                     type_id=None,
                                                                     marketplace_mws=marketplace.id_mws)

        i = 0
        ind = None
        cos = 0
        if amazon_products:
            # If the flag is a true we are going to check if the cosine coincidence is higher than 0.2
            if filter_title_coincidence:
                for amazon_product in amazon_products:
                    a = amazon_product['title']
                    b = product.name
                    cosine = self.get_cosine(a, b)
                    if cosine and cosine > AMAZON_COSINE_NAME_MIN_VALUE:
                        # We get the product with the higher coincidence
                        if cosine > cos:
                            cos = cosine
                            ind = i
                    i += 1
            else:
                ind = 0
            if ind != None:
                return amazon_products[ind]

            return {'Match name':'No'}

    @api.multi
    def _process_message(self, message):
        # We are going to delete the same messages
        messages = None
        try:
            messages = message.search([('id_message', '=', message.id_message)])
        except MissingError as e:
            return
        message_to_process = False
        has_been_processed = False
        return_vals = {}
        # It is a control for duplicate messages
        if len(messages) > 1:
            for mess in messages:
                if mess.processed:
                    has_been_processed = True
                    message_to_process = True
                if mess.id != message.id:
                    mess.unlink()
        elif len(messages) == 1 and messages.processed:
            has_been_processed = True

        if not has_been_processed and message.body:
            root = ET.fromstring(message.body)
            notification = root.find('NotificationPayload').find('AnyOfferChangedNotification')
            offer_change_trigger = notification.find('OfferChangeTrigger')
            if offer_change_trigger is not None:
                id_mws = offer_change_trigger.find('MarketplaceId').text if offer_change_trigger.find('MarketplaceId') is not None else None
                asin = offer_change_trigger.find('ASIN').text if offer_change_trigger.find('ASIN') != None else None
                return_vals['asin'] = asin
                return_vals['id_mws'] = id_mws
                products = self.env['amazon.product.product.detail'].search([('product_id.asin', '=', asin), ('marketplace_id.id_mws', '=', id_mws)])
                if products:
                    return_vals['product_details'] = products
                    for detail_prod in products:
                        marketplace = detail_prod.marketplace_id
                        # item_condition = offer_change_trigger.find('ItemCondition').text if offer_change_trigger.find('ItemCondition') != None else None
                        time_change = offer_change_trigger.find('TimeOfOfferChange').text if offer_change_trigger.find(
                            'TimeOfOfferChange') is not None else None
                        time_change = datetime.strptime(time_change, "%Y-%m-%dT%H:%M:%S.%fZ")

                        historic = self.env['amazon.historic.product.offer'].search([('offer_date', '=', time_change.isoformat(sep=' ')),
                                                                                     ('product_detail_id', '=', detail_prod.id)])

                        res = None
                        # If the message hasn't been processed
                        if not historic:

                            lowest_price = None
                            summary = notification.find('Summary')
                            lowest_prices = summary.find('LowestPrices')
                            if lowest_prices is not None and lowest_prices.find('LowestPrice'):
                                low_price = float('inf')
                                for prices in lowest_prices:
                                    if prices.find('LandedPrice'):
                                        aux = prices.find('LandedPrice').find('Amount').text
                                        if float(aux) < low_price:
                                            low_price = float(aux)
                                lowest_price = low_price

                            # We are going to get offer data
                            new_offers = []
                            for offer in root.iter('Offer'):
                                new_offer = {}
                                new_offer['id_seller'] = offer.find('SellerId').text
                                if new_offer['id_seller'] == detail_prod.product_id.backend_id.seller:
                                    new_offer['is_our_offer'] = True
                                new_offer['condition'] = offer.find('SubCondition').text
                                listing_price = offer.find('ListingPrice')
                                if listing_price:
                                    new_offer['price'] = listing_price.find('Amount').text
                                    new_offer['currency_price_id'] = self.env['res.currency'].search(
                                        [('name', '=', listing_price.find('CurrencyCode').text)]).id
                                shipping = offer.find('Shipping')
                                if shipping:
                                    new_offer['price_ship'] = shipping.find('Amount').text
                                    new_offer['currency_ship_price_id'] = self.env['res.currency'].search(
                                        [('name', '=', shipping.find('CurrencyCode').text)]).id

                                if float(new_offer.get('price') or 0 + new_offer.get('price_ship') or 0) == lowest_price:
                                    new_offer['is_lower_price'] = True

                                # min_hours = None
                                # max_hours = None
                                # shipping_time = offer.find('ShippingTime')
                                # if shipping_time:
                                #    max_hours = offer.find('ShippingTime').attrib['maximumHours'] if offer.find('ShippingTime').attrib.get('maximumHours') else None
                                #    min_hours = offer.find('ShippingTime').attrib['minimumHours'] if offer.find('ShippingTime').attrib.get('minimumHours') else None

                                seller_feedback = offer.find('SellerFeedbackRating')
                                if seller_feedback:
                                    new_offer['seller_feedback_rating'] = seller_feedback.find('SellerPositiveFeedbackRating').text
                                    new_offer['seller_feedback_count'] = seller_feedback.find('FeedbackCount').text

                                new_offer['amazon_fulffilled'] = offer.find('IsFulfilledByAmazon').text == 'true' if offer.find(
                                    'IsFulfilledByAmazon').text else False
                                new_offer['is_buybox'] = offer.find('IsBuyBoxWinner').text == 'true'

                                ship_from = offer.find('ShipsDomestically')
                                if ship_from and ship_from.text == 'true':
                                    new_offer['country_ship_id'] = marketplace.country_id.id
                                else:
                                    ship_from = offer.find('ShipsFrom').find('Country').text if offer.find('ShipsFrom') and offer.find('ShipsFrom').find(
                                        'Country') else None
                                    if ship_from:
                                        new_offer['country_ship_id'] = self.env['res.country'].search([('code', '=', ship_from)]).id

                                is_prime = offer.find('PrimeInformation')
                                if is_prime:
                                    is_prime = offer.find('PrimeInformation').find('IsPrime').text == 'true' if offer.find('PrimeInformation').find(
                                        'IsPrime') != None and offer.find('PrimeInformation').find('IsPrime').text else None
                                    new_offer['is_prime'] = is_prime

                                # We save the offer on historic register
                                new_offers.append((0, 0, new_offer))

                            # We save the offers on historic offer
                            res = self.env['amazon.historic.product.offer'].create({'offer_date':time_change,
                                                                                    'product_detail_id':detail_prod.id,
                                                                                    'offer_ids':new_offers})
                        if res or historic:
                            message_to_process = True

        if message_to_process:
            message.write({'processed':True})

        return_vals['mess_processed'] = message_to_process
        return return_vals

    def _add_listing_to_amazon(self, record):
        if isinstance(record['product_id'], (int, float)):
            product = self.env['product.product'].browse(record['product_id'])
        else:
            product = record['product_id']

        marketplaces = record['marketplaces'] if record.get('marketplaces') else self.backend_record.marketplace_ids
        margin = record['margin'] if record.get('margin') else self.backend_record.max_margin

        # Get asin if we have this
        asin = None
        if not record.get('asin') and product and product.amazon_bind_ids:
            asin = product.amazon_bind_ids.asin if len(product.amazon_bind_ids) < 2 else product.amazon_bind_ids[0].asin
        else:
            asin = record['asin'] if record.get('asin') else None

        product_doesnt_exist = True
        product_dont_match = False

        # We get the user language for match with the marketplace language
        user = self.env['res.users'].browse(self.env.uid)
        market_lang_match = marketplaces.filtered(lambda marketplace:marketplace.lang_id.code == user.lang)

        if market_lang_match and not asin:
            amazon_prod = self._get_asin_product(product, market_lang_match)
            asin = amazon_prod['asin'] if amazon_prod and amazon_prod.get('asin') else None
            product_dont_match = True if amazon_prod and amazon_prod.get('Match name') == 'No' else False

        for marketplace in marketplaces:
            # If we haven't asin and we haven't searched yet, we search this
            if not asin and market_lang_match and market_lang_match.id != marketplace.id:
                amazon_prod = self._get_asin_product(product, market_lang_match)
                asin = amazon_prod['asin'] if amazon_prod and amazon_prod.get('asin') else None
                product_dont_match = True if amazon_prod and amazon_prod.get('Match name') == 'No' else False

            add_product = False if not asin else True

            if not add_product:
                continue

            product_doesnt_exist = False

            row = {}
            row['sku'] = product.default_code or product.product_variant_id.default_code
            row['product-id'] = asin
            row['product-id-type'] = 'ASIN'
            price = product._calc_amazon_price(backend=self.backend_record,
                                               margin=margin,
                                               marketplace=marketplace,
                                               percentage_fee=AMAZON_DEFAULT_PERCENTAGE_FEE)
            row['price'] = ("%.2f" % price).replace('.', marketplace.decimal_currency_separator) if price else ''
            row['minimum-seller-allowed-price'] = ''
            row['maximum-seller-allowed-price'] = ''
            row['item-condition'] = '11'  # We assume the products are new
            row['quantity'] = '0'  # The products stocks allways is 0 when we export these
            row['add-delete'] = 'a'
            row['will-ship-internationally'] = ''
            row['expedited-shipping'] = ''
            row['merchant-shipping-group-name'] = ''
            handling_time = product._compute_amazon_handling_time() or ''
            row['handling-time'] = str(handling_time) if price else ''
            row['item_weight'] = ''
            row['item_weight_unit_of_measure'] = ''
            row['item_volume'] = ''
            row['item_volume_unit_of_measure'] = ''
            row['id_mws'] = marketplace.id_mws

            vals = {'backend_id':self.backend_record.id,
                    'type':'Add_products_csv',
                    'model':product._name,
                    'identificator':product.id,
                    'data':row,
                    }
            self.env['amazon.feed.tothrow'].create(vals)

        if product_doesnt_exist and not product_dont_match:
            # TODO Create a list of products to create
            vals = {'product_id':product.product_tmpl_id.id}
            self.env['amazon.report.product.to.create'].create(vals)
            return

    def run(self, record):
        """ Change the prices on Amazon.
        :param records: list of dictionaries of products with structure
        """
        assert record
        if record.get('method'):
            if record['method'] == 'process_price_message':
                assert record['message']
                res = self._process_message(self.env['amazon.config.sqs.message'].browse(record['message']))
                if res and res.get('mess_processed') and res.get('product_details'):
                    # TODO change prices
                    for detail in res['product_details']:
                        return detail._change_price()

            elif record['method'] == 'add_to_amazon_listing':
                assert record['product_id']
                self._add_listing_to_amazon(record)
            elif record['method'] == 'change_price':
                assert record['detail_product_id']
                exporter = self.work.component(model_name='amazon.product.product', usage='amazon.product.stock.price.export')
                exporter.calc_price_to_export(record['detail_product_id'], force_change=record.get('force_change'))
            elif record['method'] == 'recompute_stocks_product':
                assert record['product_id']
                exporter = self.work.component(model_name='amazon.product.product', usage='amazon.product.stock.export')
                exporter.recompute_amazon_stocks_product(product=record['product_id'], product_computed=[])
            elif record['method'] == 'recompute_prices_product':
                assert record['product_id']
                exporter = self.work.component(model_name='amazon.product.product', usage='amazon.product.stock.price.export')
                exporter.recompute_amazon_prices_product(product=record['product_id'], product_computed=[])
