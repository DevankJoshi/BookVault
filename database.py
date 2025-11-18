"""
BookVault Database Module
Handles all PostgreSQL database operations using psycopg2
Connection to Neon cloud-hosted PostgreSQL database
"""

import psycopg2
from psycopg2 import Error
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# Database Configuration
# For local PostgreSQL connection

DATABASE_URL = os.getenv('DATABASE_URL')
print(DATABASE_URL)

# Update this with your actual local database credentials:
# Format: postgresql://username:password@host:port/database_name
# Example: postgresql://postgres:mypassword@localhost:5432/library_db

# Connection pool for better performance
connection_pool = None

def init_connection_pool():
    """Initialize the connection pool"""
    global connection_pool
    try:
        if connection_pool is None:
            connection_pool = SimpleConnectionPool(
                1, 20,  # min and max connections
                DATABASE_URL
            )
            if connection_pool:
                print("✅ Connection pool created successfully")
                print(f"📍 Connected to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local database'}")
    except (Exception, Error) as error:
        print(f"❌ Error while connecting to PostgreSQL: {error}")
        print("\n🔧 Make sure PostgreSQL is running and check your connection details:")
        print("   - Host: localhost")
        print("   - Port: 5432 (default)")
        print("   - Database: library_db")
        print("   - Username and password are correct")
        return None

def get_db_connection():
    """Get a connection from the pool"""
    try:
        if connection_pool is None:
            init_connection_pool()
        
        if connection_pool:
            return connection_pool.getconn()
        return None
    except (Exception, Error) as error:
        print(f"❌ Error getting connection from pool: {error}")
        return None

def release_connection(conn):
    """Return a connection to the pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

def close_all_connections():
    """Close all database connections in the pool"""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        print("🔌 Connection pool closed")
# ==================== BOOK OPERATIONS ====================

def get_trending_books(trend_type='weekly', limit=10):
    """Fetch trending books from database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT b.*, t.average_rating, t.read_count, t.review_count, t.trend_rank
            FROM trending_books t
            JOIN books b ON t.book_id = b.book_id
            WHERE t.trend_type = %s
            ORDER BY t.trend_rank ASC
            LIMIT %s
        """
        cursor.execute(query, (trend_type, limit))
        books = cursor.fetchall()
        cursor.close()
        return books
    except (Exception, Error) as error:
        print(f"Error fetching trending books: {error}")
        return []
    finally:
        release_connection(conn)

def search_local_books(query):
    """Search books in local database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        search_query = f"%{query}%"
        sql = """
            SELECT * FROM books
            WHERE LOWER(title) LIKE LOWER(%s) 
            OR LOWER(author) LIKE LOWER(%s)
            OR LOWER(category) LIKE LOWER(%s)
            LIMIT 20
        """
        cursor.execute(sql, (search_query, search_query, search_query))
        books = cursor.fetchall()
        cursor.close()
        return books
    except (Exception, Error) as error:
        print(f"Error searching local books: {error}")
        return []
    finally:
        release_connection(conn)

def get_book_by_id(book_id):
    """Fetch book details by ID"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        cursor.close()
        return book
    except (Exception, Error) as error:
        print(f"Error fetching book by ID: {error}")
        return None
    finally:
        release_connection(conn)

def get_books_by_genre(genre, limit=20):
    """Get books by genre with rankings"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT b.*, g.rank_position, g.average_rating, g.rating_count
            FROM genre_rankings g
            JOIN books b ON g.book_id = b.book_id
            WHERE g.genre = %s
            ORDER BY g.rank_position ASC
            LIMIT %s
        """
        cursor.execute(query, (genre, limit))
        books = cursor.fetchall()
        cursor.close()
        return books
    except (Exception, Error) as error:
        print(f"Error fetching books by genre: {error}")
        return []
    finally:
        release_connection(conn)

def cache_google_book(book_data):
    """Insert Google Books result into local database"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Check if book already exists
        cursor.execute("SELECT book_id FROM books WHERE google_book_id = %s", (book_data['google_book_id'],))
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            return existing[0]
        
        # Insert new book
        sql = """
            INSERT INTO books (google_book_id, title, author, isbn, publication_date, 
                             description, cover_image_url, category, page_count, language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING book_id
        """
        cursor.execute(sql, (
            book_data.get('google_book_id'),
            book_data.get('title'),
            book_data.get('author'),
            book_data.get('isbn'),
            book_data.get('publication_date'),
            book_data.get('description'),
            book_data.get('cover_image_url'),
            book_data.get('category'),
            book_data.get('page_count'),
            book_data.get('language', 'en')
        ))
        
        book_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return book_id
    except (Exception, Error) as error:
        print(f"Error caching Google book: {error}")
        if conn:
            conn.rollback()
        return None
    finally:
        release_connection(conn)

