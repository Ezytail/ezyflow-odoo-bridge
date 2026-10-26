# Changelog of the EzyFlow bridge

The bridge's contract version (series-less, ADR 0015). The connector expects the
same major and minor (`src/Odoo.Service/Odoo/BridgeContract.cs`).

## 3.8.0

Every bridge setting lives on the EzyFlow settings page (ADR 0020).

- A **Connector** block on the EzyFlow page of the Settings shows the three
  wake-up keys, `ezyflow.activity`, `ezyflow.wakeup_url` and
  `ezyflow.wakeup_secret`, the secret behind a password field. They stay
  database-wide system parameters, still seeded empty, so a value already set
  is kept and shown.
- The proforma report becomes a field of the company,
  `ezy_proforma_report_id`, a sales order report chosen from a list in a new
  **Documents** block, empty by default (Odoo's pro forma). The render reads it
  from the order's company; a report of another model written through RPC
  renders Odoo's pro forma with a logged warning, as before.
- The system parameter `ezyflow.proforma_report` is retired: the migration
  copies its value onto every company whose field is empty, drops a value that
  names no sales order report with a logged warning, and deletes the parameter.
  The bridge no longer ships it.
- No new right: every internal user, the connector user included, reads the
  company field.

Before going live on 3.8.0:

- A database with several companies that relied on one parameter for all of
  them gets that report on every company, archived ones included; an
  administrator changes it per company on the page if needed.
- Scripts or runbooks that set `ezyflow.proforma_report` now write nothing the
  bridge reads; set the company's **Proforma report** instead.

## 3.7.1

The connector validates past `stock_sms`'s one-time window (ADR 0019, issue #36).

- Behaviour 11: when the connector user validates a delivery, the bridge records
  `stock_sms`'s one-time "SMS confirmation" window as received for its company,
  as the window's send button does, so the delivery closes on the first try
  instead of retrying until a person dismisses the window. No new field, no
  new right, no migration.
- Whether a text goes out stays with the company's **SMS confirmation** setting
  (Inventory settings), on for every company that existed when `stock_sms` was
  installed. A company that does not want texts turns it off, as in plain Odoo.

Before going live on 3.7.1: the 3.5.0 step about dismissing the window is no
longer needed; check the **SMS confirmation** setting of each company instead.
Where it is on, the first delivery the connector validates texts the customer
and spends IAP credits, which is what the window warned about.

## 3.6.0

Apply stock reports (ADR 0018).

- A company switch `ezy_apply_stock_reports`, **off** by default, in a new
  **Stock** block of the EzyFlow page of the Settings. The new column reads off
  for every existing company, so the upgrade needs no migration.
- Off, the connector writes a WMS stock report as pending counts (the physical
  inventory's counted quantities) and republishes nothing; on, it applies the
  report as before, when the publication's `overwrite_stock` allows it.
- No new right: the connector user reads the company switch with the
  internal-user rights it already has, after checking the installed contract
  version in `ir.module.module` (readable since S1); an older bridge reads as
  off.

Before going live on 3.6.0:

- Deploy the connector built for 3.6.0 together with the bridge: an older
  connector does not read the switch and keeps applying every report.
- An Odoo that relied on reports being applied keeps pending counts from the
  upgrade on until an administrator turns **Apply stock reports** on for each
  company that wants it.

## 3.5.0

The WMS constraints (ADR 0017, behaviour 8 of the README).

- One company switch per constraint, on by default, on a new **EzyFlow** page of
  the Settings that replaces the EzyFlow block of the Inventory settings. The
  migration carries the 3.4.0 switches `ezy_check_product_constraints` and
  `ezy_check_partner_constraints` onto the switches they covered and leaves
  every new one on.
- Two figures tighten to Reflex's own:
  - internal reference: at most **16** characters (was 17);
  - partner name: at most **35** characters (was 50).
  An existing record above the new figure is not touched; it is refused only
  when a person next writes that field, with a message naming the limit.
- New constraints: internal reference alphabet `A-Z 0-9 _ . - #`, barcode
  letters and digits up to 35, city 35, postcode 9, phone 20, email 140, a phone
  and an email on the delivery address when a sales order is confirmed, and the
  next transfer reference of a receipt or delivery type in logistics mode (at
  most 20 characters of `A-Z 0-9 _ - . # / \`).
- Each figure is checked when its own field is written; the transfer reference
  is checked when the logistics mode, the operation type, the sequence, the
  sequence code or the company of a receipt or delivery type is written, and
  when its sequence is edited (a warehouse's short code renamed included).
- The context key `ezy_defer_wms_identity` defers the product constraints only.
- The connector user is no longer bound: what a shop sends lands in Odoo as it
  is, and Reflex's declared rules judge it. Administrators and code run as
  superuser stay bound.

Before going live on 3.5.0:

- A website or portal order is confirmed only with a phone and an email on its
  delivery address; make both mandatory at checkout, or turn
  `ezy_wms_delivery_contact_required` off.
- Delivery addresses now carry a phone, so Odoo's `stock_sms` shows its one-time
  "SMS confirmation" window on the first delivery a company validates, and the
  connector cannot close that delivery until a person dismisses it once
  (Inventory, validate any delivery, then confirm or disable the SMS). Not
  needed from 3.7.1 on (ADR 0019).

## 3.4.0

The barcode is optional on sellable goods.
