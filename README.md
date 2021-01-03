================
亚马逊连接器Connector Amazon
================

## 功能

+ 税计算

## 架构

```mermaid
GRAPH LR
account.tax

```

1. account.tax
   1. compute_all_with_taxes
2. 'amazon.backend'
   1. _inherit = 'connector.backend'
3. 'amazon.metadata.batch.importer'
   1. _inherit = 'amazon.direct.batch.importer'
4. 'amazon.binding.amazon.backend.listener'
   1. _inherit = 'base.connector.listener'
5. 'amazon.binding'
   1. _inherit = 'external.binding'
6. 'amazon.config.settings'
   1. _inherit = 'res.config.settings'
7. 'amazon.config.marketplace'
8. 'amazon.config.order.item.condition'
9. 'amazon.config.order.status'
10. 'amazon.config.order.status.updatable'
11. 'amazon.config.order.levelservice'
12. 'amazon.config.product.category'
13.  'amazon.config.product.type'
14.  'amazon.brand.ban'
15.  'amazon.config.category.importer'
     1.   _inherit = 'amazon.importer'
16.  "amazon.feed"
     1.   _inherit = 'amazon.binding'
17.  'amazon.feed.tothrow'
18.   'amazon.feed.adapter'
      1.    _inherit = 'amazon.adapter'
19.   'amazon.feed.exporter'
      1.    _inherit = 'amazon.batch.exporter'
20. 'amazon.feed.batch.importer'
    1.  _inherit = 'amazon.delayed.batch.importer'
21. 'amazon.feed.importer'
    1.  _inherit = 'amazon.importer'
22. 'amazon.fix.data.importer'
    1.  _inherit = 'amazon.importer'
23. 'amazon.res.partner'
    1.  _inherit = 'amazon.binding'
24. 'amazon.res.partner.adapter'
    1.  _inherit = 'amazon.adapter'
25. 'amazon.partner.import.mapper'
    1.  _inherit = 'amazon.import.mapper'
26. 'amazon.res.partner.importer'
    1.  'amazon.importer'
27. 'amazon.product.product'
    1.  _inherit = 'amazon.binding'
28. 'amazon.product.product.detail'
29. 'amazon.product.offer'
30. 'amazon.historic.product.offer'
31. 'amazon.product.product.adapter'
    1.  'amazon.adapter'
32. 'amazon.product.stock.exporter'
    1.  _inherit = 'amazon.exporter'
33. 'amazon.product.stock.price.exporter'
    1.  _inherit = 'amazon.exporter'
34. 'amazon.inventory.product.exporter'
    1.  _inherit = 'base.exporter'
35. 'amazon.product.product.exporter'
    1.  _inherit = 'amazon.exporter'
36. 'amazon.product.product.batch.importer'
    1.  _inherit = 'amazon.delayed.batch.importer'
37. 'amazon.product.product.import.mapper'
    1.  _inherit = 'amazon.import.mapper'
38. 'product.detail.map.child.import'
    1.  _inherit = 'base.map.child'
39. 'amazon.product.product.importer'
    1.  _inherit = 'amazon.importer'
40.  'amazon.product.product.detail.mapper'
     1.   _inherit = 'amazon.import.mapper'
41.   'amazon.product.product.detail.importer'
      1. _inherit = 'amazon.importer'
42. 'amazon.product.offers.importer'
    1. _inherit = 'amazon.importer'
43. 'amazon.product.price.importer'
    1. _inherit = 'amazon.importer'
44. 'amazon.product.data.importer'
    1. _inherit = 'amazon.importer'
45. 'amazon.product.sqs.message.importer'
    1. _inherit = 'amazon.importer'
46. 'amazon.binding.amazon.product.supplierinfo.listener'
    1. _inherit = 'base.connector.listener'
47. 'amazon.binding.amazon.product.product.listener'
    1. _inherit = 'base.connector.listener'
48. 'amazon.binding.amazon.product.detail.listener'
     1. _inherit = 'base.connector.listener'
49. 'amazon.binding.amazon.product.product.listener'
     1. _inherit = 'base.connector.listener'
50. 'amazon.binding.sale.order.listener'
    1. _inherit = 'base.connector.listener'
51. 'amazon.binding.purchase.order.listener'
    1. _inherit = 'base.connector.listener'
52. 'amazon.report'
    1. _inherit = 'amazon.binding'
53. 'amazon.report.adapter'
    1. _inherit = 'amazon.adapter'
54. 'amazon.report.product.to.create'
55. 'amazon.report.product.ranking.sales'
56. 'amazon.report.batch.importer'
     1. _inherit = 'amazon.delayed.batch.importer'
57. 'amazon.report.importer'
    1. _inherit = 'amazon.importer'
58. 'amazon.order.return'
    1. _inherit = 'amazon.binding'
59. 'amazon.sale.order'
    1. _inherit = 'amazon.binding'
60. 'amazon.sale.order.line'
    1. _inherit = 'amazon.binding'
61. 'amazon.sale.order.adapter'
    1. _inherit = 'amazon.adapter'
62. 'amazon.sale.shipment.confirm.exporter'
    1. _inherit = 'amazon.exporter'
63. 'amazon.sale.order.exporter'
     1. _inherit = 'base.exporter'
64. 'amazon.sale.order.batch.importer'
    1. _inherit = 'amazon.direct.batch.importer'
65. 'amazon.sale.order.mapper'
    1. _inherit = 'amazon.import.mapper'
66. 'amazon.sale.order.importer'
    1. _inherit = 'amazon.importer'
67. 'amazon.sale.order.line.mapper'
    1. _inherit = 'amazon.import.mapper'
68. 'amazon.sale.data.importer'
    1. _inherit = 'amazon.importer'
69. 'amazon.shipping.template'
70. amazon.config.sqs.message

```plantuml
amazon.backend->amazon.backend:_scheduler_throw_jobs_for_price_changes
amazon.backend->amazon.backend:_throw_delayed_jobs_for_price_changes
amazon.backend->amazon.product.product.detail:search_count
amazon.backend->amazon.config.sqs.message:search
amazon.backend->amazon.product.product:with_delay,export_record
amazon.product.stock.exporter->amazon.product.stock.exporter:run
amazon.product.product->amazon.product.product:process_price_message
```
    
