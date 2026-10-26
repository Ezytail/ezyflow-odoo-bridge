# EzyFlow bridge

The Odoo addon (Odoo 19 and 20, one source tree, ADR 0015) the EzyFlow connector depends on: the fields and behaviours
the connector needs and nothing else (ADR 0001, ADR 0004). It lives in the
connector's repository and is versioned and tagged with the service image; the
Odoo side installs the tagged version the image was built against.

## Installing

Each GitHub release of the connector attaches `ezyflow_bridge-<version>.zip`
next to the image of the same version. Unzip it into a directory on Odoo's
addons path (the `ezyflow_bridge/` folder is at the zip's root), update the
apps list and install **EzyFlow bridge**; upgrade with `-u ezyflow_bridge`.
The same zip installs on Odoo 19 and Odoo 20 (ADR 0015). The repository
README covers the connector user, its key and the system parameters.

On Odoo 20 the Apps screen lists a module only as an official app or an
industry download; the "All" entry of its panel is hidden. A command-line
install on an existing database (`odoo -d <db> -i ezyflow_bridge`) registers
the module before that type field exists in the registry, so the row gets no
type and the bridge, installed and working, never shows in Apps; "Update Apps
List" does not repair it. Since 3.3.1 the post-install hook sets the type, and
`-u ezyflow_bridge` repairs an older install through the 3.3.1 migration
(`hooks.py`). Odoo 19 has no such field.

## What it ships

- The security group **EzyFlow connector**, the group a publication's
  connector user belongs to. It implies the inventory user rights (read
  transfers and operation types, write the WMS state) and nothing more. Its
  `api_key_duration` is ten years, so an administrator mints the connector's
  API key through the normal API-key screen with a dated expiry (ADR 0013).
  The group can read `ir.module.module`, which the connector uses to check the
  contract version at activation. The order flows (S5) add customers, sales
  orders and delivery methods; the catalogue flows (S6) add price lists (read)
  and their items, attributes and their values, and the attribute lines and
  values of templates (read, write, create). The stock flows (S7) add no right:
  the inventory user rights the group implies already read and write quants and
  read bills of materials, and Odoo 19 and 20 apply an inventory adjustment
  without a manager right. Nothing is ever unlinked. Attributes
  and their values carry no company in Odoo: one created for one publication's
  company is visible to every company of the database.
- Three system parameters, shipped empty: `ezyflow.activity` (the activity),
  `ezyflow.wakeup_url` and `ezyflow.wakeup_secret` (ADR 0006).
- The S1 contract (`docs/slices/S1-bridge-contract.md`), the closed sets in
  `models/contract.py`, on four models. Operation type: the logistics mode
  (`ezy_logistics_mode`: off, auto, manual) and the channel allow-list
  (`ezy_channels`, comma-separated channel codes, empty for every channel),
  the per-warehouse switch of ADR 0002. Transfer: the WMS state
  (`ezy_wms_state`, eight values, one field, no state on the moves, ADR 0003),
  the hold (`ezy_hold`) and the channel (`ezy_channel`, copied down from the
  sales order). Partner and sales order: the channel, copied from the delivery
  address when the order is created. Company: one switch per WMS constraint
  (`ezy_wms_*`, fourteen of them, ADR 0017), on by default, and **Apply stock
  reports** (`ezy_apply_stock_reports`, ADR 0018, since 3.6.0), off by default,
  all on the EzyFlow page of the Settings (below).
- The shop identity (`ezy_shop_product_id` on the product template, `ezy_shop_variant_id` on the
  variant): the id the product has in the web shop, indexed, not copied on duplicate, shown on
  the product forms.
- The SKU key (`ezy_sku_key` on the variant, since 3.7.0): the internal reference
  trimmed, its letters a-z upper-cased, every other character kept, stored and
  indexed. Two SKUs are the same when their keys are (CONTEXT.md, "SKU"): the
  duplicate check of behaviour 8 and the connector's SKU lookups match on it
  exactly instead of scanning the products with `ILIKE`. Only a-z fold because
  the connector computes the same key and Python and .NET disagree on Unicode
  case. It is computed for every product when the module is installed or
  upgraded to 3.7.0.
- The behaviours behind those fields, listed below.
- The **EzyFlow** page of the Settings, with its own icon
  (`static/description/icon.png`).
- Odoo tests for every behaviour, tagged `post_install`, run in the
  connector's Testcontainers job on every supported Odoo series.

Fields and behaviours land slice by slice; see `docs/slices/` in the repository.

## Behaviours

1. Offer. When a move is reserved (fully or partially), the transfer goes to
   *ready for logistics* if its operation type is in auto mode and allows its
   channel. Manual mode waits for a person (the *Offer to logistics* button);
   off never offers; internal transfers are never offered.
2. Hold. A held transfer is never offered, whatever the mode.
3. Channel copy-down: delivery address, sales order, transfer.
4. WMS state. One selection field on the transfer, eight values in hand-off
   order; Odoo sets ready, the connector writes the rest.
5. Freeze. A transfer in sent, preparation to do, in progress, done, refused
   or cancelled by logistics is neither reserved nor unreserved by Odoo
   (`_action_assign`, `_do_unreserve`, `_trigger_assign` and
   `_should_bypass_reservation` on the move; `action_assign` and
   `do_unreserve` on the transfer). Ready and shipped are not frozen.
6. Write guard. Only the connector user and administrators may change the
   lines of a frozen transfer (moves, detailed operations, quantities); the
   error names the state. Header changes and cancellation stay with people, so
   a cancellation in Odoo still reaches the WMS.
7. Visibility. The WMS state is read-only in the transfer form and list; the
   sales order's delivery status shows the WMS values (refused wins, then
   cancelled, then the transfer touched last).
