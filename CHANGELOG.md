# Changelog of the EzyFlow bridge

The bridge's contract version (series-less, ADR 0015). The connector expects the
same major and minor (`src/Odoo.Service/Odoo/BridgeContract.cs`).

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
  (Inventory, validate any delivery, then confirm or disable the SMS). Tracked
  in issue #36.

## 3.4.0

The barcode is optional on sellable goods.
