def run_bank_recon(doc1, doc2, bank_json):
    report = {}
    
    # Organize documents into a list for easy iteration
    docs = [doc1, doc2]

    for doc in docs:
        merchant = doc.merchant_group
        # Sum up the income from the properties inside this specific document
        pdf_total = sum(abs(p.net_income) for p in doc.properties)
        
        # Look for the merchant in the bank data (case-insensitive)
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