8. WMS constraints (ADR 0017, per-rule switches since 3.5.0). When a person
   saves or confirms a record, the bridge refuses the values Reflex would
   refuse later. The figures are Reflex's own (ezyflow-reflex's declared rules
   and the widths of its REST API), fixed per bridge release; each has its own
   company switch, on by default:

   | Switch | Constraint |
   | --- | --- |
   | `ezy_wms_default_code_length` | internal reference at most 16 characters |
   | `ezy_wms_default_code_alphabet` | internal reference limited to `A-Z 0-9 _ . - #` |
   | `ezy_wms_default_code_unique` | internal reference held by one active product, whatever its case (since 3.7.0) |
   | `ezy_wms_default_code_required` | internal reference required for sellable goods |
   | `ezy_wms_product_name_length` | product name at most 30 characters |
   | `ezy_wms_barcode_alphabet` | barcode, when present, letters and digits only |
   | `ezy_wms_barcode_length` | barcode at most 35 characters |
   | `ezy_wms_partner_name_length` | partner name at most 35 characters |
   | `ezy_wms_street_length` | street and street 2 at most 35 characters each |
   | `ezy_wms_city_length` | city at most 35 characters |
   | `ezy_wms_zip_length` | postcode at most 9 characters |
   | `ezy_wms_phone_length` | phone at most 20 characters |
   | `ezy_wms_email_length` | email at most 140 characters |
   | `ezy_wms_delivery_contact_required` | phone and email on the delivery address when a sales order is confirmed |
   | `ezy_wms_picking_name` | next transfer reference of a receipt or delivery type in logistics mode at most 20 characters of `A-Z 0-9 _ - . # / \` |

   Every message names the record, the field and the figure. The delivery
   contact is checked by an override of the sales order confirmation, never on
   the partner: quotations, vendors and receipts need neither. Every
   confirmation that is not the connector's is bound, a website or portal
   order confirmed after its payment included: a shop selling on Odoo's own
   website makes the phone and the email mandatory at checkout. The transfer
   reference is checked on a receipt or delivery type in logistics mode when a
   field that names its next reference is written (the logistics mode, the
   operation type, the sequence, the sequence code, the company) and when its
   sequence is edited (prefix, suffix, padding, next number; core stock
   rewrites the prefix when a warehouse's short code changes). The next name
   the sequence would produce, predicted without drawing it for today's date,
   is the example the message gives; a prefix with a year in it is judged on
   the current year. The barcode is optional (since 3.4.0): the WMS identifies
   a product by its internal reference and scans the barcode when there is
   one.

   Reflex keeps one article per internal reference and merges two products
   sent under the same one instead of refusing them, so an internal reference
   already held by another active product of the company, or by a product
   shared by every company, is refused, compared by its SKU key (above). The
   check runs when the internal reference, the active flag or the template's
   company is written: unarchiving a product or moving it into another company
   cannot create the duplicate either. Archived products do not count, so a
   replacement can take the reference of the product it replaces. The message
   names the product holding the reference only to a person allowed to read
   it; a product of a company they cannot see is named as such. A duplicate
   barcode needs no switch: Odoo itself refuses a barcode another active
   product or packaging of the company holds, for every user.

   A record of a company is judged by that company's switches; a record shared
   by every company (a contact or a product with no company) by the switches of
   the company the writer is working in.

   The constraints bind people only. The connector user (a member of the
   EzyFlow connector group) is exempt, so an order or a product from a shop
   lands as the shop sent it and Reflex's declared rules judge it on the way to
   the warehouse; administrators and code run as superuser stay bound, unlike
   the write guard of behaviour 6. Each figure is checked when its own field is
   written, so a record already above a figure tightened in 3.5.0 (internal
   reference 17 to 16, partner name 50 to 35), or one the connector wrote, is
   refused only the next time a person writes that field.

   On a template create the variant half of the check runs once the create is
   complete: Odoo generates and validates the variant before it writes the
   template's internal reference and barcode onto it, so a sellable product
   created with its whole identity from the product form was refused
   (corrected in 3.1.0). The context key `ezy_defer_wms_identity` still skips
   the product constraints for the write that carries it (Odoo generates a
   variant without identity when attribute values are added); the next write
   runs them. It lifts no partner, order or operation type constraint. Any
   caller may set it, over RPC included: the constraints keep data clean for
   the WMS, they are not a security boundary.
9. Wake-up. A transfer entering ready for logistics, a product or an order
   changing posts a small signed notification to the connector from a
   post-commit hook (ADR 0006; `models/wakeup.py`).
10. Chatter silence (ADR 0012, added in 3.3.0). Nothing the connector user does
    in a transaction leaves a tracking line, the recompute of a tracked stored
    field (a transfer's state) included: Odoo prepares that tracking in the
    environment that flushes the transaction, which does not always carry the
    connector's `tracking_disable`, so the bridge disables it for the connector
    group itself (`models/mail_thread.py`, on `mail.thread` itself, gated by Odoo's cached group check: ADR 0011 addendum).

## Settings

**Settings > EzyFlow** is the bridge's own page (an `<app>` of the settings
form, the same markup on Odoo 19 and 20, ADR 0015). Its **WMS constraints**
block shows one setting per switch of behaviour 8, for the current company. A
tenant whose WMS is not Reflex turns off what it does not need; the figures
themselves are not editable (ADR 0017). Until 3.4.0 the bridge had two switches
in the Inventory settings, `ezy_check_product_constraints` and
`ezy_check_partner_constraints`; the 3.5.0 migration carries their values onto
the switches they covered (internal reference length and requirement, product
name; partner name, street) and leaves every other switch on.

Its **Stock** block (since 3.6.0) shows **Apply stock reports**, a switch of the
current company, off at install and at upgrade (ADR 0018). Off, the connector
writes every figure of a WMS stock report, stale zeros included, as a pending
count that a person reviews and applies from the physical inventory, and Odoo
republishes nothing for the report. On, the report is applied as before, unless
the publication turned `overwrite_stock` off. WMS movements are always applied;
one applied on a cell clears the pending count there. The connector user reads
the switch with its internal-user rights, once the bridge's installed contract
version (`ir.module.module`, readable since S1) says it exists; a bridge without
the switch reads as off.

## Conventions

Odoo 19 and 20, written to the APIs both series share (ADR 0015):
`models.Constraint` (never `_sql_constraints`), `Domain` from `odoo.fields`,
`@api.model_create_multi`, series-less manifest version `x.y.z` (Odoo prepends
its own series when it records the installed version). A branch on
`odoo.release.version_info` is a last resort and carries a test on both series;
the one branch so far is `models/security.py`, which loads `security/odoo19/`
(ir.model.access rows and an ir.rule) or `security/odoo20/` (ir.access rows)
because Odoo 20 merged the two models. The loader calls
`odoo.tools.convert.convert_file`, which Odoo does not document as public API: the
bridge test on each series is what proves it still works when a series is added.
`pre-commit` runs pylint-odoo, flake8 and isort on this folder.
