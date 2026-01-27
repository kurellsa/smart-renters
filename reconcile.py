def reconcile(doc1, doc2, sheet):
    diffs = []

    if doc1.rent != sheet["expected_rent"]:
        diffs.append({
            "field": "rent",
            "pdf": doc1.rent,
            "sheet": sheet["expected_rent"]
        })

    if doc2.fees != sheet["expected_fees"]:
        diffs.append({
            "field": "fees",
            "pdf": doc2.fees,
            "sheet": sheet["expected_fees"]
        })

    net = None
    if doc1.rent is not None and doc2.fees is not None:
        net = doc1.rent - doc2.fees

    return {
        "property_id": doc1.property_id,
        "rent_match": doc1.rent == sheet["expected_rent"],
        "fee_match": doc2.fees == sheet["expected_fees"],
        "differences": diffs,
        "net": net
    }