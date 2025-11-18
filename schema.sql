-- BookVault Database Schema
-- PostgreSQL database schema for Neon cloud database
-- Run this script first to create all tables

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS genre_rankings CASCADE;
DROP TABLE IF EXISTS trending_books CASCADE;
DROP TABLE IF EXISTS reading_status CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    profile_picture VARCHAR(1000),
    bio VARCHAR(500),
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Create books table
CREATE TABLE books (
    book_id SERIAL PRIMARY KEY,
    google_book_id VARCHAR(100) UNIQUE,
    title VARCHAR(500),
    author VARCHAR(300),
    isbn VARCHAR(20),
    publication_date DATE,
    description TEXT,
    cover_image_url VARCHAR(1000),
    category VARCHAR(100),
    page_count INTEGER,
    language VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create reviews table
CREATE TABLE reviews (
    review_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(book_id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    helpful_votes INTEGER DEFAULT 0,
    total_votes INTEGER DEFAULT 0
);

-- Create reading_status table
CREATE TABLE reading_status (
    status_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(book_id) ON DELETE CASCADE,
    status VARCHAR(20) CHECK (status IN ('want-to-read', 'currently-reading', 'read')),
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_started TIMESTAMP,
    date_finished TIMESTAMP,
    progress_percentage INTEGER DEFAULT 0,
    UNIQUE(user_id, book_id)
);

-- Create trending_books table
CREATE TABLE trending_books (
    trend_id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(book_id) ON DELETE CASCADE,
    trend_type VARCHAR(20) CHECK (trend_type IN ('weekly', 'monthly', 'yearly')),
    read_count INTEGER DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    average_rating NUMERIC(3,2),
    trend_date DATE,
    trend_rank INTEGER
);

-- Create genre_rankings table
CREATE TABLE genre_rankings (
    ranking_id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(book_id) ON DELETE CASCADE,
    genre VARCHAR(100),
    rank_position INTEGER,
    rating_count INTEGER DEFAULT 0,
    average_rating NUMERIC(3,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_google_id ON books(google_book_id);
CREATE INDEX idx_books_category ON books(category);

CREATE INDEX idx_reviews_user_id ON reviews(user_id);
CREATE INDEX idx_reviews_book_id ON reviews(book_id);

CREATE INDEX idx_reading_status_user_id ON reading_status(user_id);
CREATE INDEX idx_reading_status_book_id ON reading_status(book_id);
CREATE INDEX idx_reading_status_status ON reading_status(status);

CREATE INDEX idx_trending_books_type ON trending_books(trend_type);
CREATE INDEX idx_trending_books_rank ON trending_books(trend_rank);

CREATE INDEX idx_genre_rankings_genre ON genre_rankings(genre);
CREATE INDEX idx_genre_rankings_rank ON genre_rankings(rank_position);

-- Success message
SELECT 'BookVault schema created successfully!' as message;
