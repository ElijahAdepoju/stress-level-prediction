import numpy as np
import pandas as pd
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO, StringIO
import re
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score, accuracy_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stress_predictor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

db = SQLAlchemy(app)

ALLOWED_UPLOAD_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
REQUIRED_COLUMNS = [
    'anxiety_level',
    'mental_health_history',
    'depression',
    'headache',
    'sleep_quality',
    'breathing_problem',
    'living_conditions',
    'academic_performance',
    'study_load',
    'future_career_concerns',
    'extracurricular_activities',
]
OPTIONAL_COLUMNS = ['stress_level', 'timestamp']


def ensure_upload_folder():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_upload_file(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_UPLOAD_EXTENSIONS


def normalize_column_name(name):
    name = name.strip().lower().replace(' ', '_').replace('-', '_')
    name = re.sub(r'[^a-z0-9_]', '', name)
    special_map = {
        'stresslevel': 'stress_level',
        'mentalhealthhistory': 'mental_health_history',
        'sleepquality': 'sleep_quality',
        'breathingproblem': 'breathing_problem',
        'livingconditions': 'living_conditions',
        'academicperformance': 'academic_performance',
        'studyload': 'study_load',
        'futurecareerconcerns': 'future_career_concerns',
        'extracurricularactivities': 'extracurricular_activities',
    }
    return special_map.get(name, name)


def _escape_pdf_text(value):
    """Escape special characters for PDF text content streams."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _build_simple_pdf(pages_lines):
    """Build a simple multi-page PDF without external dependencies."""
    objects = []
    page_ids = []

    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [] /Count 0 >>")

    for page_lines in pages_lines:
        content_parts = ["BT", "/F1 9 Tf"]
        y = 800
        for line in page_lines:
            safe_line = _escape_pdf_text(line)
            content_parts.append(f"1 0 0 1 40 {y} Tm ({safe_line}) Tj")
            y -= 14
        content_parts.append("ET")
        content = "\n".join(content_parts) + "\n"
        content_len = len(content.encode("latin-1", errors="replace"))

        content_obj_id = len(objects) + 1
        objects.append(f"<< /Length {content_len} >>\nstream\n{content}endstream")

        page_obj_id = len(objects) + 1
        page_ids.append(page_obj_id)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            f"/Resources << /Font << /F1 {{font_obj_id}} 0 R >> >> "
            f"/Contents {content_obj_id} 0 R >>"
        )

    font_obj_id = len(objects) + 1
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i, obj in enumerate(objects):
        if "{font_obj_id}" in obj:
            objects[i] = obj.replace("{font_obj_id}", str(font_obj_id))

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body_chunks = []
    offsets = [0]
    cursor = len(header)

    for idx, obj in enumerate(objects, start=1):
        chunk = f"{idx} 0 obj\n{obj}\nendobj\n".encode("latin-1", errors="replace")
        body_chunks.append(chunk)
        offsets.append(cursor)
        cursor += len(chunk)

    body = b"".join(body_chunks)
    xref_start = len(header) + len(body)

    xref_lines = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    for i in range(1, len(offsets)):
        xref_lines.append(f"{offsets[i]:010d} 00000 n \n")
    xref = "".join(xref_lines).encode("latin-1")

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF"
    ).encode("latin-1")

    return header + body + xref + trailer

# ==================== Database Models ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stress_records = db.relationship('StressRecord', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class StressRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    anxiety_level = db.Column(db.Float)
    mental_health_history = db.Column(db.Float)
    depression = db.Column(db.Float)
    headache = db.Column(db.Float)
    sleep_quality = db.Column(db.Float)
    breathing_problem = db.Column(db.Float)
    living_conditions = db.Column(db.Float)
    academic_performance = db.Column(db.Float)
    study_load = db.Column(db.Float)
    future_career_concerns = db.Column(db.Float)
    extracurricular_activities = db.Column(db.Float)
    stress_level = db.Column(db.Integer)


# ==================== Load and Train Models ====================

def load_and_train_models():
    """Load dataset and train all ML models"""
    print("=" * 50)
    print("LOADING AND TRAINING MODELS...")
    print("=" * 50)
    try:
        data = pd.read_csv("StressLevelDataset.csv")
        print(f"[OK] Dataset loaded: {data.shape}")
        
        encoder = LabelEncoder()
        data["stress_level"] = encoder.fit_transform(data["stress_level"])
        print(f"[OK] Labels encoded. Classes: {encoder.classes_}")

        X = data.drop("stress_level", axis=1)
        y = data["stress_level"]
        print(f"[OK] Features shape: {X.shape}, Target shape: {y.shape}")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        print(f"[OK] Train/Test split done: {X_train.shape}, {X_test.shape}")

        # Scale features for SVM
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        feature_names = list(X.columns)

        # Train Decision Tree
        print("Training Decision Tree...")
        tree_clf = DecisionTreeClassifier(max_depth=7, random_state=100)
        tree_clf.fit(X_train, y_train)
        tree_pred = tree_clf.predict(X_test)
        tree_score = accuracy_score(y_test, tree_pred)
        print(f"[OK] Decision Tree trained. Accuracy: {tree_score:.4f}")

        # Train Random Forest
        print("Training Random Forest...")
        forest_clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=100)
        forest_clf.fit(X_train, y_train)
        forest_pred = forest_clf.predict(X_test)
        forest_score = accuracy_score(y_test, forest_pred)
        print(f"[OK] Random Forest trained. Accuracy: {forest_score:.4f}")

        # Train SVM
        print("Training SVM...")
        svm_clf = SVC(kernel='rbf', random_state=100)
        svm_clf.fit(X_train_scaled, y_train)
        svm_pred = svm_clf.predict(X_test_scaled)
        svm_score = accuracy_score(y_test, svm_pred)
        print(f"[OK] SVM trained. Accuracy: {svm_score:.4f}")

        # Train Gradient Boosting
        print("Training Gradient Boosting...")
        gbm_clf = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=100)
        gbm_clf.fit(X_train, y_train)
        gbm_pred = gbm_clf.predict(X_test)
        gbm_score = accuracy_score(y_test, gbm_pred)
        print(f"[OK] Gradient Boosting trained. Accuracy: {gbm_score:.4f}")

        print("=" * 50)
        print("ALL MODELS TRAINED SUCCESSFULLY!")
        print("=" * 50)
        
        def metrics_for(y_true, y_pred):
            return {
                'accuracy': float(accuracy_score(y_true, y_pred)),
                'precision': float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
                'recall': float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
                'f1': float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
                'confusion': confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()
            }

        return {
            'tree': tree_clf,
            'forest': forest_clf,
            'svm': svm_clf,
            'gbm': gbm_clf,
            'scaler': scaler,
            'encoder': encoder,
            'feature_names': feature_names,
            'feature_importances': {
                'tree': tree_clf.feature_importances_.tolist(),
                'forest': forest_clf.feature_importances_.tolist(),
                'gbm': gbm_clf.feature_importances_.tolist()
            },
            'metrics': {
                'tree': metrics_for(y_test, tree_pred),
                'forest': metrics_for(y_test, forest_pred),
                'svm': metrics_for(y_test, svm_pred),
                'gbm': metrics_for(y_test, gbm_pred)
            },
            'scores': {
                'tree': tree_score,
                'forest': forest_score,
                'svm': svm_score,
                'gbm': gbm_score
            }
        }
    except Exception as e:
        print(f"[ERROR] ERROR loading models: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


models = {}
scaler = None
encoder = None
model_scores = {}
model_metrics = {}
feature_names = []
feature_importances = {}

if os.environ.get("SKIP_MODEL_TRAINING") == "1":
    print("[INFO] SKIP_MODEL_TRAINING=1, skipping model training at startup.")
else:
    models_data = load_and_train_models()
    models = {
        'tree': models_data['tree'],
        'forest': models_data['forest'],
        'svm': models_data['svm'],
        'gbm': models_data['gbm']
    }
    scaler = models_data['scaler']
    encoder = models_data['encoder']
    model_scores = models_data['scores']
    model_metrics = models_data.get('metrics', {})
    feature_names = models_data.get('feature_names', [])
    feature_importances = models_data.get('feature_importances', {})

    print(f"[OK] Models dictionary initialized with keys: {list(models.keys())}")
    print(f"[OK] Encoder initialized with classes: {encoder.classes_}")
    print(f"[OK] Model scores: {model_scores}")
    print("[OK] App startup completed successfully!")

# ==================== Authentication Decorators ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Route function is login_page; use correct endpoint name.
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== Routes ====================

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page - redirects to prediction if logged in"""
    if 'user_id' in session:
        return redirect(url_for('predict'))
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """User login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
            return render_template('login.html', error=error)

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validation
        if not username or not email or not password:
            error = 'All fields are required'
            return render_template('register.html', error=error)

        if password != confirm_password:
            error = 'Passwords do not match'
            return render_template('register.html', error=error)

        if User.query.filter_by(username=username).first():
            error = 'Username already exists'
            return render_template('register.html', error=error)

        if User.query.filter_by(email=email).first():
            error = 'Email already registered'
            return render_template('register.html', error=error)

        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['username'] = new_user.username
        return redirect(url_for('predict'))

    return render_template('register.html')


@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    """Stress level prediction page"""
    if request.method == 'POST':
        try:
            print("=" * 50)
            print("PREDICT REQUEST RECEIVED")
            print("=" * 50)
            
            # Get user input from the form
            anxiety_level = float(request.form.get('anxiety_level'))
            mental_health_history = float(request.form.get('mental_health_history'))
            depression = float(request.form.get('depression'))
            headache = float(request.form.get('headache'))
            sleep_quality = float(request.form.get('sleep_quality'))
            breathing_problem = float(request.form.get('breathing_problem'))
            living_conditions = float(request.form.get('living_conditions'))
            academic_performance = float(request.form.get('academic_performance'))
            study_load = float(request.form.get('study_load'))
            future_career_concerns = float(request.form.get('future_career_concerns'))
            extracurricular_activities = float(request.form.get('extracurricular_activities'))

            print(f"[OK] Form inputs received successfully")
            
            # Prepare input
            user_input = np.array([[anxiety_level, mental_health_history, depression, headache, sleep_quality,
                                    breathing_problem, living_conditions, academic_performance, study_load,
                                    future_career_concerns, extracurricular_activities]])

            print(f"[OK] User input prepared: {user_input.shape}")
            
            # Get predictions from all models
            print(f"Making predictions with models...")
            tree_pred = encoder.inverse_transform([models['tree'].predict(user_input)[0]])[0]
            print(f"  - Tree prediction: {tree_pred}")
            
            forest_pred = encoder.inverse_transform([models['forest'].predict(user_input)[0]])[0]
            print(f"  - Forest prediction: {forest_pred}")
            
            # SVM needs scaled input
            user_input_scaled = scaler.transform(user_input)
            svm_pred = encoder.inverse_transform([models['svm'].predict(user_input_scaled)[0]])[0]
            print(f"  - SVM prediction: {svm_pred}")
            
            gbm_pred = encoder.inverse_transform([models['gbm'].predict(user_input)[0]])[0]
            print(f"  - GBM prediction: {gbm_pred}")

            # Choose which model to display (default: decision tree)
            selected_model = session.get('selected_model', 'tree')
            selected_model_name = {
                'tree': 'Decision Tree',
                'forest': 'Random Forest',
                'svm': 'Support Vector Machine',
                'gbm': 'Gradient Boosting',
            }.get(selected_model, 'Decision Tree')

            selected_pred = {
                'tree': tree_pred,
                'forest': forest_pred,
                'svm': svm_pred,
                'gbm': gbm_pred,
            }.get(selected_model, tree_pred)

            def to_label(pred):
                # Normalize model output into a consistent label: low/medium/high
                if isinstance(pred, str):
                    label = pred.strip().lower()
                    for key in ('low', 'medium', 'high'):
                        if label.startswith(key):
                            return key
                    return label
                try:
                    if encoder is not None:
                        decoded = encoder.inverse_transform([int(pred)])[0]
                        # decoded may be numeric depending on dataset encoding
                        if isinstance(decoded, str):
                            return decoded.strip().lower()
                        pred = decoded
                except Exception:
                    pass
                try:
                    num = int(pred)
                except Exception:
                    return str(pred)
                return {0: 'low', 1: 'medium', 2: 'high'}.get(num, str(pred))

            selected_label = to_label(selected_pred)
            selected_value = {'low': 0, 'medium': 1, 'high': 2}.get(str(selected_label).lower(), None)

            # Simple recommendations based on numeric stress level
            if selected_value == 0:
                recommendation = (
                    "Your stress level is currently low. "
                    "Keep up your healthy routine and continue monitoring regularly. "
                    "No immediate action is required at this time."
                )
            elif selected_value == 1:
                recommendation = (
                    "Your stress level is moderate. "
                    "Consider taking short breaks, staying hydrated, and reducing workload where possible. "
                    "Monitor your stress level closely to prevent escalation."
                )
            else:
                recommendation = (
                    "Your stress level is high. "
                    "Immediate action is recommended. Take time to rest, reduce stress triggers, "
                    "and seek professional or medical support if necessary. "
                    "Continuous monitoring is strongly advised."
                )

            # Store in database
            print(f"Saving to database...")
            record = StressRecord(
                user_id=session['user_id'],
                anxiety_level=anxiety_level,
                mental_health_history=mental_health_history,
                depression=depression,
                headache=headache,
                sleep_quality=sleep_quality,
                breathing_problem=breathing_problem,
                living_conditions=living_conditions,
                academic_performance=academic_performance,
                study_load=study_load,
                future_career_concerns=future_career_concerns,
                extracurricular_activities=extracurricular_activities,
                stress_level=selected_value
            )
            db.session.add(record)
            db.session.commit()
            print(f"[OK] Record saved successfully with ID: {record.id}")

            print(f"Rendering result template...")
            return render_template('result.html',
                                   selected_model=selected_model_name,
                                   selected_stress=selected_label,
                                   recommendation=recommendation)
        except ValueError as e:
            print(f"[ERROR] ValueError in predict: {e}")
            error_message = "Invalid input. Please enter numeric values for all fields."
            return render_template('error.html', error_message=error_message), 400
        except KeyError as e:
            print(f"[ERROR] KeyError in predict: {e}")
            error_message = f"Missing form field: {str(e)}"
            return render_template('error.html', error_message=error_message), 400
        except Exception as e:
            print(f"[ERROR] Error in predict: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            error_message = f"An error occurred while processing your prediction: {str(e)}"
            return render_template('error.html', error_message=error_message), 500

    return render_template('predict.html')


@app.route('/model', methods=['GET', 'POST'])
@login_required
def model():
    """Select default model used for displaying results"""
    if request.method == 'POST':
        selected = request.form.get('selected_model', 'tree')
        if selected not in {'tree', 'forest', 'svm', 'gbm'}:
            selected = 'tree'
        session['selected_model'] = selected
        return redirect(url_for('predict'))

    current_model = session.get('selected_model', 'tree')
    return render_template('model.html', current_model=current_model)


@app.route('/history-data')
@login_required
def history_data():
    """API endpoint for chart data"""
    try:
        user_id = session['user_id']
        records = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.asc()).all()
        
        # Prepare data for trend chart (count of each stress level over time)
        data = {
            'dates': [record.timestamp.strftime('%Y-%m-%d %H:%M') for record in records],
            'stress_values': [record.stress_level for record in records],
            'low_stress': [1 if record.stress_level == 0 else 0 for record in records],
            'medium_stress': [1 if record.stress_level == 1 else 0 for record in records],
            'high_stress': [1 if record.stress_level == 2 else 0 for record in records],
        }
        
        return jsonify(data)
    except Exception as e:
        print(f"History data error: {e}")
        return jsonify({'error': 'Failed to load history data'}), 500


@app.route('/uploads', methods=['GET'])
@login_required
def uploads():
    """Uploads page for managing records and file imports/exports"""
    user_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    per_page = 5
    pagination = StressRecord.query.filter_by(user_id=user_id)\
        .order_by(StressRecord.timestamp.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    message = request.args.get('msg')
    message_type = request.args.get('type', 'info')
    return render_template(
        'uploads.html',
        records=pagination.items,
        pagination=pagination,
        message=message,
        message_type=message_type
    )


@app.route('/uploads/import', methods=['POST'])
@login_required
def uploads_import():
    """Import records from CSV or Excel"""
    try:
        ensure_upload_folder()
        upload = request.files.get('data_file')
        if upload is None or upload.filename == '':
            records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).all()
            return render_template('uploads.html', records=records, message='No file selected.', message_type='danger'), 400

        if not allowed_upload_file(upload.filename):
            records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).all()
            return render_template('uploads.html', records=records, message='Unsupported file type.', message_type='danger'), 400

        _, ext = os.path.splitext(upload.filename.lower())
        if ext == '.csv':
            df = pd.read_csv(upload)
        else:
            df = pd.read_excel(upload)

        if df.empty:
            records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).all()
            return render_template('uploads.html', records=records, message='Uploaded file is empty.', message_type='danger'), 400

        normalized_columns = {col: normalize_column_name(col) for col in df.columns}
        df = df.rename(columns=normalized_columns)

        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).all()
            message = f"Missing required columns: {', '.join(missing)}"
            return render_template('uploads.html', records=records, message=message, message_type='danger'), 400

        for col in REQUIRED_COLUMNS + ['stress_level']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        inserted = 0
        skipped = 0
        selected_model = session.get('selected_model', 'tree')

        for _, row in df.iterrows():
            if any(pd.isna(row[col]) for col in REQUIRED_COLUMNS):
                skipped += 1
                continue

            user_input = np.array([[
                float(row['anxiety_level']),
                float(row['mental_health_history']),
                float(row['depression']),
                float(row['headache']),
                float(row['sleep_quality']),
                float(row['breathing_problem']),
                float(row['living_conditions']),
                float(row['academic_performance']),
                float(row['study_load']),
                float(row['future_career_concerns']),
                float(row['extracurricular_activities'])
            ]])

            predicted_stress = None
            if models and selected_model in models:
                try:
                    if selected_model == 'svm' and scaler is not None:
                        user_input_model = scaler.transform(user_input)
                    else:
                        user_input_model = user_input
                    model_pred = models[selected_model].predict(user_input_model)[0]
                    predicted_label = encoder.inverse_transform([model_pred])[0] if encoder is not None else model_pred
                    if isinstance(predicted_label, str):
                        predicted_label = predicted_label.strip().lower()
                        predicted_stress = {'low': 0, 'medium': 1, 'high': 2}.get(predicted_label)
                    else:
                        predicted_stress = int(predicted_label)
                except Exception:
                    predicted_stress = None

            record = StressRecord(
                user_id=session['user_id'],
                anxiety_level=float(row['anxiety_level']),
                mental_health_history=float(row['mental_health_history']),
                depression=float(row['depression']),
                headache=float(row['headache']),
                sleep_quality=float(row['sleep_quality']),
                breathing_problem=float(row['breathing_problem']),
                living_conditions=float(row['living_conditions']),
                academic_performance=float(row['academic_performance']),
                study_load=float(row['study_load']),
                future_career_concerns=float(row['future_career_concerns']),
                extracurricular_activities=float(row['extracurricular_activities']),
                stress_level=int(row['stress_level']) if 'stress_level' in df.columns and not pd.isna(row['stress_level']) else predicted_stress
            )

            if 'timestamp' in df.columns and pd.notna(row['timestamp']):
                record.timestamp = row['timestamp'].to_pydatetime()

            db.session.add(record)
            inserted += 1

        db.session.commit()
        records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).limit(10).all()
        message = f"Imported {inserted} records. Skipped {skipped} rows with missing data."
        return render_template('uploads.html', records=records, message=message, message_type='info')
    except Exception as e:
        db.session.rollback()
        records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).limit(10).all()
        return render_template('uploads.html', records=records, message=f"Import failed: {str(e)}", message_type='danger'), 500


@app.route('/uploads/export/csv')
@login_required
def uploads_export_csv():
    """Export records to CSV"""
    user_id = session['user_id']
    records = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.asc()).all()
    data = [{
        'id': r.id,
        'timestamp': r.timestamp.isoformat() if r.timestamp else None,
        'anxiety_level': r.anxiety_level,
        'mental_health_history': r.mental_health_history,
        'depression': r.depression,
        'headache': r.headache,
        'sleep_quality': r.sleep_quality,
        'breathing_problem': r.breathing_problem,
        'living_conditions': r.living_conditions,
        'academic_performance': r.academic_performance,
        'study_load': r.study_load,
        'future_career_concerns': r.future_career_concerns,
        'extracurricular_activities': r.extracurricular_activities,
        'stress_level': r.stress_level
    } for r in records]

    df = pd.DataFrame(data)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    filename = f"stress_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return app.response_class(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route('/uploads/export/excel')
@login_required
def uploads_export_excel():
    """Export records to Excel"""
    user_id = session['user_id']
    records = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.asc()).all()
    data = [{
        'id': r.id,
        'timestamp': r.timestamp.isoformat() if r.timestamp else None,
        'anxiety_level': r.anxiety_level,
        'mental_health_history': r.mental_health_history,
        'depression': r.depression,
        'headache': r.headache,
        'sleep_quality': r.sleep_quality,
        'breathing_problem': r.breathing_problem,
        'living_conditions': r.living_conditions,
        'academic_performance': r.academic_performance,
        'study_load': r.study_load,
        'future_career_concerns': r.future_career_concerns,
        'extracurricular_activities': r.extracurricular_activities,
        'stress_level': r.stress_level
    } for r in records]

    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    filename = f"stress_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return app.response_class(
        buffer.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route('/uploads/export/pdf')
@login_required
def uploads_export_pdf():
    """Export records to PDF."""
    user_id = session['user_id']
    records = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.asc()).all()

    lines = [
        "Stress Records Export",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        ""
    ]

    for idx, r in enumerate(records, start=1):
        ts = r.timestamp.strftime('%Y-%m-%d %H:%M') if r.timestamp else 'N/A'
        stress = r.stress_level if r.stress_level is not None else 'N/A'
        lines.append(f"{idx}. {ts} | stress_level={stress}")
        lines.append(
            f"   anxiety={r.anxiety_level} mental={r.mental_health_history} depression={r.depression} "
            f"headache={r.headache} sleep={r.sleep_quality} breathing={r.breathing_problem}"
        )
        lines.append(
            f"   living={r.living_conditions} academic={r.academic_performance} study={r.study_load} "
            f"career={r.future_career_concerns} extra={r.extracurricular_activities}"
        )
        lines.append("")

    if len(records) == 0:
        lines.append("No records available.")

    lines_per_page = 52
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    pdf_data = _build_simple_pdf(pages)

    filename = f"stress_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return app.response_class(
        pdf_data,
        mimetype='application/pdf',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route('/uploads/create', methods=['POST'])
@login_required
def uploads_create():
    """Create a new record manually"""
    try:
        record = StressRecord(
            user_id=session['user_id'],
            anxiety_level=float(request.form.get('anxiety_level')),
            mental_health_history=float(request.form.get('mental_health_history')),
            depression=float(request.form.get('depression')),
            headache=float(request.form.get('headache')),
            sleep_quality=float(request.form.get('sleep_quality')),
            breathing_problem=float(request.form.get('breathing_problem')),
            living_conditions=float(request.form.get('living_conditions')),
            academic_performance=float(request.form.get('academic_performance')),
            study_load=float(request.form.get('study_load')),
            future_career_concerns=float(request.form.get('future_career_concerns')),
            extracurricular_activities=float(request.form.get('extracurricular_activities')),
            stress_level=int(request.form.get('stress_level')) if request.form.get('stress_level') not in (None, '') else None
        )
        db.session.add(record)
        db.session.commit()
        return redirect(url_for('uploads'))
    except Exception as e:
        db.session.rollback()
        records = StressRecord.query.filter_by(user_id=session['user_id']).order_by(StressRecord.timestamp.desc()).all()
        return render_template('uploads.html', records=records, message=f"Create failed: {str(e)}", message_type='danger'), 400


@app.route('/uploads/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def uploads_edit(record_id):
    """Edit an existing record"""
    record = StressRecord.query.filter_by(id=record_id, user_id=session['user_id']).first_or_404()
    if request.method == 'POST':
        try:
            record.anxiety_level = float(request.form.get('anxiety_level'))
            record.mental_health_history = float(request.form.get('mental_health_history'))
            record.depression = float(request.form.get('depression'))
            record.headache = float(request.form.get('headache'))
            record.sleep_quality = float(request.form.get('sleep_quality'))
            record.breathing_problem = float(request.form.get('breathing_problem'))
            record.living_conditions = float(request.form.get('living_conditions'))
            record.academic_performance = float(request.form.get('academic_performance'))
            record.study_load = float(request.form.get('study_load'))
            record.future_career_concerns = float(request.form.get('future_career_concerns'))
            record.extracurricular_activities = float(request.form.get('extracurricular_activities'))
            record.stress_level = int(request.form.get('stress_level')) if request.form.get('stress_level') not in (None, '') else None
            db.session.commit()
            return redirect(url_for('uploads', msg='Record updated successfully.', type='info'))
        except Exception as e:
            db.session.rollback()
            return render_template('upload_edit.html', record=record, message=f"Update failed: {str(e)}", message_type='danger'), 400

    return render_template('upload_edit.html', record=record)


@app.route('/uploads/delete/<int:record_id>', methods=['POST'])
@login_required
def uploads_delete(record_id):
    """Delete a record"""
    record = StressRecord.query.filter_by(id=record_id, user_id=session['user_id']).first_or_404()
    db.session.delete(record)
    db.session.commit()
    return redirect(url_for('uploads', msg='Record deleted successfully.', type='info'))


@app.route('/reports')
@login_required
def reports():
    """Reports dashboard with ML metrics and charts"""
    selected_model = session.get('selected_model', 'tree')
    selected_model_name = {
        'tree': 'Decision Tree',
        'forest': 'Random Forest',
        'svm': 'Support Vector Machine',
        'gbm': 'Gradient Boosting',
    }.get(selected_model, 'Decision Tree')

    metrics = model_metrics.get(selected_model, {
        'accuracy': 0.0,
        'precision': 0.0,
        'recall': 0.0,
        'f1': 0.0,
        'confusion': [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    })

    importance = feature_importances.get(selected_model)
    if not importance:
        importance = feature_importances.get('forest', [])

    feature_pairs = list(zip(feature_names, importance)) if feature_names and importance else []
    feature_pairs = sorted(feature_pairs, key=lambda x: x[1], reverse=True)

    user_id = session['user_id']
    latest = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.desc()).first()
    current_stress = latest.stress_level if latest and latest.stress_level is not None else 0

    return render_template(
        'reports.html',
        selected_model=selected_model_name,
        metrics=metrics,
        feature_pairs=feature_pairs,
        current_stress=current_stress
    )


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page"""
    message = request.args.get('msg')
    message_type = request.args.get('type', 'info')
    if request.method == 'POST':
        password = (request.form.get('password') or '').strip()
        confirm_password = (request.form.get('confirm_password') or '').strip()

        user = User.query.get(session['user_id'])
        if user is None:
            session.clear()
            return redirect(url_for('login_page'))

        if not password or not confirm_password:
            return render_template('settings.html', message='Please enter and confirm a new password.', message_type='danger')

        if password != confirm_password:
            return render_template('settings.html', message='Passwords do not match.', message_type='danger')

        user.set_password(password)
        db.session.commit()
        return redirect(url_for('settings', msg='Password updated successfully.', type='info'))

    return render_template('settings.html', message=message, message_type=message_type)


@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with statistics"""
    try:
        user_id = session['user_id']
        records = StressRecord.query.filter_by(user_id=user_id).order_by(StressRecord.timestamp.desc()).all()
        
        # Calculate statistics
        low_count = sum(1 for r in records if r.stress_level == 0)
        medium_count = sum(1 for r in records if r.stress_level == 1)
        high_count = sum(1 for r in records if r.stress_level == 2)
        
        # Calculate average stress level (map stress levels to numeric values: low=1, medium=2, high=3)
        stress_values = []
        for record in records:
            if record.stress_level is not None:
                stress_values.append(int(record.stress_level) + 1)
        
        avg_stress = sum(stress_values) / len(stress_values) if stress_values else 0
        
        stats = {
            'total_predictions': len(records),
            'latest_prediction': records[0] if records else None,
            'low_stress_count': low_count,
            'medium_stress_count': medium_count,
            'high_stress_count': high_count,
            'avg_stress_level': avg_stress
        }
        
        return render_template('dashboard.html', stats=stats, records=records)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('error.html', error_message='Error loading dashboard'), 500


# ==================== Context Processor ====================

@app.context_processor
def inject_user():
    """Make username available in all templates"""
    return {'username': session.get('username')}


# ==================== Error Handlers ====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error_message='Server error'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
