# Two small company-data bugs found during the 2026-09-25 audit

## Source

Wave 1 items **9** and **10** — both were on the PO's original easy-bugs
list but neither is fully fixed, confirmed by direct code inspection during
the 2026-09-25 audit. Bundled into one feature directory since both are
small, independent, unrelated-to-each-other fixes to the same settings
screen area.

## Issues

1. [01-company-name-editable-in-settings.md](issues/01-company-name-editable-in-settings.md)
2. [02-vat-registered-boolean-not-tristate.md](issues/02-vat-registered-boolean-not-tristate.md)

No dependency between them — can be done in either order or in parallel.
