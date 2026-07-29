// Hotel Booking — Booking Form Scripts
frappe.ui.form.on("Booking", {
    refresh(frm) {
        // Add custom buttons based on status
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === "Confirmed") {
                frm.add_custom_button("Check In", () => {
                    frappe.confirm(
                        `Check in booking ${frm.doc.name}?`,
                        () => frappe.call({
                            method: "hotel_booking.hotel_booking.doctype.booking.booking.check_in",
                            args: { booking_name: frm.doc.name },
                            callback(r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: "Checked in!", indicator: "green" });
                                    frm.reload_doc();
                                }
                            },
                        })
                    );
                }, "Actions");
            }

            if (frm.doc.status === "Checked In") {
                frm.add_custom_button("Check Out", () => {
                    frappe.confirm(
                        `Check out booking ${frm.doc.name}?`,
                        () => frappe.call({
                            method: "hotel_booking.hotel_booking.doctype.booking.booking.check_out",
                            args: { booking_name: frm.doc.name },
                            callback(r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: "Checked out!", indicator: "green" });
                                    frm.reload_doc();
                                }
                            },
                        })
                    );
                }, "Actions");
            }
        }
    },

    hotel(frm) {
        // Filter rooms child table to only show rooms from selected hotel
        frm.set_query("room", "rooms", () => ({
            filters: { hotel: frm.doc.hotel, status: ["in", ["Available", "Reserved"]] },
        }));
    },

    checkin_date(frm) {
        calculate_nights(frm);
        fetch_available_rooms(frm);
    },

    checkout_date(frm) {
        calculate_nights(frm);
        fetch_available_rooms(frm);
    },

    advance_payment(frm) {
        frm.trigger("calculate_balance");
    },
});

frappe.ui.form.on("Booking Room", {
    rate(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },
    extra_beds(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },
    room(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.room && !row.rate) {
            frappe.db.get_value("Room", row.room, "room_type").then(({ room_type }) => {
                if (room_type) {
                    frappe.db.get_value("Room Type", room_type, "base_rate").then((r) => {
                        frappe.model.set_value(cdt, cdn, "rate", r.base_rate);
                        frappe.model.set_value(cdt, cdn, "room_type", room_type);
                    });
                }
            });
        }
    },
});

function calculate_nights(frm) {
    if (frm.doc.checkin_date && frm.doc.checkout_date) {
        let checkin = frappe.datetime.str_to_obj(frm.doc.checkin_date);
        let checkout = frappe.datetime.str_to_obj(frm.doc.checkout_date);
        let nights = frappe.datetime.get_diff(checkout, checkin);
        frm.set_value("total_nights", nights > 0 ? nights : 0);
    }
}

function calculate_row_amount(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    let nights = frm.doc.total_nights || 0;
    let rate = row.rate || 0;
    let extra_beds = row.extra_beds || 0;
    // Get extra bed rate from room type
    frappe.db.get_value("Room Type", row.room_type, "extra_bed_rate").then((r) => {
        let extra_bed_rate = r.extra_bed_rate || 0;
        let amount = (rate * nights) + (extra_bed_rate * extra_beds * nights);
        frappe.model.set_value(cdt, cdn, "amount", amount);
        frm.trigger("calculate_total");
    });
}

function calculate_total(frm) {
    let total = 0;
    (frm.doc.rooms || []).forEach(row => {
        total += row.amount || 0;
    });
    frm.set_value("total_amount", total);
    frm.set_value("balance_due", total - (frm.doc.advance_payment || 0));
}

function fetch_available_rooms(frm) {
    // Could be used to show available rooms count
    if (!frm.doc.hotel || !frm.doc.checkin_date || !frm.doc.checkout_date) return;
}
