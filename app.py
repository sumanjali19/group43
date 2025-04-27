from flask import Flask, render_template, request
import pyodbc
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

# Database connection
def db_connect():
    conn = pyodbc.connect(
        DRIVER='{ODBC Driver 18 for SQL Server}',
        SERVER='retaildbserver.database.windows.net',
        DATABASE='RetailDB',
        UID='adminuser',
        PWD='Sumanjali@19'
    )
    return conn

# Expected columns for uploads
EXPECTED_COLUMNS = {
    'transaction_file': ['HSHD_NUM', 'BASKET_NUM', 'PURCHASE', 'PRODUCT_NUM', 'SPEND', 'UNITS', 'STORE_R', 'WEEK_NUM', 'YEAR'],
    'household_file': ['HSHD_NUM', 'LOYALTY_FLAG', 'AGE_RANGE', 'MARITAL_STATUS', 'INCOME_RANGE', 'HOMEOWNER_DESC', 'HSHD_COMPOSITION', 'HSHD_SIZE', 'CHILDREN'],
    'product_file': ['PRODUCT_NUM', 'DEPARTMENT', 'COMMODITY', 'BRAND_TY', 'NATURAL_ORGANIC_FLAG']
}

# Home page (/) -> Search Page
@app.route('/', methods=['GET', 'POST'])
def search():
    results = []
    hshd_nums = []
    selected_hshd = None

    try:
        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT HSHD_NUM FROM dbo.[400_transactions] ORDER BY HSHD_NUM;")
        hshd_nums = [row[0] for row in cursor.fetchall()]

        if request.method == 'POST':
            selected_hshd = request.form['hshd_num']

            query = """
                SELECT t.HSHD_NUM, t.BASKET_NUM, t.PURCHASE,
                       t.PRODUCT_NUM, p.DEPARTMENT, p.COMMODITY
                FROM dbo.[400_transactions] t
                LEFT JOIN dbo.[400_products] p
                ON t.PRODUCT_NUM = p.PRODUCT_NUM
                WHERE t.HSHD_NUM = ?
                ORDER BY t.HSHD_NUM, t.BASKET_NUM, t.PURCHASE, t.PRODUCT_NUM, p.DEPARTMENT, p.COMMODITY
            """
            cursor.execute(query, (selected_hshd,))
            results = cursor.fetchall()

        conn.close()

    except Exception as e:
        print(f"Database connection error: {e}")

    return render_template('search.html', results=results, hshd_nums=hshd_nums, selected_hshd=selected_hshd)

# Upload page (/upload)
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    message = None

    if request.method == 'POST':
        try:
            files = {
                'transaction_file': request.files.get('transaction_file'),
                'household_file': request.files.get('household_file'),
                'product_file': request.files.get('product_file')
            }

            for key, uploaded_file in files.items():
                if uploaded_file and uploaded_file.filename:
                    df = pd.read_csv(uploaded_file)
                    df.columns = df.columns.str.strip()

                    expected_cols = EXPECTED_COLUMNS[key]
                    if sorted(df.columns.tolist()) != sorted(expected_cols):
                        raise ValueError(f"Columns in {key} do not match expected format.\nExpected: {expected_cols}\nFound: {df.columns.tolist()}")

                    if key == 'transaction_file':
                        insert_transactions(df)
                    elif key == 'household_file':
                        insert_households(df)
                    elif key == 'product_file':
                        insert_products(df)

            message = "Available files uploaded and data inserted successfully!"

        except Exception as e:
            message = f"Upload failed: {str(e)}"

    return render_template('upload.html', message=message)

# Dashboard page (/dashboard) -> Pulling from database directly!
@app.route('/dashboard')
def dashboard():
    demo_data = []
    year_data = []
    brand_data = []

    try:
        conn = db_connect()
        cursor = conn.cursor()

        # Household Size vs Average Spend
        cursor.execute("""
            SELECT TRY_CAST(h.HH_SIZE AS INT), AVG(t.SPEND)
            FROM dbo.[400_households] h
            JOIN dbo.[400_transactions] t
            ON h.HSHD_NUM = t.HSHD_NUM
            WHERE TRY_CAST(h.HH_SIZE AS INT) IS NOT NULL
            GROUP BY TRY_CAST(h.HH_SIZE AS INT)
            ORDER BY TRY_CAST(h.HH_SIZE AS INT)
        """)
        demo_data = cursor.fetchall()

        # Year vs Total Spend
        cursor.execute("""
            SELECT YEAR(PURCHASE), SUM(SPEND)
            FROM dbo.[400_transactions]
            WHERE PURCHASE IS NOT NULL
            GROUP BY YEAR(PURCHASE)
            ORDER BY YEAR(PURCHASE)
        """)
        year_data = cursor.fetchall()

        # Brand Preferences (Organic vs Non-Organic)
        cursor.execute("""
            SELECT p.NATURAL_ORGANIC_FLAG, COUNT(*)
            FROM dbo.[400_products] p
            GROUP BY p.NATURAL_ORGANIC_FLAG
        """)
        brand_data = cursor.fetchall()

        conn.close()

    except Exception as e:
        print("Dashboard Data Error:", e)

    print("\n======== DASHBOARD DATA CHECK ========")
    print(f"Demo Data (Household Size vs Avg Spend): {demo_data}")
    print(f"Year Data (Year vs Spend): {year_data}")
    print(f"Brand Data (Organic vs Non-Organic): {brand_data}")
    print("=======================================\n")

    return render_template('dashboard.html', demo_data=demo_data, year_data=year_data, brand_data=brand_data)

# Insert functions (needed for uploads)
def insert_transactions(df):
    conn = db_connect()
    cursor = conn.cursor()

    df['SPEND'] = pd.to_numeric(df['SPEND'], errors='coerce').fillna(0)
    df['UNITS'] = pd.to_numeric(df['UNITS'], errors='coerce').fillna(0)

    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO dbo.[400_transactions]
            (HSHD_NUM, BASKET_NUM, PURCHASE, PRODUCT_NUM, SPEND, UNITS, STORE_R, WEEK_NUM, YEAR)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        row['HSHD_NUM'], row['BASKET_NUM'], row['PURCHASE'], row['PRODUCT_NUM'],
        row['SPEND'], row['UNITS'], row['STORE_R'], row['WEEK_NUM'], row['YEAR'])

    conn.commit()
    conn.close()

def insert_households(df):
    conn = db_connect()
    cursor = conn.cursor()

    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO dbo.[400_households]
            (HSHD_NUM, LOYALTY_FLAG, AGE_RANGE, MARITAL_STATUS, INCOME_RANGE, HOMEOWNER_DESC, HSHD_COMPOSITION, HSHD_SIZE, CHILDREN)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        row['HSHD_NUM'], row['LOYALTY_FLAG'], row['AGE_RANGE'], row['MARITAL_STATUS'],
        row['INCOME_RANGE'], row['HOMEOWNER_DESC'], row['HSHD_COMPOSITION'],
        row['HSHD_SIZE'], row['CHILDREN'])

    conn.commit()
    conn.close()

def insert_products(df):
    conn = db_connect()
    cursor = conn.cursor()

    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO dbo.[400_products]
            (PRODUCT_NUM, DEPARTMENT, COMMODITY, BRAND_TY, NATURAL_ORGANIC_FLAG)
            VALUES (?, ?, ?, ?, ?)
        """,
        row['PRODUCT_NUM'], row['DEPARTMENT'], row['COMMODITY'],
        row['BRAND_TY'], row['NATURAL_ORGANIC_FLAG'])

    conn.commit()
    conn.close()

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
