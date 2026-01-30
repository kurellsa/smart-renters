def run_bank_recon(doc1, doc2, bank_json):
    report = {}
    
    # Process both documents
    for doc in [doc1, doc2]:
        merchant = doc.merchant_group
        
        # Calculate total from this document's properties
        pdf_total = sum(abs(p.net_income) for p in doc.properties)
        
        # Find the matching deposit in the bank CSV
        bank_entry = next((item for item in bank_json 
                          if merchant.lower() in str(item.get('Merchant', '')).lower()), None)
        
        bank_total = float(bank_entry['Amount']) if bank_entry else 0.0
        diff = round(pdf_total - bank_total, 2)

        report[merchant] = {
            "status": "MATCHED" if abs(diff) < 0.01 else "DISCREPANCY",
            "pdf_total": round(pdf_total, 2),
            "bank_total": round(bank_total, 2),
            "difference": diff,
            "property_count": len(doc.properties)
        }
            
    return report