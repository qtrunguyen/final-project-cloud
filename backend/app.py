from flask import Flask, request, session, jsonify, render_template
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
import csv
from psycopg2 import connect, sql, Error
import io
import base64
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = os.urandom(24)

# Configuration
app.config['UPLOAD_FOLDER'] = "C:/Users/trung/Documents/Project/final-project-cloud/backend/uploads" # Specify the directory to store uploaded files
DATABASE_URL = "postgresql://postgres:123456@localhost/postgres"

try:
    conn = connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(sql.SQL("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """))
    conn.commit()
    print("Table created successfully")
except Error as e:
    print(f"Error: {str(e)}")
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.json.get("username")
    password = request.json.get("password")
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(sql.SQL("INSERT INTO users (username, password) VALUES (%s, %s)"), (username, hashed_password))
        conn.commit()
        return jsonify({'success': 'User created successfully'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    try:
        conn = connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(sql.SQL("SELECT * FROM users WHERE username = %s"), (username,))
        user = cur.fetchone()

        if user and bcrypt.check_password_hash(user[2], password):
            session['user_id'] = user[0]
            return jsonify({'success': 'Logged in successfully'}), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    except Error as e:
        return jsonify({'error': str(e)}), 400

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': 'Logged out successfully'}), 200

# Upload Endpoint
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        insert_into_postgres(filename)
        return jsonify({'success': 'File uploaded successfully'})

    return jsonify({'error': 'File type not allowed'})

import psycopg2


@app.route('/uploaded_data', methods=['GET'])
def get_uploaded_data():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()

    cursor.execute("SELECT hshd_num, l, * FROM uploaded_data LIMIT 100")  
    data = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]

    # Create a list of dictionaries where each dictionary represents a row
    result = [dict(zip(column_names, row)) for row in data]

    return jsonify(result)


@app.route('/search_data', methods=['GET'])
def search_data():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()

    hshd_num = request.args.get('hshd_num')

    if hshd_num:
        # If hshd_num is provided, fetch rows matching the hshd_num
        cursor.execute("SELECT * FROM uploaded_data WHERE hshd_num = %s LIMIT 100", (hshd_num,))
    else:
        # If hshd_num is not provided, fetch the first 100 rows
        cursor.execute("SELECT * FROM uploaded_data LIMIT 100")

    data = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]

    # Create a list of dictionaries where each dictionary represents a row
    result = [dict(zip(column_names, row)) for row in data]

    print(column_names)
    return jsonify(result)

@app.route('/plot', methods=['GET'])
def plot():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()

    # Fetch data for household size vs spend
    cursor.execute("SELECT hh_size, spend FROM uploaded_data")  
    data = cursor.fetchall()

    # Extract hh_size and spend values from the data
    hh_size = [row[0] for row in data]
    spend = [row[1] for row in data]

    # Create the plot for household size vs spend
    fig_hh_size = Figure()
    axis_hh_size = fig_hh_size.add_subplot(1, 1, 1)
    axis_hh_size.scatter(hh_size, spend)
    axis_hh_size.set_xlabel('Household Size')
    axis_hh_size.set_ylabel('Spend')

    # Convert the plot to a PNG image
    output_hh_size = io.BytesIO()
    FigureCanvas(fig_hh_size).print_png(output_hh_size)

    # Encode the PNG image as a base64 string
    plot_data_hh_size = output_hh_size.getvalue()

    # Pass the encoded plot data to the template for household size vs spend
    plot_url_hh_size = "data:image/png;base64," + base64.b64encode(plot_data_hh_size).decode()

    # Fetch data for children vs spend
    cursor.execute("SELECT children, spend FROM uploaded_data")  
    data_children = cursor.fetchall()

    # Extract children and spend values from the data
    children = [row[0] for row in data_children]
    spend_children = [row[1] for row in data_children]

    # Create the plot for children vs spend
    fig_children = Figure()
    axis_children = fig_children.add_subplot(1, 1, 1)
    axis_children.scatter(children, spend_children)
    axis_children.set_xlabel('Number of Children')
    axis_children.set_ylabel('Spend')

    # Convert the plot to a PNG image
    output_children = io.BytesIO()
    FigureCanvas(fig_children).print_png(output_children)

    # Encode the PNG image as a base64 string
    plot_data_children = output_children.getvalue()

    # Pass the encoded plot data to the template for children vs spend
    plot_url_children = "data:image/png;base64," + base64.b64encode(plot_data_children).decode()

    # Fetch data for income range vs spend
    cursor.execute("SELECT income_range, spend FROM uploaded_data")  
    data_income_range = cursor.fetchall()

    # Extract income range and spend values from the data
    income_range = [row[0] for row in data_income_range]
    spend_income_range = [row[1] for row in data_income_range]

    # Create the plot for income range vs spend
    fig_income_range = Figure()
    axis_income_range = fig_income_range.add_subplot(1, 1, 1)
    axis_income_range.scatter(income_range, spend_income_range)
    axis_income_range.set_xlabel('Income Range')
    axis_income_range.set_ylabel('Spend')

    # Convert the plot to a PNG image
    output_income_range = io.BytesIO()
    FigureCanvas(fig_income_range).print_png(output_income_range)

    # Encode the PNG image as a base64 string
    plot_data_income_range = output_income_range.getvalue()

    # Pass the encoded plot data to the template for income range vs spend
    plot_url_income_range = "data:image/png;base64," + base64.b64encode(plot_data_income_range).decode()

    return render_template('plot.html', plot_url_hh_size=plot_url_hh_size, plot_url_children=plot_url_children, plot_url_income_range=plot_url_income_range)


# Helper function to check if the file type is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}


# Helper function to insert data into PostgreSQL
def insert_into_postgres(filename):
    connection = connect(DATABASE_URL)
    cursor = connection.cursor()

    cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'uploaded_data')")
    table_exists = cursor.fetchone()[0]

    if table_exists:
        # Truncate the table to remove old data
        cursor.execute("TRUNCATE TABLE uploaded_data")

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)  
        column_definitions = []
        for column_name in header:
            column_definitions.append(f"{column_name} TEXT")  # Assuming all columns are TEXT type for simplicity

        create_table_query = f"CREATE TABLE IF NOT EXISTS uploaded_data ({', '.join(column_definitions)})"
        cursor.execute(create_table_query)
        
        for row in reader:
            placeholders = ', '.join(['%s' for _ in row])
            insert_query = f"INSERT INTO uploaded_data VALUES ({placeholders})"
            cursor.execute(insert_query, row)

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == '__main__':
    app.run(debug=True)
