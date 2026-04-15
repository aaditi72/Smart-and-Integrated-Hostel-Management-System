from flask import Flask, render_template, request, redirect, session, url_for
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import traceback

app = Flask(__name__)
app.secret_key = "smart_hostel_secret_key"


@app.errorhandler(500)
def internal_error(e):
    tb = traceback.format_exc()
    return f"""<html><body style="font-family:monospace;padding:2rem;background:#1e1e1e;color:#f8f8f2;">
    <h2 style="color:#ff5555;">500 — Internal Server Error</h2>
    <pre style="background:#282a36;padding:1.5rem;border-radius:8px;overflow-x:auto;font-size:13px;">{tb}</pre>
    <a href="/" style="color:#8be9fd;">← Back to Login</a></body></html>""", 500


def login_required(role):
    return session.get("role") == role


# ── DEBUG ──────────────────────────────────────────────────────────────────────
@app.route("/debug/db")
def debug_db():
    results = {}
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES")
        results["tables"] = [list(r.values())[0] for r in cursor.fetchall()]
        for t in ["users","students","wardens","admins","rooms","room_allocation","complaints","fees"]:
            try:
                cursor.execute(f"DESCRIBE `{t}`")
                results[f"cols_{t}"] = [r["Field"] for r in cursor.fetchall()]
            except Exception as e:
                results[f"cols_{t}"] = f"MISSING: {e}"
        cursor.execute("SELECT user_id, username, role, linked_student_id, linked_warden_id, linked_admin_id FROM users")
        results["users"] = cursor.fetchall()
        cursor.close(); conn.close()
        results["status"] = "Connected OK"
    except Exception as e:
        results["status"] = f"FAILED: {e}"
    rows = "".join(
        f"<tr><td style='padding:.5rem 1rem;font-weight:600;color:#8be9fd'>{k}</td>"
        f"<td style='padding:.5rem 1rem'>{v}</td></tr>"
        for k, v in results.items()
    )
    return f"""<html><body style="font-family:monospace;padding:2rem;background:#1e1e1e;color:#f8f8f2;">
    <h2 style="color:#50fa7b;">DB Debug</h2><table>{rows}</table>
    <br><a href="/" style="color:#8be9fd;">← Back to Login</a></body></html>"""


# ── LOGIN ──────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["email"]
        password = request.form["password"]
        role     = request.form["role"].upper()
        try:
            conn   = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE username=%s AND password=%s AND role=%s",
                (username, password, role)
            )
            user = cursor.fetchone()
            cursor.close(); conn.close()
        except Exception as e:
            return render_template("login.html", error=f"Database error: {e}")

        if user:
            session["user_id"]         = user["user_id"]
            session["role"]            = user["role"]
            session["username"]        = user["username"]
            session["student_id"]      = user.get("linked_student_id")
            session["warden_id"]       = user.get("linked_warden_id")
            session["admin_id"]        = user.get("linked_admin_id")

            if role == "STUDENT":
                return redirect(url_for("student_dashboard"))
            elif role == "WARDEN":
                return redirect(url_for("warden_dashboard"))
            elif role == "ADMIN":
                return redirect(url_for("admin_dashboard"))

        return render_template("login.html", error="Invalid credentials. Check your email, password and selected role.")
    return render_template("login.html")


