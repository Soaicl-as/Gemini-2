document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const twoFaSection = document.getElementById('2fa-section');
    const twoFaForm = document.getElementById('2fa-form');
    const botActionsSection = document.getElementById('bot-actions-section');
    const getListForm = document.getElementById('get-list-form');
    const userListOutput = document.getElementById('user-list-output');
    const sendDmForm = document.getElementById('send-dm-form');
    const logOutput = document.getElementById('log-output');
    const statusMessage = document.getElementById('status-message');

    // Function to update status message
    function updateStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = 'mt-6 text-center text-sm font-medium ' + (isError ? 'text-red-600' : 'text-gray-700');
    }

    // Function to append logs to the log output area
    function appendLog(logEntry) {
        const logElement = document.createElement('p');
        // Basic attempt to color logs based on keywords (can be improved)
        if (logEntry.includes('ERROR') || logEntry.includes('Failed')) {
            logElement.className = 'log-error';
        } else if (logEntry.includes('WARNING') || logEntry.includes('Rate limit')) {
             logElement.className = 'log-warning';
        } else if (logEntry.includes('INFO') || logEntry.includes('Successfully')) {
             logElement.className = 'log-info';
        }
        logElement.textContent = logEntry;
        logOutput.appendChild(logElement);
        // Auto-scroll to the bottom
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    // Start streaming logs from the backend
    const eventSource = new EventSource('/logs');
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data && data.log) {
            appendLog(data.log);
        }
    };
    eventSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        appendLog("ERROR: Log streaming failed. Refresh the page or check server logs.");
        eventSource.close(); // Close the connection on error
    };


    // Check login status on page load
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            if (data.logged_in) {
                loginForm.classList.add('hidden');
                botActionsSection.classList.remove('hidden');
                updateStatus("Logged in.");
            } else {
                loginForm.classList.remove('hidden');
                botActionsSection.classList.add('hidden');
                updateStatus("Please log in to Instagram.");
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
            updateStatus("Could not connect to backend. Ensure the server is running.", true);
        });


    // Handle Login Form Submission
    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        updateStatus("Logging in...");

        const formData = new FormData(loginForm);
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (result.status === 'success') {
            updateStatus(result.message);
            loginForm.classList.add('hidden');
            twoFaSection.classList.add('hidden');
            botActionsSection.classList.remove('hidden');
        } else if (result.status === '2fa_required') {
            updateStatus(result.message, true);
            loginForm.classList.add('hidden');
            twoFaSection.classList.remove('hidden');
        } else {
            updateStatus(result.message, true);
            loginForm.classList.remove('hidden');
            twoFaSection.classList.add('hidden');
        }
    });

    // Handle 2FA Form Submission
    twoFaForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        updateStatus("Submitting 2FA code...");

        const formData = new FormData(twoFaForm);
        const response = await fetch('/complete-2fa', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (result.status === 'success') {
            updateStatus(result.message);
            twoFaSection.classList.add('hidden');
            botActionsSection.classList.remove('hidden');
        } else {
            updateStatus(result.message, true);
            twoFaSection.classList.remove('hidden'); // Keep 2FA form visible on error
        }
    });

    // Handle Get List Form Submission
    getListForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        userListOutput.innerHTML = '<p>Fetching list...</p>';
        updateStatus("Fetching user list...");

        const formData = new FormData(getListForm);
        const response = await fetch('/get-list', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        userListOutput.innerHTML = ''; // Clear previous list

        if (response.ok && result.status === 'success') {
            updateStatus(`Successfully fetched ${result.users.length} users.`);
            if (result.users && result.users.length > 0) {
                const listHtml = result.users.map(user =>
                    `<p>PK: ${user.pk}, Username: ${user.username}, Full Name: ${user.full_name}</p>`
                ).join('');
                userListOutput.innerHTML = listHtml;

                // Populate recipient PKs textarea with fetched PKs
                const recipientPksTextarea = document.getElementById('recipient-pks');
                recipientPksTextarea.value = result.users.map(user => user.pk).join(', ');

            } else {
                userListOutput.innerHTML = '<p>No users found or list is empty.</p>';
            }
        } else if (response.ok && result.status === 'warning') {
             updateStatus(result.message, true); // Display warning
             userListOutput.innerHTML = `<p class="text-orange-600">${result.message}</p>`;
        }
        else {
            const errorDetail = result.detail || 'Unknown error';
            updateStatus(`Failed to fetch list: ${errorDetail}`, true);
            userListOutput.innerHTML = `<p class="text-red-600">Error: ${errorDetail}</p>`;
        }
    });

    // Handle Send DM Form Submission
    sendDmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        updateStatus("Starting mass DM process...");

        const formData = new FormData(sendDmForm);
        // Ensure recipient_pks is sent as a string
        formData.set('recipient_pks', document.getElementById('recipient-pks').value);

        const response = await fetch('/send-dm', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (response.ok && result.status === 'processing') {
            updateStatus(result.message);
            // Logs will provide real-time updates
        } else {
            const errorDetail = result.detail || 'Unknown error';
            updateStatus(`Failed to start DM process: ${errorDetail}`, true);
        }
    });
});
