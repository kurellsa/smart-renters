import csv
import io
from fastapi.responses import StreamingResponse

def generate_baselane_csv(properties, statement_date):
    # Create an in-memory string buffer
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Write Baselane-friendly headers
    # Adjust these names if your specific Baselane upload template differs
    writer.writerow(["Date", "Property Address", "Description", "Category", "Amount"])

    # 2. Map your extracted properties to rows
    for prop in properties:
        writer.writerow([
            statement_date,
            prop.address,
            f"Rent Payment - {prop.address}",
            "Rent",
            prop.net_income  # This matches the $1,567.50, etc.
        ])

    # 3. Seek to start of the stream
    output.seek(0)
    return output