# ── REGISTER ───────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        phone    = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm_password", "").strip()
        role     = request.form.get("role", "student").upper()

        if not name or not email or not password:
            return render_template("register.html", error="Name, email and password are required.")
        if password != confirm:
            return render_template("register.html", error="Passwords do not match.")
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters.")

        try:
            conn   = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # duplicate email check
            cursor.execute("SELECT user_id FROM users WHERE username=%s", (email,))
            if cursor.fetchone():
                cursor.close(); conn.close()
                return render_template("register.html", error="An account with this email already exists.")

            cursor = conn.cursor()

            if role == "STUDENT":
                roll_no    = request.form.get("roll_no", "").strip()
                gender     = request.form.get("gender", "").strip() or None
                department = request.form.get("department", "").strip() or None
                year       = request.form.get("year", "").strip() or None
                address    = request.form.get("address", "").strip() or None

                cursor.execute("""
                    INSERT INTO students (roll_no, name, gender, department, year, phone, email, address)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (roll_no, name, gender, department, year, phone, email, address))
                conn.commit()
                new_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO users (username, password, role, linked_student_id)
                    VALUES (%s,%s,'STUDENT',%s)
                """, (email, password, new_id))
                conn.commit()

            elif role == "WARDEN":
                employee_id = request.form.get("employee_id", "").strip()
                department  = request.form.get("department", "").strip() or None
                designation = request.form.get("designation", "").strip() or "Hostel Warden"
                joined_date = request.form.get("joined_date", "").strip() or None
                address     = request.form.get("address", "").strip() or None

                cursor.execute("""
                    INSERT INTO wardens (employee_id, name, email, phone, department, designation, joined_date, address)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (employee_id, name, email, phone, department, designation, joined_date, address))
                conn.commit()
                new_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO users (username, password, role, linked_warden_id)
                    VALUES (%s,%s,'WARDEN',%s)
                """, (email, password, new_id))
                conn.commit()

            elif role == "ADMIN":
                employee_id = request.form.get("employee_id", "").strip()
                designation = request.form.get("designation", "").strip() or "Administrator"
                joined_date = request.form.get("joined_date", "").strip() or None
                address     = request.form.get("address", "").strip() or None

                cursor.execute("""
                    INSERT INTO admins (employee_id, name, email, phone, designation, joined_date, address)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (employee_id, name, email, phone, designation, joined_date, address))
                conn.commit()
                new_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO users (username, password, role, linked_admin_id)
                    VALUES (%s,%s,'ADMIN',%s)
                """, (email, password, new_id))
                conn.commit()

            cursor.close(); conn.close()

        except Exception as e:
            return render_template("register.html", error=f"Registration failed: {e}")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── STUDENT ────────────────────────────────────────────────────────────────────
@app.route("/student/dashboard")
def student_dashboard():
    if not login_required("STUDENT"): return redirect(url_for("login"))
    student_id = session.get("student_id")
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()
    room = None
    try:
        cursor.execute(
            "SELECT r.* FROM rooms r JOIN room_allocation ra ON r.room_id=ra.room_id WHERE ra.student_id=%s AND ra.status='Approved'",
            (student_id,))
        room = cursor.fetchone()
    except Exception: pass
    fee = None
    try:
        cursor.execute("SELECT * FROM fees WHERE student_id=%s ORDER BY due_date DESC LIMIT 1", (student_id,))
        fee = cursor.fetchone()
    except Exception: pass
    complaints = []
    try:
        cursor.execute("SELECT * FROM complaints WHERE student_id=%s ORDER BY created_at DESC LIMIT 5", (student_id,))
        complaints = cursor.fetchall()
    except Exception: pass
    cursor.close(); conn.close()
    return render_template("student/dashboard.html", student=student, room=room, fee=fee, complaints=complaints)


@app.route("/student/room-booking", methods=["GET", "POST"])
def student_room_booking():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    message = None

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO room_allocation (student_id, room_id, status)
            VALUES (%s, %s, 'Pending')
        """, (student_id, request.form["room_id"]))
        conn.commit()
        message = ("success", "Room request submitted")

    cursor.execute("SELECT * FROM rooms WHERE status='Available'")
    rooms = cursor.fetchall()

    cursor.execute("""
        SELECT ra.status, r.room_number
        FROM room_allocation ra
        JOIN rooms r ON ra.room_id = r.room_id
        WHERE ra.student_id=%s
        ORDER BY ra.allocation_id DESC LIMIT 1
    """, (student_id,))

    allocation = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "student/room_booking.html",
        rooms=rooms,
        allocation=allocation,
        message=message,
        student=student   
    )


@app.route("/student/complaints", methods=["GET", "POST"])
def student_complaints():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    # 🔥 FETCH STUDENT (IMPORTANT)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    message = None

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO complaints (student_id, title, description, status)
            VALUES (%s, %s, %s, 'Pending')
        """, (
            student_id,
            request.form["title"],
            request.form["description"]
        ))
        conn.commit()
        message = ("success", "Complaint submitted")

    cursor.execute("""
        SELECT * FROM complaints
        WHERE student_id=%s
        ORDER BY created_at DESC
    """, (student_id,))

    complaints = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "student/complaints.html",
        complaints=complaints,
        student=student,  
        message=message
    )


