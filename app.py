from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = 'ccsu_project_secret'  # Needed for sessions

def get_db_connection():
    # Path to the ca.pem file you downloaded from Aiven
    ca_path = os.path.join(os.path.dirname(__file__), 'ca.pem')
    
    return mysql.connector.connect(
        host="libflow-06-kmittal019-b41a.g.aivencloud.com",
        port=16294,
        user="avnadmin",
        password="AVNS_6xWY2Lh4vJWgyinZpks", # Paste your real Aiven password here
        database="defaultdb",
        ssl_ca=ca_path,
        ssl_verify_cert=True,
        autocommit=True
    )

@app.route('/')
def choice_page():
    session.clear()
    return render_template('choice.html')

@app.route('/set_role/<role>')
def set_role(role):
    session['role'] = role
    return render_template('login.html', role=role)

@app.route('/login_verify', methods=['POST'])
def login_verify():
    username = request.form.get('username')
    password = request.form.get('password')
    role = session.get('role')

    # Simple logic for Viva demo
    if role == 'admin' and username == 'admin' and password == 'admin123':
        session['logged_in'] = True
        return redirect(url_for('dashboard_view'))
    elif role == 'student' and username == 'student' and password == 'student123':
        session['logged_in'] = True
        return redirect(url_for('dashboard_view'))
    else:
        return "Invalid Credentials. <a href='/'>Try again</a>"

@app.route('/dashboard')
def dashboard_view():
    if not session.get('logged_in'):
        return redirect(url_for('choice_page'))

    role = session.get('role', 'student')
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch active books (Pagination)
        cursor.execute("SELECT id, title, author, category FROM books WHERE is_archived = 0 LIMIT %s OFFSET %s", (per_page, offset))
        active_books = cursor.fetchall()

        # 2. Total count for pagination
        cursor.execute("SELECT COUNT(*) FROM books WHERE is_archived = 0")
        total_active = cursor.fetchone()[0]
        total_pages = (total_active + per_page - 1) // per_page

        # 3. Vault (Archived)
        cursor.execute("SELECT id, title FROM books WHERE is_archived = 1")
        archived_books = cursor.fetchall()

        # 4. Student's own requests
        cursor.execute("SELECT book_title, status, request_date FROM requests WHERE student_name = %s ORDER BY request_date DESC", (role,))
        user_requests = cursor.fetchall()

        # 5. Admin Inbox (Only Pending)
        admin_requests = []
        if role == 'admin':
            cursor.execute("SELECT id, book_title, student_name FROM requests WHERE status = 'Pending'")
            admin_requests = cursor.fetchall()

        # 6. Stats for Dashboard Counters
        cursor.execute("SELECT COUNT(*) FROM requests WHERE status = 'Approved' AND DATE(request_date) = CURDATE()")
        issued_today = cursor.fetchone()[0]  
        
        cursor.execute("SELECT COUNT(*) FROM requests WHERE status = 'Pending'")
        pending_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return render_template('index.html', 
                               books=active_books,
                               role=role, 
                               requests=user_requests,
                               admin_requests=admin_requests,
                               archived=archived_books,
                               total_count=total_active,
                               current_page=page,
                               pending_count=pending_count,
                               total_pages=total_pages,
                               issued_today=issued_today)
    except Exception as e:
        return f"Database Error: {e}"

@app.route('/approve/<int:req_id>')
def approve_request(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'Approved' WHERE id = %s", (req_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard_view'))

@app.route('/reject/<int:req_id>')
def reject_request(req_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'Rejected' WHERE id = %s", (req_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard_view'))    

@app.route('/add', methods=['POST'])
def add_book():
    if session.get('role') != 'admin':
        return "Access Denied", 403
    title = request.form.get('title')
    author = request.form.get('author')
    category = request.form.get('category')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO books (title, author, category, is_archived) VALUES (%s, %s, %s, 0)"
        cursor.execute(query, (title, author, category))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error adding book: {e}")
    return redirect(url_for('dashboard_view'))

@app.route('/archive/<int:id>')
def archive_book(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE books SET is_archived = 1 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard_view'))

@app.route('/restore/<int:id>')
def restore_book(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE books SET is_archived = 0 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard_view'))

@app.route('/request/<int:book_id>')
def request_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM books WHERE id = %s", (book_id,))
    book_title = cursor.fetchone()[0]
    cursor.execute("INSERT INTO requests (book_id, book_title, student_name, status) VALUES (%s, %s, %s, 'Pending')", 
                   (book_id, book_title, session.get('role')))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard_view'))

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('choice_page'))
@app.route('/delete_permanent/<int:id>')
def delete_permanent(id):
    if session.get('role') != 'admin': 
        return "Unauthorized", 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Using lowercase 'books' to match your Aiven setup
        cursor.execute("DELETE FROM books WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error deleting book: {e}")
    return redirect(url_for('dashboard_view'))

if __name__ == '__main__':
    # Using 0.0.0.0 so you can still show it via mobile hotspot!
    app.run(host='0.0.0.0', port=5000, debug=True)