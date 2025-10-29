// Navigation Component for Authenticated Pages
class Navigation {
    static render(activePage = '') {
        return `
            <nav class="main-nav">
                <div class="nav-container">
                    <div class="nav-brand">
                        <a href="dashboard.html">
                            <i class="fas fa-chart-line"></i>
                            MicroLending
                        </a>
                    </div>
                    <ul class="nav-menu">
                        <li class="${activePage === 'dashboard' ? 'active' : ''}">
                            <a href="dashboard.html">
                                <i class="fas fa-home"></i>
                                Dashboard
                            </a>
                        </li>
                        <li class="${activePage === 'wallet' ? 'active' : ''}">
                            <a href="wallet.html">
                                <i class="fas fa-wallet"></i>
                                Wallet
                            </a>
                        </li>
                        <li class="${activePage === 'my-loans' ? 'active' : ''}">
                            <a href="my-loans.html">
                                <i class="fas fa-file-invoice-dollar"></i>
                                My Loans
                            </a>
                        </li>
                        <li class="${activePage === 'browse-loans' ? 'active' : ''}">
                            <a href="browse-loans.html">
                                <i class="fas fa-search-dollar"></i>
                                Browse Loans
                            </a>
                        </li>
                        <li class="${activePage === 'apply-loan' ? 'active' : ''}">
                            <a href="apply-loan.html">
                                <i class="fas fa-plus-circle"></i>
                                Apply for Loan
                            </a>
                        </li>
                    </ul>
                    <div class="nav-user">
                        <div class="user-info">
                            <span id="nav-user-name">Loading...</span>
                            <small id="nav-user-email"></small>
                        </div>
                        <button onclick="Navigation.logout()" class="btn-logout">
                            <i class="fas fa-sign-out-alt"></i>
                            Logout
                        </button>
                    </div>
                </div>
            </nav>
        `;
    }

    static async init(activePage = '') {
        // TEMPORARILY DISABLED FOR DEMO - Skip authentication check
        // if (!isAuthenticated()) {
        //     window.location.href = '/login.html';
        //     return;
        // }

        // Insert navigation
        const navPlaceholder = document.getElementById('nav-placeholder');
        if (navPlaceholder) {
            navPlaceholder.innerHTML = this.render(activePage);
        }

        // Load user info
        try {
            const user = await UserAPI.getProfile();
            if (document.getElementById('nav-user-name')) {
                document.getElementById('nav-user-name').textContent = `${user.first_name} ${user.last_name}`;
            }
            if (document.getElementById('nav-user-email')) {
                document.getElementById('nav-user-email').textContent = user.email;
            }
        } catch (error) {
            console.error('Failed to load user info:', error);
            // Use demo user name for demo purposes
            if (document.getElementById('nav-user-name')) {
                document.getElementById('nav-user-name').textContent = 'Demo User';
            }
        }
    }

    static logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login.html';
    }
}
