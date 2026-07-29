import frappe
from frappe.model.document import Document

class Room(Document):
    def validate(self):
        self.validate_room_number()

    def validate_room_number(self):
        if self.hotel and self.room_number:
            exists = frappe.db.exists(
                "Room",
                {"hotel": self.hotel, "room_number": self.room_number, "name": ("!=", self.name)},
            )
            if exists:
                frappe.throw(f"Room {self.room_number} already exists in hotel {self.hotel}")

    def before_save(self):
        if self.status == "Available":
            # Check if there are any active bookings for this room
            active_bookings = frappe.db.exists(
                "Booking Room",
                {
                    "room": self.name,
                    "docstatus": 1,
                    "parenttype": "Booking",
                },
            )
            # This is simplified — real check would verify date ranges
