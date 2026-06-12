def init_db():
    if not os.path.exists(DATABASE):
        with app.app_context():
            db = get_db()
            
            # Enable Foreign Keys
            db.execute('PRAGMA foreign_keys = ON;')
            
            # 1. Users Table (Added phone_number back!)
            db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    phone_number TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # 2. Reminders Table (With Foreign Key & Dates)
            db.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    medicine_name TEXT NOT NULL,
                    dosage TEXT,
                    reminder_time TEXT,
                    reminder_date DATE,
                    frequency TEXT DEFAULT 'daily',
                    send_email INTEGER DEFAULT 1,
                    last_sent DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            ''')
            
            # 3. Donations Table
            db.execute('''
                CREATE TABLE IF NOT EXISTS donations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    medicine_name TEXT NOT NULL,
                    expiry_date DATE,
                    quantity INTEGER,
                    location TEXT,
                    contact TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                );
            ''')
            
            db.commit()
            print("✅ Database initialized successfully.")