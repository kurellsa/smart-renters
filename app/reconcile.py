def run_bank_recon(all_properties, bank_json):
    """
    all_properties: List of objects (either Pydantic from LLM or SQLAlchemy from DB)
    bank_json: List of dicts from your CSV-to-JSON logic
    """
    report = {}
    
    for merchant in ["GOGO PROPERTY", "SURE REALTY"]:
        # 1. Sum up what the PDFs claim
        pdf_total = sum(p.net_income for p in all_properties if p.merchant_group == merchant)
        
        # 2. Find the 'Truth' in the bank CSV
        # We use a case-insensitive search and handle potential string/float conversion
        bank_entry = next((item for item in bank_json 
                          if merchant.lower() in str(item.get('Merchant', '')).lower()), None)
        
        bank_total = float(bank_entry['Amount']) if bank_entry else 0.0
        
        # 3. Calculate the gap (Tolerance check: ignore differences less than 1 cent)
        diff = round(pdf_total - bank_total, 2)
        is_match = abs(diff) < 0.01

        report[merchant] = {
            "status": "MATCHED" if is_match else "DISCREPANCY",
            "pdf_total": round(pdf_total, 2),
            "bank_total": round(bank_total, 2),
            "difference": diff,
            "count": len([p for p in all_properties if p.merchant_group == merchant])
        }
            
    return report