@app.route("/student/attendance")
def student_attendance():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    # 🔥 FETCH STUDENT (REQUIRED FOR NAVBAR)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    # Attendance data
    cursor.execute("""
        SELECT date, status
        FROM attendance
        WHERE student_id=%s
        ORDER BY date DESC
    """, (student_id,))

    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "student/attendance.html",
        records=records,
        student=student   
    )


@app.route("/student/food-order", methods=["GET", "POST"])
def student_food_order():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    # 🔥 FETCH STUDENT (IMPORTANT)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    message = None

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO food_orders (student_id, partner_id, order_details, order_status)
            VALUES (%s, %s, %s, %s)
        """, (
            student_id,
            request.form["partner_id"],
            request.form["order_details"],
            "Pending"
        ))
        conn.commit()
        message = ("success", "Order placed successfully") 

    cursor.execute("""
        SELECT * FROM food_orders
        WHERE student_id=%s
        ORDER BY order_id DESC
    """, (student_id,))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "student/food_order.html",
        orders=orders,
        message=message,
        student=student  
    )


@app.route("/student/fees")
def student_fees():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    # 🔥 FETCH STUDENT (IMPORTANT)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    # Fees data
    cursor.execute("""
        SELECT * FROM fees
        WHERE student_id=%s
        ORDER BY payment_date DESC
    """, (student_id,))

    fees = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "student/fees.html",
        fees=fees,
        student=student   
    )

@app.route("/student/announcements")
def student_announcements():
    if not login_required("STUDENT"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session.get("student_id")

    # 🔥 FETCH STUDENT (IMPORTANT)
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM announcements
        ORDER BY created_at DESC
    """)
    announcements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "student/announcements.html",
        announcements=announcements,
        student=student   
    )

# ── WARDEN ─────────────────────────────────────────────────────────────────────
@app.route("/warden/dashboard")
def warden_dashboard():
    if session.get("role") != "WARDEN":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total students
    cursor.execute("SELECT COUNT(*) AS count FROM students")
    total_students = cursor.fetchone()["count"]

    # Rooms
    cursor.execute("SELECT COUNT(*) AS total FROM rooms")
    total_rooms = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS occupied FROM rooms WHERE status='Occupied'")
    occupied_rooms = cursor.fetchone()["occupied"]

    cursor.execute("SELECT COUNT(*) AS available FROM rooms WHERE status='Available'")
    available_rooms = cursor.fetchone()["available"]

    # Complaints
    cursor.execute("SELECT COUNT(*) AS count FROM complaints WHERE status='Pending'")
    pending_complaints = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM complaints WHERE status='Resolved'")
    resolved_complaints = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM complaints WHERE status='Escalated'")
    escalated_complaints = cursor.fetchone()["count"]

    # Room requests pending
    room_requests = 0
    try:
        cursor.execute("SELECT COUNT(*) AS count FROM room_allocation WHERE status='Pending'")
        room_requests = cursor.fetchone()["count"]
    except Exception: pass

    # Attendance today
    cursor.execute("""
        SELECT COUNT(*) AS present
        FROM attendance
        WHERE DATE(date) = CURDATE() AND status='Present'
    """)
    present_today = cursor.fetchone()["present"]

    # Rooms with occupancy
    cursor.execute("""
    SELECT 
        r.room_number,
        r.capacity,
        COUNT(ra.student_id) AS occupied,
        r.status
    FROM rooms r
    LEFT JOIN room_allocation ra 
        ON r.room_id = ra.room_id AND ra.status='Approved'
    GROUP BY r.room_id
    """)
    rooms = cursor.fetchall()

    # Complaints list
    cursor.execute("""
        SELECT c.*, s.name, r.room_number
        FROM complaints c
        JOIN students s ON c.student_id = s.student_id
        LEFT JOIN room_allocation ra ON ra.student_id = s.student_id AND ra.status='Approved'
        LEFT JOIN rooms r ON r.room_id = ra.room_id
        ORDER BY c.created_at DESC
        LIMIT 5
    """)
    complaints = cursor.fetchall()

    # Students (DYNAMIC)
    cursor.execute("""
        SELECT s.student_id, s.name, r.room_number, 'Active' as status
        FROM students s
        LEFT JOIN room_allocation ra ON s.student_id = ra.student_id AND ra.status='Approved'
        LEFT JOIN rooms r ON r.room_id = ra.room_id
    """)
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "warden/dashboard.html",
        total_students=total_students,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        available_rooms=available_rooms,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints,
        escalated_complaints=escalated_complaints,
        room_requests=room_requests,
        present_today=present_today,
        rooms=rooms,
        complaints=complaints,
        students=students
    )


