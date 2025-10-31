// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// Simple utility to get auth token from localStorage
function getAuthToken() {
    return localStorage.getItem('access_token');
}

// Store auth token
function setAuthToken(token) {
    localStorage.setItem('access_token', token);
}

// Remove auth token
function removeAuthToken() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_email');
}

// Get current user ID
function getCurrentUserId() {
    return localStorage.getItem('user_id');
}

// Generic API call function
async function apiCall(endpoint, options = {}) {
    const token = getAuthToken();
    
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    
    // Add auth header if token exists (unless it's a public endpoint)
    if (token && !options.skipAuth) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const config = {
        ...options,
        headers,
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        
        // If unauthorized, redirect to login
        if (response.status === 401) {
            removeAuthToken();
            window.location.href = '/login.html';
            return null;
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'API request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Authentication API calls
const AuthAPI = {
    async login(email, password) {
        const data = await apiCall('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
            skipAuth: true,
        });
        
        if (data && data.access_token) {
            setAuthToken(data.access_token);
            if (data.refresh_token) {
                localStorage.setItem('refresh_token', data.refresh_token);
            }
        }
        
        return data;
    },
    
    async register(userData) {
        return await apiCall('/users', {
            method: 'POST',
            body: JSON.stringify(userData),
            skipAuth: true,
        });
    },
    
    async refreshToken(refreshToken) {
        const data = await apiCall('/auth/refresh', {
            method: 'POST',
            body: JSON.stringify({ refresh_token: refreshToken }),
            skipAuth: true,
        });
        
        if (data && data.access_token) {
            setAuthToken(data.access_token);
        }
        
        return data;
    },
    
    logout() {
        removeAuthToken();
        window.location.href = '/login.html';
    }
};

// User API calls
const UserAPI = {
    async getProfile(userId) {
        return await apiCall(`/users/${userId}`);
    },
    
    async updateProfile(userId, userData) {
        return await apiCall(`/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(userData),
        });
    },
    
    async getWalletAccounts(userId) {
        return await apiCall(`/users/${userId}/accounts`);
    },
    
    async createWalletAccount(userId, currencyCode) {
        return await apiCall(`/users/${userId}/accounts`, {
            method: 'POST',
            body: JSON.stringify({ currency_code: currencyCode }),
        });
    },
    
    async getKYCStatus(userId) {
        return await apiCall(`/users/${userId}/kyc`);
    },
    
    async submitKYC(userId, kycData) {
        return await apiCall(`/users/${userId}/kyc`, {
            method: 'POST',
            body: JSON.stringify(kycData),
        });
    }
};

// Loan Application API calls
const LoanAPI = {
    async getUserApplications(userId) {
        return await apiCall(`/users/${userId}/loan-application`);
    },
    
    async getApplication(userId, appId) {
        return await apiCall(`/users/${userId}/loan-applications/${appId}`);
    },
    
    async createApplication(userId, applicationData) {
        return await apiCall(`/users/${userId}/loan-application`, {
            method: 'POST',
            body: JSON.stringify(applicationData),
        });
    },
    
    async updateApplication(userId, appId, applicationData) {
        return await apiCall(`/users/${userId}/loan-applications/${appId}`, {
            method: 'PUT',
            body: JSON.stringify(applicationData),
        });
    },
    
    async getOffers(userId, appId) {
        return await apiCall(`/users/${userId}/loan-applications/${appId}/offers`);
    },
    
    async createOffer(userId, appId, offerData) {
        return await apiCall(`/users/${userId}/loan-applications/${appId}/offers`, {
            method: 'POST',
            body: JSON.stringify(offerData),
        });
    },
    
    async getUserLoans(userId, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/users/${userId}/loans${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    },
    
    async getRiskAssessment(userId, appId) {
        return await apiCall(`/users/${userId}/loan-applications/${appId}/risk-assessment`);
    }
};

// Transaction API calls
const TransactionAPI = {
    async getAccountTransactions(accountId, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/accounts/${accountId}/transactions${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    }
};

// Admin API calls
const AdminAPI = {
    async approveLoan(loanId, approvalData) {
        return await apiCall(`/admin/loans/${loanId}/approve`, {
            method: 'POST',
            body: JSON.stringify(approvalData),
        });
    },
    
    async rejectLoan(loanId, rejectionData) {
        return await apiCall(`/admin/loans/${loanId}/reject`, {
            method: 'POST',
            body: JSON.stringify(rejectionData),
        });
    },
    
    async getAuditLogs(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/admin/audit-logs${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    },
    
    async getDelinquencyReports(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/admin/delinquency${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    },
    
    async getTransactions(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/admin/transactions${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    }
};

// Reporting API calls
const ReportAPI = {
    async getPlatformMetrics(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/reports/platform-metrics${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    },
    
    async getRevenueReport(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = `/reports/revenue${queryString ? '?' + queryString : ''}`;
        return await apiCall(endpoint);
    }
};

// Helper function to check if user is authenticated
function isAuthenticated() {
    // TEMPORARILY DISABLED FOR DEMO - Return true to allow access without login
    return true;
}

// Helper function to protect pages (redirect to login if not authenticated)
function requireAuth() {
    // TEMPORARILY DISABLED FOR DEMO - Allow access without auth check
    return true;
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AuthAPI,
        UserAPI,
        LoanAPI,
        TransactionAPI,
        AdminAPI,
        ReportAPI,
        isAuthenticated,
        requireAuth,
        getCurrentUserId,
        getAuthToken,
    };
}