# ==================== GOOGLE BOOKS API ====================

def fetch_from_google_books(query, max_results=20):
    """Query Google Books API"""
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            'q': query,
            'maxResults': max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        books = []
        
        if 'items' in data:
            for item in data['items']:
                volume_info = item.get('volumeInfo', {})
                
                # Extract ISBN
                isbn = ''
                if 'industryIdentifiers' in volume_info:
                    for identifier in volume_info['industryIdentifiers']:
                        if identifier['type'] in ['ISBN_13', 'ISBN_10']:
                            isbn = identifier['identifier']
                            break
                
                # Extract authors
                authors = ', '.join(volume_info.get('authors', ['Unknown']))
                
                # Extract best available thumbnail from imageLinks
                image_links = volume_info.get('imageLinks', {}) or {}
                thumbnail = ''
                # Prefer larger sizes when available
                for key in ['extraLarge', 'large', 'medium', 'small', 'thumbnail', 'smallThumbnail']:
                    if key in image_links:
                        thumbnail = image_links.get(key) or ''
                        break
                # Normalize to https and clean common unwanted params
                if thumbnail:
                    # Protocol-relative URLs (e.g. //books.google...) -> add https:
                    if thumbnail.startswith('//'):
                        thumbnail = 'https:' + thumbnail
                    # Replace http with https when necessary
                    if thumbnail.startswith('http:'):
                        thumbnail = 'https:' + thumbnail[5:]
                    # Remove Google-specific edge param that sometimes breaks
                    thumbnail = thumbnail.replace('&edge=curl', '')
                
                # Extract categories
                categories = ', '.join(volume_info.get('categories', ['General']))
                
                book = {
                    'google_book_id': item['id'],
                    'title': volume_info.get('title', 'Unknown Title'),
                    'author': authors,
                    'isbn': isbn,
                    'publication_date': volume_info.get('publishedDate', None),
                    'description': volume_info.get('description', 'No description available'),
                    'cover_image_url': thumbnail,
                    'category': categories,
                    'page_count': volume_info.get('pageCount', 0),
                    'language': volume_info.get('language', 'en')
                }
                books.append(book)
        
        return books
    except requests.exceptions.RequestException as error:
        print(f"Error fetching from Google Books API: {error}")
        return []

# ==================== USER OPERATIONS ====================

def create_user(username, email, password_hash, first_name='', last_name=''):
    """Create a new user"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO users (username, email, password_hash, first_name, last_name)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
        """
        cursor.execute(sql, (username, email, password_hash, first_name, last_name))
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return user_id
    except (Exception, Error) as error:
        print(f"Error creating user: {error}")
        if conn:
            conn.rollback()
        return None
    finally:
        release_connection(conn)

