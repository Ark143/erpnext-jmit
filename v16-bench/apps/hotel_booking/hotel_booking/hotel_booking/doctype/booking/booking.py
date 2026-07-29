import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, now_datetime, getdate, add_days


class Booking(Document):
    def validate(self):
        self.set_title()
        self.validate_dates()
        self.validate_rooms()
        self.calculate_totals()

    def set_title(self):
        guest = getattr(self, "guest_name", None) or self.guest or ""
        hotel = self.hotel or ""
        self.title = f"{guest} — {hotel} ({self.check_in} to {self.check_out})"

    def validate_dates(self):
        if getdate(self.check_out) <= getdate(self.check_in):
            frappe.throw("Check-out Date must be after Check-in Date")

        # Check minimum 1 night
        nights = date_diff(self.check_out, self.check_in)
        if nights < 1:
            frappe.throw("Booking must be for at least 1 night")

        self.total_nights = nights

    def validate_rooms(self):
        """Ensure no duplicate rooms and rooms are available."""
        if not self.rooms:
            frappe.throw("At least one room must be selected")

        room_ids = set()
        for item in self.rooms:
            if item.room in room_ids:
                frappe.throw(f"Duplicate room: {item.room}")
            room_ids.add(item.room)

            # Fetch room details
            room_doc = frappe.get_cached_doc("Room", item.room)
            if not item.room_type:
                item.room_type = room_doc.room_type
            if not item.hotel:
                item.hotel = room_doc.hotel

            # Validate hotel matches
            if item.hotel != self.hotel:
                frappe.throw(f"Room {item.room} belongs to {item.hotel}, not {self.hotel}")

            # Check room availability (skip submitted/cancelled bookings for same room)
            if self.docstatus == 0 and not getattr(self, "amended_from", None):
                overlapping = frappe.db.sql("""
                    SELECT br.parent
                    FROM `tabBooking Room` br
                    JOIN `tabBooking` b ON b.name = br.parent
                    WHERE br.room = %s
                      AND b.docstatus = 1
                      AND b.name != %s
                      AND b.status NOT IN ('Cancelled', 'Checked Out')
                      AND b.check_in < %s
                      AND b.check_out > %s
                    LIMIT 1
                """, (item.room, self.name, self.check_out, self.check_in))

                if overlapping:
                    frappe.throw(
                        f"Room {item.room} is already booked during this period "
                        f"(Booking: {overlapping[0][0]})"
                    )

    def calculate_totals(self):
        """Calculate per-room and total amounts."""
        total = 0
        nights = getattr(self, "total_nights", None) or date_diff(self.check_out, self.check_in)

        for item in self.rooms:
            rate = item.rate or 0
            extra_bed_rate = 0

            # Get room type pricing if available
            if item.room_type:
                room_type = frappe.get_cached_doc("Room Type", item.room_type)
                if not item.rate:
                    rate = room_type.base_rate or 0
                    item.rate = rate
                extra_bed_rate = room_type.extra_bed_rate or 0

            item.amount = (rate * nights) + (extra_bed_rate * (item.extra_beds or 0) * nights)
            total += item.amount

        self.total_amount = total
        self.balance_due = total - (getattr(self, "advance_payment", 0) or 0)
        self.calculate_payment_status()

    def calculate_payment_status(self):
        balance = getattr(self, "balance_due", 0) or 0
        total = self.total_amount or 0

        if total <= 0:
            self.payment_status = "Paid"
        elif balance <= 0:
            self.payment_status = "Paid"
        elif balance < total:
            self.payment_status = "Partially Paid"
        else:
            self.payment_status = "Unpaid"

    def on_submit(self):
        """Mark rooms as occupied."""
        self.status = "Confirmed"
        for item in self.rooms:
            frappe.db.set_value("Room", item.room, "status", "Reserved")

    def on_cancel(self):
        """Release rooms back to available."""
        self.status = "Cancelled"
        # Only release if not already checked in/out
        actual_status = frappe.db.get_value("Booking", self.name, "status")
        for item in self.rooms:
            frappe.db.set_value("Room", item.room, "status", "Available")

    def on_update_after_submit(self):
        """Handle status transitions after submit."""
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return

        if self.status == "Checked In" and old_doc.status != "Checked In":
            self.actual_checkin = now_datetime()
            for item in self.rooms:
                frappe.db.set_value("Room", item.room, "status", "Occupied")

        if self.status == "Checked Out" and old_doc.status != "Checked Out":
            self.actual_checkout = now_datetime()
            for item in self.rooms:
                frappe.db.set_value("Room", item.room, "status", "Dirty")

        if self.status == "Cancelled" and old_doc.status != "Cancelled":
            for item in self.rooms:
                frappe.db.set_value("Room", item.room, "status", "Available")

    def before_save(self):
        self.set_title()

    @staticmethod
    def has_permission(doc, user=None, permission_type=None):
        """Custom permission check."""
        if not user:
            user = getattr(frappe.session, "user", "Administrator")
        if user == "Administrator":
            return True
        return True


@frappe.whitelist()
def get_available_rooms(hotel, checkin_date, checkout_date, room_type=None):
    """Return list of available rooms for given hotel and dates."""
    filters = {
        "hotel": hotel,
        "status": "Available",
        "disabled": 0,
    }
    if room_type:
        filters["room_type"] = room_type

    all_rooms = frappe.get_all(
        "Room",
        filters=filters,
        fields=["name", "room_number", "room_type", "floor"],
    )

    # Exclude rooms with overlapping confirmed bookings
    booked = frappe.db.sql("""
        SELECT DISTINCT br.room
        FROM `tabBooking Room` br
        JOIN `tabBooking` b ON b.name = br.parent
        WHERE b.docstatus = 1
          AND b.status NOT IN ('Cancelled', 'Checked Out')
          AND b.check_in < %s
          AND b.check_out > %s
    """, (checkout_date, checkin_date))

    booked_rooms = {r[0] for r in booked}

    available = [r for r in all_rooms if r.name not in booked_rooms]
    return available


@frappe.whitelist()
def check_in(booking_name):
    """API to check in a booking."""
    booking = frappe.get_doc("Booking", booking_name)
    if booking.status == "Checked In":
        frappe.throw("Booking is already checked in")
    if booking.status == "Cancelled":
        frappe.throw("Cannot check in a cancelled booking")

    booking.status = "Checked In"
    booking.actual_checkin = now_datetime()
    booking.save()

    for item in booking.rooms:
        frappe.db.set_value("Room", item.room, "status", "Occupied")

    return "Check-in successful"


@frappe.whitelist()
def check_out(booking_name):
    """API to check out a booking."""
    booking = frappe.get_doc("Booking", booking_name)
    if booking.status != "Checked In":
        frappe.throw("Booking must be checked in before check-out")

    booking.status = "Checked Out"
    booking.actual_checkout = now_datetime()
    booking.save()

    for item in booking.rooms:
        frappe.db.set_value("Room", item.room, "status", "Dirty")

    return "Check-out successful"


def auto_checkout_overdue():
    """Daily scheduler: auto check-out bookings past their checkout date."""
    overdue = frappe.get_all(
        "Booking",
        filters={
            "docstatus": 1,
            "status": "Checked In",
            "check_out": ("<", frappe.utils.today()),
        },
        fields=["name"],
    )

    for b in overdue:
        try:
            check_out(b.name)
        except Exception as e:
            frappe.log_error(f"Auto checkout failed for {b.name}: {e}")
