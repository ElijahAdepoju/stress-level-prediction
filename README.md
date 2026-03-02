# Stress Level Predictor

A comprehensive web application that predicts stress levels using multiple machine learning models and provides detailed analysis with historical tracking.

## Features

### User Management
- **User Registration & Authentication** - Secure account creation with password hashing
- **Session Management** - Persistent user sessions with login/logout
- **Data Isolation** - Each user's stress records are private and isolated

### Stress Assessment
- **11 Input Factors** - Comprehensive assessment covering:
  - Mental health factors (anxiety, mental health history, depression)
  - Physical health indicators (headaches, sleep quality, breathing problems)
  - Life circumstances (living conditions, academic performance, study load, career concerns, extracurricular activities)
- **Detailed Explanations** - Tooltips and guidance for each input factor
- **Input Validation** - Client-side and server-side validation

### Machine Learning Models
- **Decision Tree Classifier** - Simple, interpretable predictions
- **Random Forest** - Ensemble method with reduced overfitting
- **Support Vector Machine (SVM)** - Complex boundary detection
- **Gradient Boosting** - Sequential improvement with high accuracy

All models are trained on the provided dataset and their predictions are displayed for comparison.

### History & Analytics
- **Prediction History** - Track all past assessments with timestamps
- **Interactive Chart** - Visualize stress level trends over time
- **Model Comparison** - See predictions from all four models for each assessment
- **Dashboard** - Quick overview of assessment statistics

## Technologies Used

- **Backend:** Python, Flask, Flask-SQLAlchemy
- **Database:** SQLite
- **ML:** scikit-learn
- **Frontend:** HTML5, CSS3, JavaScript
- **Visualization:** Chart.js
- **Security:** Werkzeug (password hashing)

## Project Structure

```
stress-level-predection/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── StressLevelDataset.csv      # Training dataset
├── static/
│   └── styles.css             # Enhanced CSS styling
├── templates/
│   ├── login.html             # Login page
│   ├── register.html          # Registration page
│   ├── predict.html           # Stress assessment form with detailed explanations
│   ├── result.html            # Results with model comparisons
│   ├── history.html           # Historical data and trend visualization
│   ├── dashboard.html         # User dashboard with statistics
│   └── error.html             # Error page
├── stress_predictor.db        # SQLite database (created automatically)
└── README.md                  # This file
```

## Setup and Running the Application

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. Clone the repository:
   ```sh
   git clone <repository-url>
   cd stress-level-predection
   ```

2. Create a virtual environment (recommended):
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

4. Ensure you have the `StressLevelDataset.csv` file in the project root directory.

5. Run the Flask application:
   ```sh
   python app.py
   ```

6. Open your web browser and navigate to `http://localhost:5000`

## Usage

### Creating an Account
1. Click "Register" on the login page
2. Enter your desired username, email, and password
3. Confirm your password and submit

### Taking an Assessment
1. Log in with your credentials
2. Click "Predict" to access the assessment form
3. Fill in the 11 stress factors with honest responses
4. Review the detailed explanations for each factor (hover over ℹ️ icons)
5. Submit the form to get predictions from all four models

### Viewing Results
- See side-by-side predictions from all models
- Review accuracy scores for each model
- Understand the pros and cons of each approach
- Take a new assessment or view your history

### Tracking Progress
- Visit "History" to see all past assessments
- View an interactive chart showing trends over time
- Examine individual factors (anxiety, depression, sleep quality, etc.) for each assessment
- Use the dashboard for a quick overview of your assessment patterns

## Understanding the Models

### Decision Tree
- **Pros:** Easy to interpret, fast predictions
- **Cons:** Can overfit, may miss complex patterns
- **Best for:** Quick assessment when interpretability matters

### Random Forest
- **Pros:** More robust, reduces overfitting, good generalization
- **Cons:** Less interpretable than single tree
- **Best for:** Balanced accuracy and robustness

### Support Vector Machine (SVM)
- **Pros:** Excellent for complex boundaries, handles high dimensions
- **Cons:** Slower training, requires feature scaling
- **Best for:** Finding non-linear patterns

### Gradient Boosting
- **Pros:** Often provides best accuracy, sequential improvement
- **Cons:** More complex, risk of overfitting
- **Best for:** Highest accuracy predictions

## Understanding Your Results

**Stress Level Categories:**
- **Low** - You're managing stress well
- **Moderate** - Some stress present; consider stress management techniques
- **High** - Significant stress; consider professional support or lifestyle changes

**When Models Disagree:**
If models give different predictions, your stress level is in a borderline zone. Consider the model accuracies and your personal judgment.

## Tips for Better Mental Health

- Maintain 7-9 hours of quality sleep per night
- Exercise regularly (at least 30 minutes daily)
- Practice mindfulness or meditation
- Maintain social connections
- Engage in hobbies and activities you enjoy
- Seek professional help if stress remains consistently high

## Security Notes

- Passwords are hashed using werkzeug's secure hashing
- User data is stored in a local SQLite database
- Each user can only access their own stress records
- Session management prevents unauthorized access

## License

This project is open source and available for educational use.

## Disclaimer

This application is for informational purposes only and should not be used as a substitute for professional mental health diagnosis or treatment. If you are experiencing significant stress or mental health concerns, please consult a qualified mental health professional.


## How to Use

1. Fill in the form with your stress-related factors. Each field has a specified range of values.
2. Click the "Submit" button to get your predicted stress level.
3. The result page will display your predicted stress level based on the input factors.

## Future Improvements

- Implement user authentication and data storage
- Add more detailed explanations for each input factor
- Incorporate additional machine learning models for comparison
- Develop a feature to track stress levels over time

## Contributing

Contributions to improve the project are welcome. Please feel free to fork the repository and submit pull requests.

## License

This project is open source and available under the [MIT License](LICENSE).
