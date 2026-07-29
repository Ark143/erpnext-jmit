from . import __version__

app_name = "hotel_booking"
app_title = "Hotel Booking"
app_publisher = "josem"
app_description = "Hotel Booking Module for ERPNext"
app_email = "josem@example.com"
app_license = "MIT"

# ---------- DocTypes ----------
doctype_js = {
    "Booking": "public/js/booking.js",
}

# ---------- Fixtures ----------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Hotel Booking"]],
    },
]

# ---------- DocType Events ----------
# DocType lifecycle events (validate, on_submit, on_cancel) are implemented directly 
# as class methods on Document controllers in room.py and booking.py
doc_events = {}

# ---------- Scheduled Tasks ----------
scheduler_events = {
    "daily": [
        "hotel_booking.hotel_booking.doctype.booking.booking.auto_checkout_overdue",
    ],
}

# ---------- Permissions ----------
# Handled via Document class static method in booking.py and standard DocType permissions
has_permission = {}

# ---------- Standard NavBar ----------
standard_navbar_settings = 1

# ---------- Setup ----------
def after_install():
    """Create default Room Types and other setup data."""
    pass

# ---------- Module Config ----------
# This tells ERPNext that this is an app with its own module
