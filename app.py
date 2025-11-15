from flask import Flask, render_template, request, redirect, url_for, session, send_file
import json
import os
import base64
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

USER_DATA_FILE = 'users.json'
FILES_DATA_FILE = 'user_files.json'
MAX_STORAGE_BYTES = 20 * 1024 * 1024  # 20 MB per user

# Initialize JSON files
for f in [USER_DATA_FILE, FILES_DATA_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            json.dump({} if 'files' in f else [], file)

# ---------------- Functions ----------------
def load_users():
    with open(USER_DATA_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_files():
    with open(FILES_DATA_FILE, 'r') as f:
        return json.load(f)

def save_files(files_data):
    with open(FILES_DATA_FILE, 'w') as f:
        json.dump(files_data, f, indent=4)

def get_user_storage(email):
    files_data = load_files()
    user_files = files_data.get(email, [])
    total_size = sum(f['size'] for f in user_files)
    return total_size, len(user_files)

# ---------------- Routes ----------------
@app.route('/')
def home():
    return redirect(url_for('login') if 'email' not in session else url_for('dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        users = load_users()
        user = next((u for u in users if u['email']==email and u['password']==password), None)
        if user:
            session['email'] = email
            return redirect(url_for('dashboard'))
        else:
            error='Invalid email or password'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET','POST'])
def register():
    error = None
    if request.method=='POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        users = load_users()
        if any(u['email']==email for u in users):
            error='Email already registered'
        else:
            users.append({'name':name,'email':email,'password':password,'phone':phone,'address':address,'registered_at':datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            save_users(users)
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session: return redirect(url_for('login'))
    email = session['email']
    users = load_users()
    user = next((u for u in users if u['email']==email), None)
    used_bytes, files_count = get_user_storage(email)
    remaining_bytes = MAX_STORAGE_BYTES - used_bytes
    storage_percent = int((used_bytes / MAX_STORAGE_BYTES)*100)
    return render_template('dashboard.html',
                           user=user,
                           used_mb=f"{used_bytes/1024/1024:.2f}",
                           remaining_mb=f"{remaining_bytes/1024/1024:.2f}",
                           files_count=files_count,
                           storage_percent=storage_percent)

@app.route('/files', methods=['GET','POST'])
def files_page():
    if 'email' not in session: return redirect(url_for('login'))
    email = session['email']
    message = None
    error = None
    if request.method=='POST':
        if 'file' not in request.files:
            error='No file part'
        else:
            file = request.files['file']
            if file.filename=='':
                error='No selected file'
            else:
                files_data = load_files()
                user_files = files_data.get(email, [])
                file_bytes = file.read()
                if sum(f['size'] for f in user_files) + len(file_bytes) > MAX_STORAGE_BYTES:
                    error='Storage limit exceeded'
                else:
                    user_files.append({'name':file.filename,
                                       'data':base64.b64encode(file_bytes).decode('utf-8'),
                                       'size':len(file_bytes),
                                       'uploaded_at':datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                    files_data[email]=user_files
                    save_files(files_data)
                    message='File uploaded successfully'
    files_data = load_files()
    user_files = files_data.get(email, [])
    used_bytes = sum(f['size'] for f in user_files)
    remaining_bytes = MAX_STORAGE_BYTES - used_bytes
    storage_percent = int((used_bytes / MAX_STORAGE_BYTES)*100)
    return render_template('files.html',
                           files=user_files,
                           used_mb=f"{used_bytes/1024/1024:.2f}",
                           remaining_mb=f"{remaining_bytes/1024/1024:.2f}",
                           files_count=len(user_files),
                           storage_percent=storage_percent,
                           message=message,
                           error=error)

@app.route('/logout')
def logout():
    session.pop('email',None)
    return redirect(url_for('login'))

@app.route('/download/<email>/<filename>')
def download_file(email,filename):
    files_data = load_files()
    user_files = files_data.get(email,[])
    file_entry = next((f for f in user_files if f['name']==filename),None)
    if file_entry:
        return send_file(BytesIO(base64.b64decode(file_entry['data'])), download_name=filename, as_attachment=True)
    return "File not found",404

@app.route('/delete/<email>/<filename>', methods=['POST'])
def delete_file(email,filename):
    files_data = load_files()
    user_files = files_data.get(email,[])
    user_files = [f for f in user_files if f['name']!=filename]
    files_data[email] = user_files
    save_files(files_data)
    return redirect(url_for('files_page'))

if __name__=="__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)