const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS for API requests
app.use(cors());

// Serve static files from the current directory
app.use(express.static(__dirname));

// Route for root - redirect to login
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
    console.log('\n🚀 MicroLending Frontend Server');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`✅ Server running at: http://localhost:${PORT}`);
    console.log(`📱 Dashboard: http://localhost:${PORT}/dashboard.html`);
    console.log(`🔐 Login: http://localhost:${PORT}/login.html`);
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('💡 Press Ctrl+C to stop the server\n');
});
