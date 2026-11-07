# EzyFlow bridge: legacy glue

The companion addon of `ezyflow_bridge` for a tenant still running the legacy
logistics module (`logistics_improvements`): installed by Odoo on its own
where both are present, never where the legacy module is not (ADR 0035).
The legacy module owns every mirrored
value, eligibility and backorders; the bridge's fields mirror them, so the
EzyFlow connector reads and writes the bridge's fields only and never learns
which world it runs in. The developer's documentation is the bridge's README
(section "The legacy glue"); the administrator's is the bridge help page,
section 8.

## After a bridge upgrade

A bridge release that adds a WMS constraint switch defaults it on; on a glued
database the legacy module keeps the constraints, so switch the new one off on
the EzyFlow settings page after the upgrade. The install switched the others
off and computed the mirrors for the rows that existed; nothing else is to do.
