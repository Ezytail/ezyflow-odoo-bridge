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
  address when the order is created. Company: `ezy_check_product_constraints`
  and `ezy_check_partner_constraints`, on by default (Inventory settings).
- The shop identity (`ezy_shop_product_id` on the product template, `ezy_shop_variant_id` on the
  variant): the id the product has in the web shop, indexed, not copied on duplicate, shown on
  the product forms.
- The behaviours behind those fields, listed below.
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
8. Length constraints. Product name 30, internal reference 17 and required
   for sellable goods; partner name 50, street and street 2 35. Each behind
   its company toggle. The barcode is optional since 3.4.0: the WMS
   identifies a product by its internal reference and scans the barcode
   when there is one. On a template
   create the variant half of the check runs once the create is complete:
   Odoo generates and validates the variant before it writes the template's
   internal reference and barcode onto it, so a sellable product created with
   its whole identity, from the product form or by the connector, was refused
   (corrected in 3.1.0). The connector adds attribute values to a template
   under the context key `ezy_defer_wms_identity`, which skips the variant
   check for that write (Odoo generates the new variant without identity),
   and writes the identity in its next call, where the check runs.
9. Wake-up. A transfer entering ready for logistics, a product or an order
   changing posts a small signed notification to the connector from a
   post-commit hook (ADR 0006; `models/wakeup.py`).
10. Chatter silence (ADR 0012, added in 3.3.0). Nothing the connector user does
    in a transaction leaves a tracking line, the recompute of a tracked stored
    field (a transfer's state) included: Odoo prepares that tracking in the
    environment that flushes the transaction, which does not always carry the
    connector's `tracking_disable`, so the bridge disables it for the connector
    group itself (`models/mail_thread.py`, on `mail.thread` itself, gated by Odoo's cached group check: ADR 0011 addendum).

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