@app.route("/warden/complaints", methods=["GET","POST"])
def warden_complaints():
    if not login_required("WARDEN"): return redirect(url_for("login"))
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    message = None
    if request.method == "POST":
        cid    = request.form.get("complaint_id")
        action = request.form.get("action")
        if action == "resolve":
            cursor.execute("UPDATE complaints SET status='Resolved' WHERE complaint_id=%s", (cid,))
        elif action == "escalate":
            cursor.execute("UPDATE complaints SET status='Escalated', level='Admin' WHERE complaint_id=%s", (cid,))
        conn.commit()
        message = ("success", f"Complaint {action}d successfully.")
    cursor.execute("""
        SELECT c.*, s.name AS student_name FROM complaints c
        JOIN students s ON c.student_id=s.student_id
        WHERE c.level='Warden' ORDER BY c.created_at DESC""")
    complaints = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("warden/complaints.html", complaints=complaints, message=message)


@app.route("/warden/room-approval", methods=["GET","POST"])
def warden_room_approval():
    if not login_required("WARDEN"): return redirect(url_for("login"))
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    message = None
    if request.method == "POST":
        aid    = request.form.get("allocation_id")
        action = request.form.get("action")
        if action == "approve":
            cursor.execute("UPDATE room_allocation SET status='Approved' WHERE allocation_id=%s", (aid,))
            cursor.execute("""UPDATE rooms r JOIN room_allocation ra ON r.room_id=ra.room_id
                SET r.status='Occupied' WHERE ra.allocation_id=%s""", (aid,))
        elif action == "reject":
            cursor.execute("UPDATE room_allocation SET status='Rejected' WHERE allocation_id=%s", (aid,))
        conn.commit()
        message = ("success", f"Request {action}d successfully.")
    cursor.execute("""
        SELECT ra.allocation_id, s.name AS student_name, r.room_number, r.room_type, ra.status
        FROM room_allocation ra JOIN students s ON ra.student_id=s.student_id
        JOIN rooms r ON ra.room_id=r.room_id WHERE ra.status='Pending' ORDER BY ra.allocation_id DESC""")
    requests = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("warden/room_approval.html", requests=requests, message=message)

@app.route("/warden/announcements", methods=["GET", "POST"])
def warden_announcements():
    if session.get("role") != "WARDEN":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    message= None

    if request.method == "POST":
        title = request.form["title"]
        message = request.form["content"]

        cursor.execute("""
            INSERT INTO announcements (title, message)
            VALUES (%s, %s)
        """, (title, message))

        conn.commit()
        message = ("success", "Announcement posted")

    # Fetch all announcements
    cursor.execute("""
        SELECT * FROM announcements
        ORDER BY created_at DESC
    """)
    announcements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "warden/announcements.html",
        announcements=announcements,
        message=message
    )


# ── ADMIN ──────────────────────────────────────────────────────────────────────
@app.route("/admin/dashboard")
def admin_dashboard():
    if not login_required("ADMIN"): return redirect(url_for("login"))
    admin_id = session.get("admin_id")
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)

    # fetch admin profile
    admin = None
    try:
        cursor.execute("SELECT * FROM admins WHERE admin_id=%s", (admin_id,))
        admin = cursor.fetchone()
    except Exception: pass

    cursor.execute("SELECT COUNT(*) AS c FROM users")
    total_users = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM students")
    total_students = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM rooms WHERE status='Occupied'")
    occupied = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM rooms WHERE status='Available'")
    available_rooms = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM rooms")
    total_rooms = cursor.fetchone()["c"]
    occupancy_rate = int((occupied / total_rooms) * 100) if total_rooms else 0
    pending_payments = 0
    try:
        cursor.execute("SELECT COUNT(*) AS c FROM fees WHERE payment_status='Pending'")
        pending_payments = cursor.fetchone()["c"]
    except Exception: pass

    # Complaint stats for chart
    pending_complaints, resolved_complaints, escalated_complaints = 0, 0, 0
    try:
        cursor.execute("SELECT COUNT(*) AS c FROM complaints WHERE status='Pending'")
        pending_complaints = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM complaints WHERE status='Resolved'")
        resolved_complaints = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM complaints WHERE status='Escalated'")
        escalated_complaints = cursor.fetchone()["c"]
    except Exception: pass

    # Escalated complaints for admin to manage (US8 - Complaint Resolution)
    escalated_list = []
    try:
        cursor.execute("""
            SELECT c.*, s.name AS student_name
            FROM complaints c
            JOIN students s ON c.student_id = s.student_id
            WHERE c.level='Admin' OR c.status='Escalated'
            ORDER BY c.created_at DESC
        """)
        escalated_list = cursor.fetchall()
    except Exception: pass

    cursor.execute("SELECT w.name, w.designation, u.username FROM wardens w JOIN users u ON u.linked_warden_id=w.warden_id")
    wardens = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("admin/dashboard.html",
        admin=admin,
        total_users=total_users,
        total_students=total_students,
        total_rooms=total_rooms,
        available_rooms=available_rooms,
        occupied_rooms=occupied,
        occupancy_rate=occupancy_rate,
        pending_payments=pending_payments,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints,
        escalated_complaints=escalated_complaints,
        escalated_list=escalated_list,
        wardens=wardens)


