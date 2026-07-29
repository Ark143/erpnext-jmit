import frappe
from frappe.model.document import Document

class Hotel(Document):
    def validate(self):
        self.validate_hotel_code()

    def validate_hotel_code(self):
        if self.hotel_code:
            self.hotel_code = self.hotel_code.upper().replace(" ", "_")
