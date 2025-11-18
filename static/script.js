// BookVault JavaScript - AJAX and Dynamic Interactions

// Search functionality
let searchTimeout;

function searchBooks() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }
    
    // Show loading
    document.getElementById('searchResults').innerHTML = '<div class="text-center p-3"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    
    // Debounce search
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        fetch(`/search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                displaySearchResults(data);
            })
            .catch(error => {
                console.error('Search error:', error);
                document.getElementById('searchResults').innerHTML = '<div class="alert alert-danger">Search failed. Please try again.</div>';
            });
    }, 300);
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    
    if (results.length === 0) {
        container.innerHTML = '<div class="text-center p-3 text-muted">No books found</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    
    results.forEach(book => {
        const coverUrl = book.cover || 'https://via.placeholder.com/60x90?text=No+Cover';
        const source = book.source === 'local' ? '<span class="badge bg-success">In Library</span>' : '<span class="badge bg-info">Google Books</span>';
        
        if (book.source === 'local') {
            // Local book - link to details page
            html += `
                <a href="/book/${book.id}" class="list-group-item list-group-item-action search-result-item">
                    <div class="d-flex align-items-center">
                        <img src="${coverUrl}" class="search-book-cover me-3" alt="${book.title}">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${book.title}</h6>
                            <p class="mb-1 text-muted small">${book.author}</p>
                            <p class="mb-0 small text-truncate">${book.description}</p>
                        </div>
                        <div class="text-end">
                            ${source}
                        </div>
                    </div>
                </a>
            `;
        } else {
            // Google Books result - show add to shelf buttons
            const bookData = JSON.stringify(book.data).replace(/"/g, '&quot;');
            html += `
                <div class="list-group-item search-result-item">
                    <div class="d-flex align-items-center">
                        <img src="${coverUrl}" class="search-book-cover me-3" alt="${book.title}">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${book.title}</h6>
                            <p class="mb-1 text-muted small">${book.author}</p>
                            <p class="mb-0 small text-truncate">${book.description}</p>
                        </div>
                        <div class="text-end">
                            ${source}
                            <div class="btn-group btn-group-sm mt-2" role="group">
                                <button class="btn btn-outline-primary" onclick='addGoogleBookToShelf(${bookData}, "want-to-read")'>
                                    <i class="fas fa-bookmark"></i>
                                </button>
                                <button class="btn btn-outline-success" onclick='addGoogleBookToShelf(${bookData}, "currently-reading")'>
                                    <i class="fas fa-book-open"></i>
                                </button>
                                <button class="btn btn-outline-secondary" onclick='addGoogleBookToShelf(${bookData}, "read")'>
                                    <i class="fas fa-check"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Add book to shelf (local books)
function addToShelf(bookId, status) {
    if (!bookId) {
        alert('Please login to add books to your shelf');
        return;
    }
    
    const formData = new FormData();
    formData.append('book_id', bookId);
    formData.append('status', status);
    
    fetch('/add-to-shelf', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Book added to ' + status.replace('-', ' '), 'success');
            // Reload page after short delay to show updated shelf
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showNotification(data.message || 'Failed to add book', 'error');
            if (response.status === 401) {
                // User not logged in
                window.location.href = '/';
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred', 'error');
    });
}

// Add Google Books result to shelf
function addGoogleBookToShelf(bookData, status) {
    const formData = new FormData();
    formData.append('google_book_id', bookData.google_book_id);
    formData.append('title', bookData.title);
    formData.append('author', bookData.author);
    formData.append('isbn', bookData.isbn || '');
    formData.append('publication_date', bookData.publication_date || '');
    formData.append('description', bookData.description || '');
    formData.append('cover_image_url', bookData.cover_image_url || '');
    formData.append('category', bookData.category || 'General');
    formData.append('page_count', bookData.page_count || '0');
    formData.append('language', bookData.language || 'en');
    formData.append('status', status);
    
    fetch('/add-to-shelf', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Book added to your library and ' + status.replace('-', ' '), 'success');
            // Clear search and reload after delay
            setTimeout(() => {
                document.getElementById('searchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
                window.location.href = '/book/' + data.book_id;
            }, 1000);
        } else {
            showNotification(data.message || 'Failed to add book', 'error');
            if (data.message && data.message.includes('login')) {
                // Show login modal
                setTimeout(() => {
                    const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                    loginModal.show();
                }, 1500);
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred', 'error');
    });
}

// Update reading progress
function updateProgress(bookId, progress) {
    const formData = new FormData();
    formData.append('book_id', bookId);
    formData.append('progress', progress);
    
    fetch('/update-progress', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Progress updated to ' + progress + '%', 'success');
            
            // Update progress bar if it exists
            const progressBar = document.querySelector(`[data-book-id="${bookId}"] .progress-bar`);
            if (progressBar) {
                progressBar.style.width = progress + '%';
                progressBar.textContent = progress + '%';
            }
        } else {
            showNotification(data.message || 'Failed to update progress', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred', 'error');
    });
}

// Delete review
function deleteReview(reviewId) {
    if (!confirm('Are you sure you want to delete this review?')) {
        return;
    }
    
    fetch(`/delete-review/${reviewId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Review deleted successfully', 'success');
            // Reload page after short delay
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showNotification(data.message || 'Failed to delete review', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred', 'error');
    });
}

// Show notification
function showNotification(message, type) {
    const alertClass = type === 'error' ? 'danger' : type;
    const alertHtml = `
        <div class="alert alert-${alertClass} alert-dismissible fade show position-fixed top-0 end-0 m-3" role="alert" style="z-index: 9999;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // Auto dismiss after 3 seconds
    setTimeout(() => {
        const alert = document.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, 3000);
}

// Real-time search on input
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', searchBooks);
        
        // Search on Enter key
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchBooks();
            }
        });
    }
});

// Form validation
(function() {
    'use strict';
    
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
})();
