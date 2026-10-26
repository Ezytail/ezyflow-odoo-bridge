# Part of the EzyFlow connector for Odoo. See LICENSE in the repository root.
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged

from ..models.wms_constraints import SWITCHES
from .common import EzyflowBridgeCase


@tagged("post_install", "-at_install")
class TestWmsConstraints(EzyflowBridgeCase):
    """Behaviour 8 (ADR 0017): Reflex's figures, one company switch each. Every
    constraint is proved five ways: refused over the figure, accepted at the
    figure, accepted with its switch off, accepted when the connector user
    writes it, refused when an administrator writes it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.good = cls.env["product.product"].create(
            {"name": "Checked good", "default_code": "CHECKED-1", "barcode": "EZY900000001"}
        )
        cls.address = cls.env["res.partner"].create({"name": "Checked address"})

    def admin_env(self):
        return self.env(user=self.admin_user)

    def connector_env(self):
        return self.env(user=self.connector_user)

    def assert_constraint(self, switch, write, over, at, message):
        """``write(env, value)`` saves ``value`` as the user behind ``env``."""
        self.assertTrue(self.company[switch], f"{switch} is on by default")
        # Code run as superuser and an administrator are bound alike.
        for env in (self.env, self.admin_env()):
            with self.assertRaisesRegex(ValidationError, message), self.env.cr.savepoint():
                write(env, over)
        write(self.admin_env(), at)
        write(self.connector_env(), over)
        self.company[switch] = False
        write(self.admin_env(), over)

    # Products ---------------------------------------------------------------

    def write_good(self, field_name):
        def write(env, value):
            self.good.with_env(env).write({field_name: value})

        return write

    def test_internal_reference_at_most_16_characters(self):
        self.assert_constraint(
            "ezy_wms_default_code_length",
            self.write_good("default_code"),
            over="A" * 17,
            at="A" * 16,
            message=r"Internal Reference of .*Checked good.* longer than 16 characters",
        )

    def test_internal_reference_alphabet(self):
        self.assert_constraint(
            "ezy_wms_default_code_alphabet",
            self.write_good("default_code"),
            over="Gadget-1",
            at="AZ09_.-#",
            message=r"Internal Reference of .*Checked good.*Gadget-1.*A-Z 0-9 _ \. - #",
        )

    def test_internal_reference_alphabet_refuses_a_space(self):
        with self.assertRaisesRegex(ValidationError, "A-Z 0-9"):
            self.good.with_env(self.admin_env()).default_code = "GOOD 1"

    def test_internal_reference_held_by_one_active_product(self):
        self.assert_constraint(
            "ezy_wms_default_code_unique",
            self.write_good("default_code"),
            over="GOOD-1",
            at="CHECKED-3",
            message=r"Internal Reference GOOD-1 of .*Checked good.* already used by "
            r".*Sellable good.* one product per reference",
        )

    def test_internal_reference_held_by_one_product_whatever_its_case(self):
        self.company.ezy_wms_default_code_alphabet = False

        with self.assertRaisesRegex(ValidationError, "already used by"):
            self.good.with_env(self.admin_env()).default_code = "good-1"

    def test_internal_reference_is_matched_literally_not_as_a_pattern(self):
        self.company.ezy_wms_default_code_alphabet = False
        self.good.with_env(self.admin_env()).default_code = "GOOD_1"
        self.product.with_env(self.admin_env()).default_code = "GOOD%"

        self.assertEqual(self.good.default_code, "GOOD_1")

    def test_the_sku_key_is_trimmed_with_only_a_to_z_upper_cased(self):
        self.company.ezy_wms_default_code_alphabet = False
        self.company.ezy_wms_default_code_required = False
        self.good.default_code = "café-1"
        self.assertEqual(self.good.ezy_sku_key, "CAFé-1")

        self.good.default_code = False
        self.assertFalse(self.good.ezy_sku_key)

    def test_a_product_created_with_a_held_internal_reference_is_refused(self):
        Product = self.env["product.product"].with_env(self.admin_env())
        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            Product.create({"name": "Twin", "default_code": "GOOD-1"})
        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            self.env["product.template"].with_env(self.admin_env()).create(
                {"name": "Twin", "type": "consu", "default_code": "GOOD-1"}
            )
        twin = {"name": "Twin", "default_code": "GOOD-1"}
        self.assertTrue(Product.with_env(self.connector_env()).create(twin))

    def test_an_archived_product_leaves_its_internal_reference_to_a_replacement(self):
        self.product.with_env(self.admin_env()).action_archive()

        self.good.with_env(self.admin_env()).default_code = "GOOD-1"

        self.assertEqual(self.good.default_code, "GOOD-1")

    def test_unarchiving_a_product_whose_internal_reference_is_held_is_refused(self):
        self.product.with_env(self.admin_env()).action_archive()
        self.good.with_env(self.admin_env()).default_code = "GOOD-1"

        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            self.product.with_env(self.admin_env()).action_unarchive()
        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            self.product.product_tmpl_id.with_env(self.admin_env()).action_unarchive()

    def test_another_company_keeps_its_own_internal_references(self):
        # Code run as superuser is bound: the duplicate check applies to it.
        self.product.product_tmpl_id.company_id = self.company
        other = self.env["res.company"].create({"name": "Other company"})
        twin = self.env["product.product"].create(
            {"name": "Twin", "default_code": "TWIN-1", "company_id": other.id}
        )

        twin.default_code = "GOOD-1"

        self.assertEqual(twin.default_code, "GOOD-1")

    def test_a_product_shared_by_every_company_holds_its_reference_in_each(self):
        other = self.env["res.company"].create({"name": "Other company"})

        with self.assertRaisesRegex(ValidationError, "already used by"):
            self.env["product.product"].create(
                {"name": "Twin", "default_code": "GOOD-1", "company_id": other.id}
            )

    def test_the_holder_of_another_company_is_not_named_to_a_person_who_cannot_see_it(self):
        self.product.product_tmpl_id.company_id = self.company
        other = self.env["res.company"].create({"name": "Other company"})
        self.env["product.product"].create(
            {"name": "Hidden twin", "default_code": "HIDDEN-1", "company_id": other.id}
        )
        person = new_test_user(
            self.env,
            login="ezy_one_company",
            name="One-company person",
            groups="base.group_user,product.group_product_manager",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        shared = self.env["product.product"].create({"name": "Shared", "default_code": "SHARED-1"})

        with self.assertRaisesRegex(ValidationError, "used by a product of another company"):
            shared.with_user(person).default_code = "HIDDEN-1"

    def test_moving_a_product_into_a_company_that_holds_its_reference_is_refused(self):
        self.product.product_tmpl_id.company_id = self.company
        other = self.env["res.company"].create({"name": "Other company"})
        twin = self.env["product.product"].create(
            {"name": "Twin", "default_code": "GOOD-1", "company_id": other.id}
        )

        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            twin.product_tmpl_id.company_id = False
        with self.assertRaisesRegex(ValidationError, "already used by"), self.env.cr.savepoint():
            twin.product_tmpl_id.company_id = self.company

    def test_internal_reference_required_for_sellable_goods(self):
        self.assert_constraint(
            "ezy_wms_default_code_required",
            self.write_good("default_code"),
            over=False,
            at="CHECKED-2",
            message=r"Checked good.* no internal reference.*Internal Reference",
        )

    def test_services_and_goods_not_for_sale_need_no_internal_reference(self):
        Product = self.env["product.product"].with_env(self.admin_env())
        self.assertTrue(Product.create({"name": "Service", "type": "service"}))
        self.assertTrue(Product.create({"name": "Not for sale", "sale_ok": False}))

    def test_a_good_that_becomes_sellable_is_checked(self):
        product = self.env["product.product"].create({"name": "Later", "sale_ok": False})

        with self.assertRaisesRegex(ValidationError, "internal reference"):
            product.product_tmpl_id.with_env(self.admin_env()).sale_ok = True

    def test_a_sellable_good_created_without_internal_reference_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "internal reference"):
            self.env["product.product"].with_env(self.admin_env()).create({"name": "Bare"})
        self.assertTrue(
            self.env["product.product"].with_env(self.connector_env()).create({"name": "Bare"})
        )

    def test_product_name_at_most_30_characters(self):
        self.assert_constraint(
            "ezy_wms_product_name_length",
            self.write_good("name"),
            over="x" * 31,
            at="x" * 30,
            message=r"Name of .* longer than 30 characters",
        )

    def test_a_template_created_with_a_long_name_is_refused(self):
        values = {"name": "x" * 31, "type": "consu", "default_code": "LONG-NAME"}
        with self.assertRaisesRegex(ValidationError, "30 characters"):
            self.env["product.template"].with_env(self.admin_env()).create(values)
        self.assertTrue(self.env["product.template"].with_env(self.connector_env()).create(values))

    def test_barcode_letters_and_digits_only(self):
        self.assert_constraint(
            "ezy_wms_barcode_alphabet",
            self.write_good("barcode"),
            over="EZY-900",
            at="Ezy900",
            message=r"Barcode of .*Checked good.*EZY-900.* only letters and digits",
        )

    def test_barcode_at_most_35_characters(self):
        self.assert_constraint(
            "ezy_wms_barcode_length",
            self.write_good("barcode"),
            over="9" * 36,
            at="9" * 35,
            message=r"Barcode of .*Checked good.* longer than 35 characters",
        )

    def test_a_good_without_barcode_is_accepted(self):
        self.good.with_env(self.admin_env()).barcode = False

        self.assertFalse(self.good.barcode)

    # Partners ---------------------------------------------------------------

    def write_address(self, field_name):
        def write(env, value):
            self.address.with_env(env).write({field_name: value})

        return write

    def assert_address_limit(self, switch, field_name, limit, label):
        self.assert_constraint(
            switch,
            self.write_address(field_name),
            over="x" * (limit + 1),
            at="x" * limit,
            message=rf"{label} of .* longer than {limit} characters",
        )

    def test_partner_name_at_most_35_characters(self):
        self.assert_address_limit("ezy_wms_partner_name_length", "name", 35, "Name")

    def test_street_at_most_35_characters(self):
        self.assert_address_limit("ezy_wms_street_length", "street", 35, "Street")

    def test_street_2_at_most_35_characters(self):
        self.assert_address_limit("ezy_wms_street_length", "street2", 35, "Street2")

    def test_city_at_most_35_characters(self):
        self.assert_address_limit("ezy_wms_city_length", "city", 35, "City")

    def test_postcode_at_most_9_characters(self):
        self.assert_address_limit("ezy_wms_zip_length", "zip", 9, "Zip")

    def test_phone_at_most_20_characters(self):
        self.assert_constraint(
            "ezy_wms_phone_length",
            self.write_address("phone"),
            over="+" + "3" * 20,
            at="+" + "3" * 19,
            message=r"Phone of .*Checked address.* longer than 20 characters",
        )

    def test_email_at_most_140_characters(self):
        domain = "@example.test"
        self.assert_constraint(
            "ezy_wms_email_length",
            self.write_address("email"),
            over="x" * (141 - len(domain)) + domain,
            at="x" * (140 - len(domain)) + domain,
            message=r"Email of .*Checked address.* longer than 140 characters",
        )

    def test_a_partner_created_by_the_connector_lands_as_the_shop_sent_it(self):
        values = {"name": "x" * 60, "street": "x" * 60, "zip": "x" * 12}
        with self.assertRaisesRegex(ValidationError, "35 characters"):
            self.env["res.partner"].with_env(self.admin_env()).create(values)

        self.assertTrue(self.env["res.partner"].with_env(self.connector_env()).create(values))

    # Delivery contact at confirmation ----------------------------------------

    def quotation(self, address):
        # The origin marks an order created from a shop, the only kind the
        # connector user may write on Odoo 19 (security/odoo19/ir_rule.xml).
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "partner_shipping_id": address.id,
                "warehouse_id": self.warehouse.id,
                "origin": "SHOP-1",
                "order_line": [Command.create({"product_id": self.product.id})],
            }
        )

    def test_phone_and_email_required_on_the_delivery_address_at_confirmation(self):
        switch = "ezy_wms_delivery_contact_required"
        complete = self.env["res.partner"].create(
            {"name": "Complete", "phone": "+33100000000", "email": "complete@example.test"}
        )
        no_phone = self.env["res.partner"].create(
            {"name": "No phone", "email": "no.phone@example.test"}
        )
        no_email = self.env["res.partner"].create({"name": "No email", "phone": "+33100000000"})
        self.assertTrue(self.company[switch])

        for env in (self.env, self.admin_env()):
            for address, field in ((no_phone, "Phone"), (no_email, "Email")):
                order = self.quotation(address)
                with self.assertRaisesRegex(
                    ValidationError,
                    rf"{order.name} cannot be confirmed: its delivery address "
                    rf"{address.name} has no {field}",
                ), self.env.cr.savepoint():
                    order.with_env(env).action_confirm()
                self.assertEqual(order.state, "draft")
        accepted = self.quotation(complete)
        accepted.with_env(self.admin_env()).action_confirm()
        self.assertEqual(accepted.state, "sale")

        by_connector = self.quotation(no_phone)
        by_connector.with_env(self.connector_env()).action_confirm()
        self.assertEqual(by_connector.state, "sale")

        self.company[switch] = False
        switched_off = self.quotation(no_email)
        switched_off.with_env(self.admin_env()).action_confirm()
        self.assertEqual(switched_off.state, "sale")

    def test_a_quotation_and_a_receipt_need_no_delivery_contact(self):
        bare = self.env["res.partner"].create({"name": "Bare vendor"})
        self.assertTrue(self.quotation(bare).with_env(self.admin_env()))
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": bare.id,
                "order_line": [Command.create({"product_id": self.product.id, "product_qty": 1})],
            }
        )

        purchase.with_env(self.admin_env()).button_confirm()

        self.assertEqual(purchase.state, "purchase")
        self.assertTrue(purchase.picking_ids)

    # Transfer reference ------------------------------------------------------

    def with_prefix(self, picking_type, prefix):
        picking_type.sequence_id.write({"prefix": prefix, "padding": 5})

    def write_mode(self, picking_type):
        def write(env, prefix):
            target = picking_type.with_env(env)
            if env.user == self.connector_user:
                # The connector never writes operation types and holds no right
                # to; sudo keeps it the user the constraint looks at.
                target = target.sudo()
            target.write({"ezy_logistics_mode": "off"})
            self.with_prefix(picking_type, prefix)
            target.write({"ezy_logistics_mode": "auto"})

        return write

    def test_picking_reference_at_most_20_characters_on_deliveries(self):
        # The next name is the prefix and five digits.
        self.assert_constraint(
            "ezy_wms_picking_name",
            self.write_mode(self.out_type),
            over="WH/OUT/LONGER12/",
            at="WH/OUT/LONGER1/",
            message=r"Reference Sequence of .* reference WH/OUT/LONGER12/\d{5}; "
            r"the WMS accepts at most 20 characters",
        )

    def test_picking_reference_at_most_20_characters_on_receipts(self):
        self.assert_constraint(
            "ezy_wms_picking_name",
            self.write_mode(self.in_type),
            over="WH/IN/LONGER123/",
            at="WH/IN/LONGER12/",
            message=r"reference WH/IN/LONGER123/\d{5}",
        )

    def test_picking_reference_alphabet(self):
        self.assert_constraint(
            "ezy_wms_picking_name",
            self.write_mode(self.out_type),
            over="wh/out/",
            at="WH_1-2.3#/\\",
            message=r"reference wh/out/\d{5}; .*A-Z 0-9 _ - \. # / \\",
        )

    def test_a_type_saved_while_on_is_checked(self):
        # Long enough on both series: Odoo 19 builds the prefix from the
        # warehouse code and this code, Odoo 20 relates the code to the prefix.
        self.out_type.ezy_logistics_mode = "manual"

        with self.assertRaisesRegex(ValidationError, "at most 20 characters"):
            self.out_type.with_env(self.admin_env()).sequence_code = "VERYVERYLONGCODE"

    def test_a_sequence_edited_while_its_type_is_on_is_checked(self):
        self.out_type.ezy_logistics_mode = "auto"
        sequence = self.out_type.sequence_id.with_env(self.admin_env())

        with self.assertRaisesRegex(
            ValidationError, r"reference wh/out/\d{5}"
        ), self.env.cr.savepoint():
            sequence.prefix = "wh/out/"
        with self.assertRaisesRegex(
            ValidationError, "at most 20 characters"
        ), self.env.cr.savepoint():
            sequence.padding = 15
        sequence.prefix = "WH/OUT2/"

    def test_a_warehouse_code_renamed_while_its_deliveries_are_on_is_checked(self):
        self.out_type.ezy_logistics_mode = "auto"

        with self.assertRaisesRegex(ValidationError, "A-Z 0-9 _ - \\. # / "):
            self.warehouse.with_env(self.admin_env()).code = "wh"

    def test_a_type_in_mode_off_and_internal_types_are_never_checked(self):
        self.with_prefix(self.out_type, "WH/OUT/FAR/TOO/LONG/")
        self.out_type.with_env(self.admin_env()).name = "Deliveries"
        self.with_prefix(self.int_type, "WH/INT/FAR/TOO/LONG/")

        self.int_type.with_env(self.admin_env()).ezy_logistics_mode = "auto"

    def test_a_type_above_the_figure_is_refused_only_on_the_fields_that_name_it(self):
        # Turned on by a writer the constraint does not bind, as a long prefix
        # set before 3.5.0 would be.
        self.with_prefix(self.out_type, "WH/OUT/FAR/TOO/LONG/")
        self.out_type.with_env(self.connector_env()).sudo().ezy_logistics_mode = "auto"
        person = self.out_type.with_env(self.admin_env())

        person.name = "Deliveries"
        person.ezy_channels = "WEB"

        with self.assertRaisesRegex(ValidationError, "at most 20 characters"):
            person.ezy_logistics_mode = "manual"

    # Deferral and defaults ---------------------------------------------------

    def test_the_deferral_key_still_skips_the_product_checks(self):
        self.good.with_env(self.admin_env()).with_context(ezy_defer_wms_identity=True).write(
            {"default_code": False}
        )

        self.assertFalse(self.good.default_code)

    def test_the_deferral_key_lifts_no_other_constraint(self):
        deferred = self.admin_env()(context={"ezy_defer_wms_identity": True})

        with self.assertRaisesRegex(ValidationError, "35 characters"):
            self.address.with_env(deferred).name = "x" * 36
        order = self.quotation(self.address)
        with self.assertRaisesRegex(ValidationError, "cannot be confirmed"):
            order.with_env(deferred).action_confirm()

    # A tightened figure binds when a person next writes that field -----------

    def test_a_partner_above_a_tightened_figure_is_refused_only_on_that_field(self):
        # Written by the connector, as from a shop: above the 3.5.0 figure.
        self.address.with_env(self.connector_env()).name = "x" * 40
        person = self.address.with_env(self.admin_env())

        person.phone = "+33100000009"

        with self.assertRaisesRegex(ValidationError, "35 characters"):
            person.name = "y" * 40

    def test_a_product_above_a_tightened_figure_is_refused_only_on_that_field(self):
        self.good.with_env(self.connector_env()).default_code = "A" * 17
        person = self.good.with_env(self.admin_env())

        person.barcode = "Ezy901"

        with self.assertRaisesRegex(ValidationError, "16 characters"):
            person.default_code = "B" * 17

    def test_a_partner_of_no_company_is_judged_by_the_switch_of_the_active_company(self):
        other = self.env["res.company"].create({"name": "Other company"})
        other.ezy_wms_city_length = False
        self.admin_user.company_ids |= other
        in_other = self.admin_env()(context={"allowed_company_ids": [other.id, self.company.id]})

        self.address.with_env(in_other).city = "x" * 36

        with self.assertRaisesRegex(ValidationError, "35 characters"):
            self.address.with_env(self.admin_env()).city = "y" * 36

    def test_every_switch_is_on_for_a_new_company(self):
        company = self.env["res.company"].create({"name": "New company"})

        self.assertEqual([switch for switch in SWITCHES if not company[switch]], [])
