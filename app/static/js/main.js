/**
 * WarrantyPro Custom JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Clickable Rows (Tables)
    const clickableRows = document.querySelectorAll('.clickable-row');
    clickableRows.forEach(row => {
        row.addEventListener('click', (e) => {
            // Prevent navigating if clicking a button inside the row
            if (!e.target.closest('button') && !e.target.closest('a')) {
                window.location.href = row.dataset.href;
            }
        });
    });

    // 2. Fetch Notifications Badge Count & Red Dot
    const notifBadge = document.getElementById('notifBadge');
    const notifDot   = document.getElementById('notifDot');
    const sidebarDot = document.querySelector('.sidebar-notif-dot');

    if (notifBadge || notifDot || sidebarDot) {
        fetch('/api/v1/notifications')
            .then(res => {
                if (res.ok) return res.json();
                throw new Error('Not auth');
            })
            .then(data => {
                if (data.length > 0) {
                    // Navbar badge with count
                    if (notifBadge) {
                        notifBadge.textContent = data.length > 99 ? '99+' : data.length;
                        notifBadge.style.display = 'block';
                    }
                    // Navbar pulsing red dot
                    if (notifDot) notifDot.style.display = 'block';
                    // Sidebar red dot next to Notifications link
                    if (sidebarDot) sidebarDot.style.display = 'block';
                }
            })
            .catch(err => console.log('Notification fetch skipped:', err));
    }

    // 3. Auto-hide flash messages
    const flashMessages = document.querySelectorAll('.flash-container .alert');
    flashMessages.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000); // 5 seconds
    });
});
