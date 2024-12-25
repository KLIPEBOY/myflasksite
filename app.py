import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Initialize the database
DATABASE = 'tickets.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                balance REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                location TEXT NOT NULL,
                city TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 10
            );

            CREATE TABLE IF NOT EXISTS user_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticket_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (ticket_id) REFERENCES tickets (id)
            );
        ''')


def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def index():
    tickets = query_db('SELECT * FROM tickets WHERE buyer_id IS NULL')
    return render_template('index.html', tickets=tickets)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('login'))



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if user and user['password'] == password:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            query_db('INSERT INTO users (username, password) VALUES (?, ?)', [username, password])
            flash('Registration successful')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = query_db('SELECT * FROM users WHERE id = ?', [session['user_id']], one=True)
    user_tickets = query_db('''
        SELECT t.* 
        FROM tickets t
        JOIN user_tickets ut ON t.id = ut.ticket_id
        WHERE ut.user_id = ?
    ''', [session['user_id']])

    return render_template('dashboard.html', user=user, user_tickets=user_tickets)



@app.route('/debug_tickets')
def debug_tickets():
    tickets = query_db('SELECT * FROM tickets')
    return {'tickets': [dict(ticket) for ticket in tickets]}


@app.route('/add_balance', methods=['POST'])
def add_balance():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    amount = float(request.form['amount'])
    query_db('UPDATE users SET balance = balance + ? WHERE id = ?', [amount, session['user_id']])
    flash('Balance updated')
    return redirect(url_for('dashboard'))

@app.route('/buy_ticket/<int:ticket_id>')
def buy_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ticket = query_db('SELECT * FROM tickets WHERE id = ?', [ticket_id], one=True)
    user = query_db('SELECT * FROM users WHERE id = ?', [session['user_id']], one=True)

    if ticket and ticket['quantity'] > 0:
        if user['balance'] >= ticket['price']:
            query_db('UPDATE users SET balance = balance - ? WHERE id = ?', [ticket['price'], user['id']])
            query_db('UPDATE tickets SET quantity = quantity - 1 WHERE id = ?', [ticket['id']])
            query_db('INSERT INTO user_tickets (user_id, ticket_id) VALUES (?, ?)', [user['id'], ticket['id']])
            flash('Билет успешно куплен!')
        else:
            flash('Недостаточно средств для покупки.')
    else:
        flash('Билеты закончились.')

    return redirect(url_for('index'))



@app.route('/return_ticket/<int:ticket_id>')
def return_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ticket = query_db('SELECT * FROM tickets WHERE id = ?', [ticket_id], one=True)
    user_ticket = query_db('SELECT * FROM user_tickets WHERE user_id = ? AND ticket_id = ?', [session['user_id'], ticket_id], one=True)

    if user_ticket:
        query_db('DELETE FROM user_tickets WHERE user_id = ? AND ticket_id = ?', [session['user_id'], ticket_id])
        query_db('UPDATE users SET balance = balance + ? WHERE id = ?', [ticket['price'], session['user_id']])
        query_db('UPDATE tickets SET quantity = quantity + 1 WHERE id = ?', [ticket_id])
        flash('Билет успешно возвращен.')
    else:
        flash('Вы не можете вернуть этот билет.')

    return redirect(url_for('dashboard'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        title = request.form['title']
        artist = request.form['artist']
        location = request.form['location']
        city = request.form['city']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        query_db('INSERT INTO tickets (title, artist, location, city, price, quantity) VALUES (?, ?, ?, ?, ?, ?)',
                 [title, artist, location, city, price, quantity])
        flash('Билет добавлен.')
    tickets = query_db('SELECT * FROM tickets')
    return render_template('admin.html', tickets=tickets)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
