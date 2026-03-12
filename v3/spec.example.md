# OrderService
Short description of what this service does and why it exists (1-3 sentences).

-------------------------------------------------------------------------------
# Data Models
Models are ordered by importance: core entities first, then their dependencies.
-> one to many  
-- one to one

## Order
A purchase placed by a customer.  
**Storage** postgres  
**Fields**
- number           string                          unique
- status           OrderStatus                     = draft
- total            decimal                         >= 0, computed = sum(items.subtotal)
- note             string?                         required when total = 0
- created_at       datetime
- completed_at     datetime?                       > created_at
- customer         -> Customer
**Indexes**     
- status, created_at       for listing active orders
- customer, created_at     for customer order history

## OrderStatus
**Values:** draft, confirmed, shipped, cancelled

## Customer
A person or company that places orders.
**Storage** postgres
**Fields**
 - email            string                unique
 - name             string
 - type             enum (individual|company)
 - user             -- User

## User
**Source:** auth-service

## Product
An item available for sale.
**Storage** postgres
**Fields**
 - name             string
 - sku              string        unique
 - price            decimal       >= 0

## LineItem
A single product entry within an order.  
**Storage** postgres  
**Fields**
 - quantity          int           > 0
 - price             decimal       >= 0
 - subtotal          decimal       computed = quantity * price
 - order             -> Order
 - product           -> Product

**Constraints**
 - order, product    unique together
 - price must match product.price at time of creation

-------------------------------------------------------------------------------
# Business Rules

## Roles
**Source:** auth-service — authenticated, staff, admin
- owner              order.customer.user = current user

## Jobs
Scheduled or event-driven tasks that run without user interaction.
Defines *what* should happen and *when* (business rule).
- cancel stale orders   | cron: every hour | cancel orders in draft older than 24h

## Ordering Process
desc: Customer creates and manages their orders before submission.
who: owner

**Actions**
- create order → draft
- add item: draft
  guard: product.price > 0
  then: recalculate order.total
- remove item: draft
  then: recalculate order.total
- cancel order: draft → cancelled
  then: release reserved stock via warehouse-service

## Fulfillment Process
Staff reviews, confirms and ships orders to customers.
**Permission**
- staff, admin
**Actions**
- *confirm order*
  state: draft → confirmed
  guard: items.count > 0
  then: notify customer via email-service
  then: reserve stock via warehouse-service
- *ship order*
  state: confirmed → shipped
  do: set completed_at = now
  do: print shipping documents
  then: notify customer via email-service

-------------------------------------------------------------------------------
# Runtime
Logical units that compose the running service.
Defines *what* must be running, not *how* it is deployed.

## api
Main HTTP process
- Serves REST API
- port: 8000

## order-worker
Handles async side-effects for order state changes
- Wakes on signal: order.confirmed, order.cancelled

## stock-sync-worker
Syncs stock levels from warehouse-service
- Wakes on signal: stock.updated

## stale-orders-scheduler
- Runs job: cancel stale orders
