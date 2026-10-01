import httpx
from typing import Dict, Any, Optional
from ..config import get_settings

settings = get_settings()

class NOVAService:
    def __init__(self):
        self.api_key = settings.nova_api_key
        self.api_url = settings.nova_api_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def extract_invoice(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Extract invoice data from uploaded file using NOVA API"""
        try:
            # Read the file
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # For the NOVA API, we need to send the file for processing
            # The API structure might vary - this is a basic implementation
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {'file': file_content}
                response = await client.post(
                    f"{self.api_url}/extract",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._normalize_extraction(data)
                else:
                    print(f"NOVA API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Error during NOVA extraction: {str(e)}")
            return None
    
    def _normalize_extraction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize NOVA API response to expected format"""
        # This normalizes the NOVA response to our expected structure
        return {
            "vendor": {
                "name": data.get("vendor", {}).get("name", ""),
                "tax_id": data.get("vendor", {}).get("tax_id", "")
            },
            "invoice_number": data.get("invoice_number", ""),
            "invoice_date": data.get("invoice_date", ""),
            "due_date": data.get("due_date", ""),
            "po_number": data.get("po_number", ""),
            "currency": data.get("currency", "USD"),
            "payment_terms": data.get("payment_terms", ""),
            "subtotal": float(data.get("subtotal", 0)),
            "tax_amount": float(data.get("tax_amount", 0)),
            "total_amount": float(data.get("total_amount", 0)),
            "line_items": [
                {
                    "description": item.get("description", ""),
                    "sku": item.get("sku", ""),
                    "quantity": float(item.get("quantity", 0)),
                    "unit_price": float(item.get("unit_price", 0)),
                    "tax_rate": float(item.get("tax_rate", 0)),
                    "line_total": float(item.get("line_total", 0))
                }
                for item in data.get("line_items", [])
            ],
            "confidence": float(data.get("confidence", 0))
        }
