from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from flask_sqlalchemy import SQLAlchemy
import database as db
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# db = SQLAlchemy(app)

# ==================== HOME ROUTE ====================

@app.route('/')
def index():
    """Home dashboard with trending books and user's current reads"""
    user_id = session.get('user_id')
    user = None
    currently_reading = []
    
    if user_id:
        user = db.get_user_by_id(user_id)
        currently_reading = db.get_user_books(user_id, 'currently-reading')
    
    # Get trending books
    trending_weekly = db.get_trending_books('weekly', 6)
    trending_monthly = db.get_trending_books('monthly', 6)
    
    # Get recent reviews (from all books)
    recent_reviews = []
    conn = None
    try:
        conn = db.get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=db.RealDictCursor)
            cursor.execute("""
                SELECT r.*, u.username, b.title, b.cover_image_url
                FROM reviews r
                JOIN users u ON r.user_id = u.user_id
                JOIN books b ON r.book_id = b.book_id
                ORDER BY r.review_date DESC
                LIMIT 5
            """)
            recent_reviews = cursor.fetchall()
            cursor.close()
    except Exception as e:
        print(f"Error fetching recent reviews: {e}")
    finally:
        if conn:
            db.release_connection(conn)
    
    return render_template('index.html', 
                         user=user,
                         currently_reading=currently_reading,
                         trending_weekly=trending_weekly,
                         trending_monthly=trending_monthly,
                         recent_reviews=recent_reviews)

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        
        # Check if user already exists
        existing_user = db.get_user_by_username(username)
        if existing_user:
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        # Hash password and create user
        password_hash = generate_password_hash(password)
        user_id = db.create_user(username, email, password_hash, first_name, last_name)
        
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            flash('Registration successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    """User login"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = db.get_user_by_username(username)
    
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        db.update_last_login(user['user_id'])
        flash('Login successful!', 'success')
    else:
        flash('Invalid username or password', 'error')
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

# ==================== BOOK ROUTES ====================

@app.route('/book/<int:book_id>')
def book_details(book_id):
    """Display book details with reviews"""
    book = db.get_book_by_id(book_id)
    if not book:
        return render_template('404.html'), 404
    
    reviews = db.get_book_reviews(book_id)
    average_rating = db.get_book_average_rating(book_id)
    
    user_id = session.get('user_id')
    user_status = None
    user_review = None
    
    if user_id:
        # Check if user has this book in their shelf
        user_books = db.get_user_books(user_id)
        for ub in user_books:
            if ub['book_id'] == book_id:
                user_status = ub
                break
        
        # Check if user has reviewed this book
        for review in reviews:
            if review['user_id'] == user_id:
                user_review = review
                break
    
    # Get related books (same genre/category)
    related_books = []
    if book.get('category'):
        related_books = db.get_books_by_genre(book['category'], 6)
        # Remove current book from related
        related_books = [b for b in related_books if b['book_id'] != book_id]
    
    return render_template('book_details.html',
                         book=book,
                         reviews=reviews,
                         average_rating=average_rating,
                         user_status=user_status,
                         user_review=user_review,
                         related_books=related_books,
                         user=db.get_user_by_id(user_id) if user_id else None)

@app.route('/search')
def search():
    """Search books in local database and Google Books API"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    # Search local database first
    local_books = db.search_local_books(query)
    
    # Search Google Books API
    google_books = db.fetch_from_google_books(query, 10)
    
    # Combine results (local first, then Google Books)
    results = []
    
    for book in local_books:
        results.append({
            'id': book['book_id'],
            'google_book_id': book.get('google_book_id'),
            'title': book['title'],
            'author': book['author'],
            'cover': book.get('cover_image_url'),
            'description': book.get('description', '')[:200] + '...' if book.get('description') else '',
            'source': 'local'
        })
    
    for book in google_books:
        # Check if already in local results
        if not any(r.get('google_book_id') == book['google_book_id'] for r in results):
            results.append({
                'google_book_id': book['google_book_id'],
                'title': book['title'],
                'author': book['author'],
                'cover': book.get('cover_image_url'),
                'description': book.get('description', '')[:200] + '...' if book.get('description') else '',
                'source': 'google',
                'data': book  # Full data for caching
            })
    
    return jsonify(results)

# ==================== SHELF MANAGEMENT ROUTES ====================

@app.route('/add-to-shelf', methods=['POST'])
def add_to_shelf():
    """Add book to user's shelf (with AJAX support)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    user_id = session['user_id']
    book_id = request.form.get('book_id')
    google_book_id = request.form.get('google_book_id')
    status = request.form.get('status', 'want-to-read')
    
    # If it's a Google Books result, cache it first
    if google_book_id and not book_id:
        # Get book data from form
        book_data = {
            'google_book_id': google_book_id,
            'title': request.form.get('title'),
            'author': request.form.get('author'),
            'isbn': request.form.get('isbn', ''),
            'publication_date': request.form.get('publication_date'),
            'description': request.form.get('description', ''),
            'cover_image_url': request.form.get('cover_image_url', ''),
            'category': request.form.get('category', 'General'),
            'page_count': int(request.form.get('page_count', 0)),
            'language': request.form.get('language', 'en')
        }
        book_id = db.cache_google_book(book_data)
    
    if not book_id:
        return jsonify({'success': False, 'message': 'Failed to add book'}), 400
    
    success = db.add_book_to_shelf(user_id, book_id, status)
    
    if success:
        return jsonify({'success': True, 'message': f'Book added to {status}', 'book_id': book_id})
    else:
        return jsonify({'success': False, 'message': 'Failed to add book to shelf'}), 500

@app.route('/update-progress', methods=['POST'])
def update_progress():
    """Update reading progress"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    user_id = session['user_id']
    book_id = request.form.get('book_id')
    progress = int(request.form.get('progress', 0))
    
    success = db.update_reading_progress(user_id, book_id, progress)
    
    if success:
        return jsonify({'success': True, 'message': 'Progress updated'})
    else:
        return jsonify({'success': False, 'message': 'Failed to update progress'}), 500

# ==================== REVIEW ROUTES ====================

@app.route('/submit-review', methods=['POST'])
def submit_review():
    """Submit or update a review"""
    if 'user_id' not in session:
        flash('Please login to submit a review', 'error')
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    book_id = request.form.get('book_id')
    rating = int(request.form.get('rating'))
    review_text = request.form.get('review_text', '')
    
    review_id = db.submit_review(user_id, book_id, rating, review_text)
    
    if review_id:
        flash('Review submitted successfully!', 'success')
    else:
        flash('Failed to submit review', 'error')
    
    return redirect(url_for('book_details', book_id=book_id))

@app.route('/delete-review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    """Delete a user's review"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    user_id = session['user_id']
    success = db.delete_review(review_id, user_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Review deleted'})
    else:
        return jsonify({'success': False, 'message': 'Failed to delete review'}), 500

# ==================== PROFILE ROUTE ====================

@app.route('/profile')
def profile():
    """User profile with reading stats and shelves"""
    if 'user_id' not in session:
        flash('Please login to view your profile', 'error')
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    user = db.get_user_by_id(user_id)
    
    # Get reading statistics
    stats = db.get_user_reading_stats(user_id)
    
    # Get books by shelf
    want_to_read = db.get_user_books(user_id, 'want-to-read')
    currently_reading = db.get_user_books(user_id, 'currently-reading')
    read_books = db.get_user_books(user_id, 'read')
    
    # Get user reviews
    user_reviews = db.get_user_reviews(user_id)
    
    return render_template('profile.html',
                         user=user,
                         stats=stats,
                         want_to_read=want_to_read,
                         currently_reading=currently_reading,
                         read_books=read_books,
                         user_reviews=user_reviews)

# ==================== GENRE/DISCOVERY ROUTES ====================

@app.route('/genre/<genre_name>')
def genre_books(genre_name):
    """Browse books by genre"""
    books = db.get_books_by_genre(genre_name, 20)
    user = db.get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    
    return render_template('index.html', 
                         genre_books=books,
                         genre_name=genre_name,
                         user=user)

@app.route('/trending/<trend_type>')
def trending(trend_type):
    """View trending books by type (weekly, monthly, yearly)"""
    if trend_type not in ['weekly', 'monthly', 'yearly']:
        return render_template('404.html'), 404
    
    books = db.get_trending_books(trend_type, 20)
    user = db.get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    
    return render_template('index.html',
                         trending_books=books,
                         trend_type=trend_type,
                         user=user)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 error page"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Custom 500 error page"""
    return render_template('500.html'), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("BookVault - Starting Application")
    print("=" * 60)
    print("\nIMPORTANT: Make sure you have:")
    print("1. Created a Neon database at https://console.neon.tech")
    print("2. Updated DATABASE_URL in database.py with your connection string")
    print("3. Run schema.sql and sample_data.sql in your Neon database")
    print("\nStarting server on http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