@app.route("/admin/complaints", methods=["GET", "POST"])
def admin_complaints():
    if not login_required("ADMIN"): return redirect(url_for("login"))
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    message = None
    if request.method == "POST":
        cid    = request.form.get("complaint_id")
        action = request.form.get("action")
        if action == "resolve":
            cursor.execute("UPDATE complaints SET status='Resolved' WHERE complaint_id=%s", (cid,))
            conn.commit()
            message = ("success", "Complaint marked as Resolved.")
        elif action == "close":
            cursor.execute("UPDATE complaints SET status='Closed' WHERE complaint_id=%s", (cid,))
            conn.commit()
            message = ("success", "Complaint closed.")
    try:
        cursor.execute("""
            SELECT c.*, s.name AS student_name
            FROM complaints c
            JOIN students s ON c.student_id = s.student_id
            ORDER BY c.created_at DESC
        """)
        complaints = cursor.fetchall()
    except Exception:
        complaints = []
    cursor.close(); conn.close()
    return render_template("admin/complaints.html", complaints=complaints, message=message)


@app.route("/admin/rooms", methods=["GET", "POST"])
def admin_rooms():
    if not login_required("ADMIN"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    message = None

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO rooms (room_number, room_type, capacity, block, status)
            VALUES (%s, %s, %s, %s, 'Available')
        """, (
            request.form["room_number"],
            request.form["room_type"],
            request.form["capacity"],
            request.form["block"]
        ))
        conn.commit()

        message = ("success", "Room added successfully")

    cursor.execute("SELECT * FROM rooms ORDER BY room_number")
    rooms = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/rooms.html", rooms=rooms, message=message)


@app.route("/admin/students")
def admin_students():
    if not login_required("ADMIN"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.*, r.room_number
        FROM students s
        LEFT JOIN room_allocation ra 
            ON ra.student_id = s.student_id AND ra.status='Approved'
        LEFT JOIN rooms r 
            ON r.room_id = ra.room_id
        ORDER BY s.name
    """)

    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/students.html", students=students)


@app.route("/admin/reports")
def admin_reports():
    if not login_required("ADMIN"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total students
    cursor.execute("SELECT COUNT(*) AS count FROM students")
    total_students = cursor.fetchone()["count"]

    # Occupied rooms
    cursor.execute("SELECT COUNT(*) AS count FROM rooms WHERE status='Occupied'")
    occupied_rooms = cursor.fetchone()["count"]

    # Pending complaints
    cursor.execute("SELECT COUNT(*) AS count FROM complaints WHERE status='Pending'")
    pending_complaints = cursor.fetchone()["count"]

    # Pending fees
    cursor.execute("SELECT COUNT(*) AS count FROM fees WHERE payment_status='Pending'")
    pending_fees = cursor.fetchone()["count"]

    cursor.close()
    conn.close()

    return render_template(
        "admin/reports.html",
        total_students=total_students,
        occupied_rooms=occupied_rooms,
        pending_complaints=pending_complaints,
        pending_fees=pending_fees
    )


if __name__ == "__main__":
    app.run(debug=True)