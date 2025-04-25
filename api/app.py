from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import os
import base64
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from datetime import datetime
from werkzeug.serving import run_simple
pymysql.install_as_MySQLdb()
import MySQLdb

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your_secret_key_here'

# MySQL Connection Setup
db = MySQLdb.connect(
    host="localhost",
    user="root",
    password="Nhla@1234",
    database="To_Do_List_Calender"
)

# File upload setup
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    # Get total number of users
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']

    # Get testimonials with user names
    cursor.execute("""
        SELECT t.message, u.first_name, u.surname
        FROM testimonials t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC
    """)
    testimonials = cursor.fetchall()

    return render_template('index.html', total_users=total_users, testimonials=testimonials)



def save_profile_picture(file, first_name):
    # Create a directory named after the user's first name
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(first_name))
    os.makedirs(user_folder, exist_ok=True)  # Create the folder if it doesn't exist

    # Generate a secure filename
    filename = secure_filename(file.filename)
    file_path = os.path.join(user_folder, filename)
    
    # Save the file
    file.save(file_path)
    return file_path


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        password = request.form.get('password')
        profile_picture = request.files.get('profile_picture')

        # Basic validation
        if not all([first_name, surname, email, password]):
            flash('All fields are required.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        
        # Save profile picture and get the file path
        picture_path = None
        if profile_picture:
            picture_path = save_profile_picture(profile_picture, first_name)

        cursor = db.cursor(MySQLdb.cursors.DictCursor)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash('Email already registered. Please login or use another email.', 'warning')
                return redirect(url_for('register'))

            cursor.execute(
                "INSERT INTO users (first_name, surname, email, password, profile_picture) VALUES (%s, %s, %s, %s, %s)",
                (first_name, surname, email, hashed_password, picture_path)
            )
            db.commit()
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('success', first_name=first_name))
        except Exception as e:
            db.rollback()
            print("[ERROR] Registration failed:", e)
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')




@app.route('/success')
def success():
    first_name = request.args.get('first_name')  # Get first name from URL query params
    if not first_name:
        return redirect(url_for('home'))  # If no name found, redirect to home
    return render_template('success.html', first_name=first_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user'] = user
            return redirect(url_for('calendar'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/submit_testimonial', methods=['POST'])
def submit_testimonial():
    user = session.get('user')
    if not user:
        flash('You must be logged in to submit a testimonial.', 'danger')
        return redirect(url_for('login'))

    testimonial = request.form.get('testimonial')
    
    if not testimonial:
        flash('Please write something in your testimonial.', 'warning')
        return redirect(url_for('calendar'))

    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO testimonials (user_id, message) VALUES (%s, %s)",
            (user['id'], testimonial)
        )
        db.commit()
        # 🎯 Redirect to the testimonial success screen
        return redirect(url_for('testimonial_success'))
    except Exception as e:
        db.rollback()
        print("[ERROR] Testimonial submission failed:", e)
        flash('An error occurred while submitting your testimonial.', 'danger')

    return redirect(url_for('calendar'))

@app.route('/testimonial_success')
def testimonial_success():
    return render_template('testimonial_success.html')



@app.route('/add_task', methods=['POST'])
def add_task():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = request.json
    name = data.get('name')
    description = data.get('description')
    priority = data.get('priority')
    due_date = data.get('due_date')  # In ISO format from datetime-local input

    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO tasks (user_id, name, description, priority, due_date, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
            """,
            (user['id'], name, description, priority, due_date)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Task added'})
    except Exception as e:
        db.rollback()
        print("[ERROR] Failed to add task:", e)
        return jsonify({'success': False, 'message': 'Failed to add task'}), 500
    
@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401

    task_id = request.form.get('task_id')
    status = request.form.get('status')

    if not task_id or not status:
        return jsonify({'success': False, 'message': 'Missing task ID or status'}), 400

    try:
        cursor = db.cursor()
        cursor.execute(
            "UPDATE tasks SET status = %s WHERE user_id = %s AND id = %s",
            (status, user['id'], task_id)
        )
        db.commit()

        # Always return success regardless of whether the row was affected
        return jsonify({'success': True})

    except Exception as e:
        db.rollback()
        print("[ERROR] Failed to update task status:", e)
        return jsonify({'success': False}), 500


@app.route('/calendar')
def calendar():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    # 1. Update missed tasks
    cursor.execute("""
        UPDATE tasks
        SET status = 'missed'
        WHERE user_id = %s AND due_date < NOW() AND status = 'pending'
    """, (user['id'],))
    db.commit()

    # 2. Fetch only active (not done or expired) tasks
    cursor.execute("""
        SELECT * FROM tasks
        WHERE user_id = %s AND status = 'pending'
        ORDER BY due_date ASC
    """, (user['id'],))
    tasks = cursor.fetchall()

    current_time = datetime.now()

    return render_template('calendar.html', user=user, tasks=tasks, current_time=current_time)
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

# Serverless setup
if __name__ == '__main__':
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app)
    run_simple('0.0.0.0', 5000, app)
