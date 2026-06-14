"""
Supply chain data importer.
Reads brands.yaml supplier mappings and populates the DB.
"""

import logging

import yaml

from pipeline.db import get_db

log = logging.getLogger(__name__)

BRANDS_YAML = "config/brands.yaml"


def import_suppliers(yaml_path: str = BRANDS_YAML):
    """Import supplier-brands relationships from YAML into DB."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    db = get_db()
    suppliers = data.get("suppliers", [])
    count = 0

    for s in suppliers:
        name = s["name"]
        component = s.get("component", "other")
        brands = s.get("dependency_brands", [])
        for brand in brands:
            db.execute(
                """INSERT OR IGNORE INTO supplier_relations
                   (brand_name, supplier_name, component_type, dependency_level)
                   VALUES (?, ?, ?, 'major')""",
                (brand, name, component),
            )
            count += 1

    log.info("supplier: imported %d brand-supplier edges for %d suppliers",
             count, len(suppliers))
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    n = import_suppliers()
    db = get_db()
    rows = db.query("SELECT COUNT(*) as n FROM supplier_relations")
    print(f"Total edges in DB: {rows[0]['n']}")
