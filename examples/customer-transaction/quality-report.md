# Data Quality Report

**Quality Score: 100.0/100** (score v1)

| Category | Score |
|---|---|
| integrity | 100.0 |
| completeness | 100.0 |
| consistency | 100.0 |
| validity | 100.0 |

## dim_customer — 76/76 passed (50000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | customer_id | ✅ | 0 duplicate value(s) |
| not_null | customer_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | customer_number | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | first_name | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | first_name | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | last_name | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | last_name | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | full_name | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | gender | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | gender | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | date_of_birth | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | age | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | age | ✅ | 0 value(s) (0.00%) outside [15.4, 70.6] (tolerance 1%) |
| not_null | email | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | phone_number | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | customer_type | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | customer_type | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | loyalty_tier | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | loyalty_tier | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | loyalty_points | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | loyalty_points | ✅ | 0 value(s) (0.00%) outside [-1286, 1.421e+04] (tolerance 1%) |
| not_null | signup_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | account_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | account_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | preferred_language | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | preferred_language | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | preferred_currency | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | preferred_currency | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | preferred_device | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | preferred_device | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | preferred_channel | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | preferred_channel | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | marketing_opt_in | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | customer_segment | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | customer_segment | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | occupation | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | occupation | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | annual_income | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | annual_income | ✅ | 0 value(s) (0.00%) outside [-5.665e+05, 6.891e+06] (tolerance 1%) |
| not_null | marital_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | marital_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | country | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | country | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | state | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | state | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | city | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | city | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | district | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | district | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | postal_code | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | postal_code | ✅ | 0 value(s) (0.00%) outside [5.109e+04, 7.584e+05] (tolerance 1%) |
| not_null | timezone | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | timezone | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | address_line1 | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | latitude | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | latitude | ✅ | 0 value(s) (0.00%) outside [5.628, 34.38] (tolerance 1%) |
| not_null | longitude | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | longitude | ✅ | 0 value(s) (0.00%) outside [65.61, 94.34] (tolerance 1%) |
| not_null | total_orders | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | total_orders | ✅ | 8 value(s) (0.02%) outside [-6.3, 81.3] (tolerance 1%) |
| not_null | total_spent | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | total_spent | ✅ | 17 value(s) (0.03%) outside [-9835, 1.118e+05] (tolerance 1%) |
| not_null | average_order_value | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | average_order_value | ✅ | 0 value(s) (0.00%) outside [-620.4, 9591] (tolerance 1%) |
| not_null | first_purchase_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | last_purchase_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | churn_risk | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | churn_risk | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | customer_lifetime_value | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | customer_lifetime_value | ✅ | 0 value(s) (0.00%) outside [-1.619e+04, 1.826e+05] (tolerance 1%) |
| not_null | acquisition_source | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | acquisition_source | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | acquisition_campaign | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | acquisition_campaign | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | created_at | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | updated_at | ✅ | null ratio 0.0000 (tolerance 0.02) |

## fact_transaction — 81/81 passed (50000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | transaction_id | ✅ | 0 duplicate value(s) |
| not_null | transaction_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | order_number | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | customer_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | product_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | seller_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | warehouse_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | order_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | payment_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | shipment_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | delivery_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | expected_delivery_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | quantity | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | quantity | ✅ | 4 value(s) (0.01%) outside [0.3, 8.7] (tolerance 1%) |
| not_null | unit_price | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | unit_price | ✅ | 0 value(s) (0.00%) outside [-3740, 4.173e+04] (tolerance 1%) |
| not_null | discount_amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | discount_amount | ✅ | 5 value(s) (0.01%) outside [-722.5, 7947] (tolerance 1%) |
| not_null | tax_amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | tax_amount | ✅ | 0 value(s) (0.00%) outside [-3400, 3.756e+04] (tolerance 1%) |
| not_null | shipping_charge | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | shipping_charge | ✅ | 0 value(s) (0.00%) outside [34, 214] (tolerance 1%) |
| not_null | packaging_charge | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | packaging_charge | ✅ | 0 value(s) (0.00%) outside [3, 27] (tolerance 1%) |
| not_null | platform_fee | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | platform_fee | ✅ | 0 value(s) (0.00%) outside [-377.8, 4174] (tolerance 1%) |
| not_null | payment_gateway_fee | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | payment_gateway_fee | ✅ | 0 value(s) (0.00%) outside [-283.3, 3130] (tolerance 1%) |
| not_null | subtotal | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | subtotal | ✅ | 0 value(s) (0.00%) outside [-1.889e+04, 2.087e+05] (tolerance 1%) |
| not_null | total_amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | total_amount | ✅ | 0 value(s) (0.00%) outside [-2.222e+04, 2.463e+05] (tolerance 1%) |
| not_null | currency | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | currency | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | payment_method | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | payment_method | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | payment_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | payment_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | order_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | order_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | return_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | return_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | refund_amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | refund_amount | ✅ | 3 value(s) (0.01%) outside [-2386, 2.625e+04] (tolerance 1%) |
| accepted_values | refund_reason | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | shipping_provider | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | shipping_provider | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | tracking_number | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | fulfillment_type | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | fulfillment_type | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | delivery_partner | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | delivery_partner | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | warehouse_location | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | warehouse_location | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | customer_rating | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | customer_rating | ✅ | 0 value(s) (0.00%) outside [0.6, 5.4] (tolerance 1%) |
| not_null | review_sentiment | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | review_sentiment | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | fraud_score | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | fraud_score | ✅ | 0 value(s) (0.00%) outside [-0.09896, 1.089] (tolerance 1%) |
| not_null | fraud_flag | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | device_type | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | device_type | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | browser | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | browser | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | operating_system | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | operating_system | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | ip_address | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | session_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | cart_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | checkout_duration_seconds | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | checkout_duration_seconds | ✅ | 0 value(s) (0.00%) outside [-149.8, 1720] (tolerance 1%) |
| not_null | source_channel | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | source_channel | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | marketing_campaign | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | marketing_campaign | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | acquisition_source | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | acquisition_source | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | created_at | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | updated_at | ✅ | null ratio 0.0000 (tolerance 0.02) |
| foreign_key | customer_id | ✅ | 0 orphan value(s) |
