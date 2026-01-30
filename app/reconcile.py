def run_bank_recon(all_properties, bank_json):
    report = {}
    
    for merchant in ["GOGO PROPERTY", "SURE REALTY"]:
        # Use abs() to ensure negative LLM extractions match positive bank deposits
        pdf_total = sum(abs(p.net_income) for p in all_properties if p.merchant_group == merchant)
        
        # Case-insensitive merchant lookup in bank data
        bank_entry = next((item for item in bank_json 
                          if merchant.lower() in str(item.get('Merchant', '')).lower()), None)
        
        bank_total = float(bank_entry['Amount']) if bank_entry else 0.0
        
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