def get_user_by_username(username):
    """Get user by username"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        return user
    except (Exception, Error) as error:
        print(f"Error fetching user: {error}")
        return None
    finally:
        release_connection(conn)

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        return user
    except (Exception, Error) as error:
        print(f"Error fetching user by ID: {error}")
        return None
    finally:
        release_connection(conn)

def update_last_login(user_id):
    """Update user's last login timestamp"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()
        cursor.close()
        return True
    except (Exception, Error) as error:
        print(f"Error updating last login: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        release_connection(conn)

# ==================== READING STATUS OPERATIONS ====================

def add_book_to_shelf(user_id, book_id, status):
    """Add or update book in user's shelf"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute(
            "SELECT status_id FROM reading_status WHERE user_id = %s AND book_id = %s",
            (user_id, book_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            sql = """
                UPDATE reading_status 
                SET status = %s, date_added = CURRENT_TIMESTAMP
                WHERE user_id = %s AND book_id = %s
            """
            cursor.execute(sql, (status, user_id, book_id))
        else:
            # Insert new
            sql = """
                INSERT INTO reading_status (user_id, book_id, status)
                VALUES (%s, %s, %s)
            """
            cursor.execute(sql, (user_id, book_id, status))
        
        conn.commit()
        cursor.close()
        return True
    except (Exception, Error) as error:
        print(f"Error adding book to shelf: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        release_connection(conn)

def update_reading_progress(user_id, book_id, progress):
    """Update reading progress for a book"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        sql = """
            UPDATE reading_status 
            SET progress_percentage = %s,
                date_started = CASE WHEN date_started IS NULL AND %s > 0 THEN CURRENT_TIMESTAMP ELSE date_started END,
                date_finished = CASE WHEN %s >= 100 THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE user_id = %s AND book_id = %s
        """
        cursor.execute(sql, (progress, progress, progress, user_id, book_id))
        conn.commit()
        cursor.close()
        return True
    except (Exception, Error) as error:
        print(f"Error updating reading progress: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        release_connection(conn)

def get_user_books(user_id, status=None):
    """Fetch user's books by shelf status"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if status:
            query = """
                SELECT b.*, rs.status, rs.progress_percentage, rs.date_added, rs.date_started, rs.date_finished
                FROM reading_status rs
                JOIN books b ON rs.book_id = b.book_id
                WHERE rs.user_id = %s AND rs.status = %s
                ORDER BY rs.date_added DESC
            """
            cursor.execute(query, (user_id, status))
        else:
            query = """
                SELECT b.*, rs.status, rs.progress_percentage, rs.date_added, rs.date_started, rs.date_finished
                FROM reading_status rs
                JOIN books b ON rs.book_id = b.book_id
                WHERE rs.user_id = %s
                ORDER BY rs.date_added DESC
            """
            cursor.execute(query, (user_id,))
        
        books = cursor.fetchall()
        cursor.close()
        return books
    except (Exception, Error) as error:
        print(f"Error fetching user books: {error}")
        return []
    finally:
        release_connection(conn)

def get_user_reading_stats(user_id):
    """Get user's reading statistics"""
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Count books by status
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'read' THEN 1 END) as books_read,
                COUNT(CASE WHEN status = 'currently-reading' THEN 1 END) as currently_reading,
                COUNT(CASE WHEN status = 'want-to-read' THEN 1 END) as want_to_read
            FROM reading_status
            WHERE user_id = %s
        """, (user_id,))
        stats = cursor.fetchone()
        
        # Get average rating given
        cursor.execute("""
            SELECT AVG(rating) as avg_rating_given, COUNT(*) as total_reviews
            FROM reviews
            WHERE user_id = %s
        """, (user_id,))
        rating_stats = cursor.fetchone()
        
        cursor.close()
        
        return {
            'books_read': stats['books_read'] or 0,
            'currently_reading': stats['currently_reading'] or 0,
            'want_to_read': stats['want_to_read'] or 0,
            'avg_rating_given': float(rating_stats['avg_rating_given']) if rating_stats['avg_rating_given'] else 0,
            'total_reviews': rating_stats['total_reviews'] or 0
        }
    except (Exception, Error) as error:
        print(f"Error fetching user stats: {error}")
        return {}
    finally:
        release_connection(conn)

# ==================== REVIEW OPERATIONS ====================

def submit_review(user_id, book_id, rating, review_text):
    """Submit a review for a book"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Check if user already reviewed this book
        cursor.execute(
            "SELECT review_id FROM reviews WHERE user_id = %s AND book_id = %s",
            (user_id, book_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing review
            sql = """
                UPDATE reviews 
                SET rating = %s, review_text = %s, review_date = CURRENT_TIMESTAMP
                WHERE review_id = %s
                RETURNING review_id
            """
            cursor.execute(sql, (rating, review_text, existing[0]))
        else:
            # Insert new review
            sql = """
                INSERT INTO reviews (user_id, book_id, rating, review_text)
                VALUES (%s, %s, %s, %s)
                RETURNING review_id
            """
            cursor.execute(sql, (user_id, book_id, rating, review_text))
        
        review_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return review_id
    except (Exception, Error) as error:
        print(f"Error submitting review: {error}")
        if conn:
            conn.rollback()
        return None
    finally:
        release_connection(conn)

def get_book_reviews(book_id):
    """Fetch all reviews for a book"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT r.*, u.username, u.first_name, u.last_name
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.book_id = %s
            ORDER BY r.review_date DESC
        """
        cursor.execute(query, (book_id,))
        reviews = cursor.fetchall()
        cursor.close()
        return reviews
    except (Exception, Error) as error:
        print(f"Error fetching book reviews: {error}")
        return []
    finally:
        release_connection(conn)

def get_user_reviews(user_id):
    """Fetch all reviews by a user"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT r.*, b.title, b.author, b.cover_image_url
            FROM reviews r
            JOIN books b ON r.book_id = b.book_id
            WHERE r.user_id = %s
            ORDER BY r.review_date DESC
        """
        cursor.execute(query, (user_id,))
        reviews = cursor.fetchall()
        cursor.close()
        return reviews
    except (Exception, Error) as error:
        print(f"Error fetching user reviews: {error}")
        return []
    finally:
        release_connection(conn)

def delete_review(review_id, user_id):
    """Delete a user's review"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reviews WHERE review_id = %s AND user_id = %s",
            (review_id, user_id)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted
    except (Exception, Error) as error:
        print(f"Error deleting review: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        release_connection(conn)

def get_book_average_rating(book_id):
    """Get average rating for a book"""
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT AVG(rating) as avg_rating FROM reviews WHERE book_id = %s",
            (book_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        return float(result[0]) if result[0] else 0
    except (Exception, Error) as error:
        print(f"Error getting average rating: {error}")
        return 0
    finally:
        release_connection(conn)

# Initialize connection pool on module load
init_connection_pool()

