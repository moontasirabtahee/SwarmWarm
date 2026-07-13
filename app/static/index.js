/* ==============================================================================
   SWARMWARM FRONTEND CONTROLLER (VANILLA JAVASCRIPT SPA WITH SSE TELEMETRY)
   ============================================================================== */

// Global State
let token = localStorage.getItem("swarmwarm_token") || null;
let currentView = "landing";
let activeProvider = "google";
let userEmail = localStorage.getItem("swarmwarm_email") || "";
let sseSource = null;
let isFirstAdminLog = true;

// DOM Views
const landingView = document.getElementById("landing-view");
const authView = document.getElementById("auth-view");
const dashboardView = document.getElementById("dashboard-view");
const onboardModal = document.getElementById("onboard-modal");
const analyticsModal = document.getElementById("analytics-modal");

// Landing Page Elements
const landingLoginBtn = document.getElementById("landing-login-btn");
const landingCtaBtn = document.getElementById("landing-cta-btn");
const backToLanding = document.getElementById("back-to-landing");

// Auth Form Elements
const authForm = document.getElementById("auth-form");
const authTitle = document.getElementById("auth-title");
const authSubtitle = document.getElementById("auth-subtitle");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authError = document.getElementById("auth-error");
const authSubmitBtn = document.getElementById("auth-submit-btn");
const authToggleLink = document.getElementById("auth-toggle-link");
const authToggleMsg = document.getElementById("auth-toggle-msg");

const userEmailDisplay = document.getElementById("user-email-display");
const logoutBtn = document.getElementById("logout-btn");
const addMailboxBtn = document.getElementById("add-mailbox-btn");
const closeOnboardBtn = document.getElementById("close-onboard-btn");
const cancelOnboardBtn = document.getElementById("cancel-onboard-btn");

const onboardForm = document.getElementById("onboard-form");
const providerCards = document.querySelectorAll(".provider-card");
const providerWarning = document.getElementById("provider-warning");
const onboardEmail = document.getElementById("onboard-email");
const onboardSmtpHost = document.getElementById("onboard-smtp-host");
const onboardSmtpPort = document.getElementById("onboard-smtp-port");
const onboardImapHost = document.getElementById("onboard-imap-host");
const onboardImapPort = document.getElementById("onboard-imap-port");
const onboardPassword = document.getElementById("onboard-password");
const onboardSubmitBtn = document.getElementById("onboard-submit-btn");
const onboardSpinner = document.getElementById("onboard-spinner");

const closeAnalyticsBtn = document.getElementById("close-analytics-btn");
const mailboxListBody = document.getElementById("mailbox-list-body");

// Role Console Buttons & Panels
const consoleToggleContainer = document.getElementById("console-toggle-container");
const toggleUserBtn = document.getElementById("toggle-user-btn");
const toggleAdminBtn = document.getElementById("toggle-admin-btn");
const userDashboardPanel = document.getElementById("user-dashboard-panel");
const adminDashboardPanel = document.getElementById("admin-dashboard-panel");
const adminLogStreamBody = document.getElementById("admin-log-stream-body");

// Stats elements
const statSent = document.getElementById("stat-sent");
const statRescued = document.getElementById("stat-rescued");
const statAi = document.getElementById("stat-ai");
const statHealth = document.getElementById("stat-health");
const statHealthFill = document.getElementById("stat-health-fill");

// Mode: login or signup
let isLoginMode = true;

// Initialize Application state
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    if (token) {
        showView("dashboard");
        fetchDashboardData();
        connectSSEStream();
    } else {
        showView("landing");
    }
});

// Decode user role from JWT token
function getRoleFromToken(t) {
    try {
        const base64Url = t.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        const decoded = JSON.parse(jsonPayload);
        return decoded.role || "user";
    } catch(e) {
        return "user";
    }
}

// View Navigation Handler (Landing Page router)
function showView(viewName) {
    currentView = viewName;
    
    // Deactivate all views first
    landingView.classList.remove("active");
    authView.classList.remove("active");
    dashboardView.classList.remove("active");
    
    if (viewName === "landing") {
        landingView.classList.add("active");
    } else if (viewName === "auth") {
        authView.classList.add("active");
    } else if (viewName === "dashboard") {
        dashboardView.classList.add("active");
        userEmailDisplay.textContent = userEmail;
        
        // SECURE ROLE GATE: Only administrators see the Admin Radar toggle options
        const userRole = getRoleFromToken(token);
        console.log(`[AUTH GAUNTLET] User identity resolved. Assigned Role: ${userRole}`);
        
        if (userRole === "admin") {
             consoleToggleContainer.style.display = "flex";
        } else {
             // Standard users are hard-locked into the User View panel
             consoleToggleContainer.style.display = "none";
             toggleUserBtn.classList.add("active");
             toggleAdminBtn.classList.remove("active");
             userDashboardPanel.classList.remove("hidden");
             adminDashboardPanel.classList.add("hidden");
        }
    }
}

// Event Listeners Setup
function setupEventListeners() {
    // Landing navigation routes
    landingLoginBtn.addEventListener("click", () => showView("auth"));
    landingCtaBtn.addEventListener("click", () => showView("auth"));
    backToLanding.addEventListener("click", () => showView("landing"));

    // Auth Mode Toggle
    authToggleLink.addEventListener("click", (e) => {
        e.preventDefault();
        isLoginMode = !isLoginMode;
        authError.classList.add("hidden");
        if (isLoginMode) {
            authTitle.textContent = "Welcome Back";
            authSubtitle.textContent = "Log in to manage your P2P email warmup fleet";
            authSubmitBtn.querySelector("span").textContent = "Sign In";
            authToggleMsg.textContent = "New to SwarmWarm?";
            authToggleLink.textContent = "Create an account";
        } else {
            authTitle.textContent = "Create Account";
            authSubtitle.textContent = "Sign up to join the P2P warmup swarm";
            authSubmitBtn.querySelector("span").textContent = "Sign Up";
            authToggleMsg.textContent = "Already have an account?";
            authToggleLink.textContent = "Sign in here";
        }
    });

    // Auth Submission
    authForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        authError.classList.add("hidden");
        
        const email = authEmail.value.trim();
        const password = authPassword.value;
        
        if (!validateEmail(email)) {
            showAuthError("Please enter a valid email format.");
            return;
        }
        
        authSubmitBtn.disabled = true;
        
        try {
            if (isLoginMode) {
                const formData = new URLSearchParams();
                formData.append("username", email);
                formData.append("password", password);
                
                const response = await fetch("/api/v1/auth/token", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: formData
                });
                
                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || "Authentication failed.");
                }
                
                const data = await response.json();
                token = data.access_token;
                userEmail = email;
                localStorage.setItem("swarmwarm_token", token);
                localStorage.setItem("swarmwarm_email", userEmail);
                
                showView("dashboard");
                fetchDashboardData();
                connectSSEStream();
            } else {
                const response = await fetch("/api/v1/auth/signup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });
                
                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || "Registration failed.");
                }
                
                isLoginMode = true;
                authTitle.textContent = "Welcome Back";
                authSubmitBtn.querySelector("span").textContent = "Sign In";
                authToggleMsg.textContent = "New to SwarmWarm?";
                authToggleLink.textContent = "Create an account";
                authPassword.value = "";
                showAuthSuccess("Account created successfully! Please sign in.");
            }
        } catch (err) {
            showAuthError(err.message);
        } finally {
            authSubmitBtn.disabled = false;
        }
    });

    // Logout Action
    logoutBtn.addEventListener("click", () => {
        token = null;
        userEmail = "";
        localStorage.removeItem("swarmwarm_token");
        localStorage.removeItem("swarmwarm_email");
        if (sseSource) {
            sseSource.close();
            sseSource = null;
        }
        showView("landing");
        authEmail.value = "";
        authPassword.value = "";
    });

    // Modal Actions
    addMailboxBtn.addEventListener("click", () => {
        onboardModal.classList.add("active");
        resetOnboardForm();
    });
    
    closeOnboardBtn.addEventListener("click", () => onboardModal.classList.remove("active"));
    cancelOnboardBtn.addEventListener("click", () => onboardModal.classList.remove("active"));
    closeAnalyticsBtn.addEventListener("click", () => analyticsModal.classList.remove("active"));

    // Provider Selector Cards
    providerCards.forEach(card => {
        card.addEventListener("click", () => {
            providerCards.forEach(c => c.classList.remove("active"));
            card.classList.add("active");
            
            activeProvider = card.dataset.provider;
            updateProviderFields(activeProvider);
        });
    });

    // Onboard Form Submission
    onboardForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            email: onboardEmail.value.trim(),
            smtp_host: onboardSmtpHost.value.trim(),
            smtp_port: parseInt(onboardSmtpPort.value),
            imap_host: onboardImapHost.value.trim(),
            imap_port: parseInt(onboardImapPort.value),
            app_password: onboardPassword.value,
            provider: activeProvider,
            use_ssl: (parseInt(onboardSmtpPort.value) === 465)
        };
        
        onboardSpinner.classList.remove("hidden");
        onboardSubmitBtn.disabled = true;
        
        try {
            const response = await fetch("/api/v1/mailboxes/onboard", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Onboarding connection check failed.");
            }
            
            onboardModal.classList.remove("active");
            fetchDashboardData();
        } catch (err) {
            alert(err.message);
        } finally {
            onboardSpinner.classList.add("hidden");
            onboardSubmitBtn.disabled = false;
        }
    });

    // Console Toggles (Role Selection)
    toggleUserBtn.addEventListener("click", () => {
        toggleUserBtn.classList.add("active");
        toggleUserBtn.style.borderColor = "var(--color-primary)";
        toggleAdminBtn.classList.remove("active");
        toggleAdminBtn.style.borderColor = "transparent";
        userDashboardPanel.classList.remove("hidden");
        adminDashboardPanel.classList.add("hidden");
    });

    toggleAdminBtn.addEventListener("click", () => {
        toggleAdminBtn.classList.add("active");
        toggleAdminBtn.style.borderColor = "var(--color-primary)";
        toggleUserBtn.classList.remove("active");
        toggleUserBtn.style.borderColor = "transparent";
        adminDashboardPanel.classList.remove("hidden");
        userDashboardPanel.classList.add("hidden");
        fetchAdminLogs();
    });
}

// Low-latency Event Telemetry SSE Stream
function connectSSEStream() {
    if (sseSource) {
         sseSource.close();
    }
    
    console.log("[SSE CONNECT] Establishing real-time event telemetry stream...");
    sseSource = new EventSource(`/api/v1/analytics/stream?token=${encodeURIComponent(token)}`);
    
    sseSource.onmessage = (event) => {
         const data = JSON.parse(event.data);
         
         // 1. Dynamic Delta Counters (UI transitions)
         if (data.metrics) {
              statSent.textContent = data.metrics.total_sent_24h;
              statRescued.textContent = data.metrics.spam_rescues_24h;
              statAi.textContent = data.metrics.ai_replies_activated_24h;
              statHealth.textContent = `${data.metrics.inbox_placement_rate}%`;
              statHealthFill.style.width = `${data.metrics.inbox_placement_rate}%`;
         }
         
         // 2. Admin System radar telemetry (Only update elements if they exist in DOM and role is admin)
         const userRole = getRoleFromToken(token);
         if (userRole === "admin" && data.system_radar) {
              document.getElementById("admin-redis-backlog").textContent = `${data.system_radar.redis_backlog} Tasks Pending`;
              document.getElementById("admin-gemma-speed").textContent = `${data.system_radar.inference_speed} Tokens/Sec`;
              document.getElementById("admin-temp").textContent = `${data.system_radar.hardware_temp}°C`;
         }
         
         // 3. Append to admin operations log stream table if we are in admin view
         if (userRole === "admin" && data.new_log) {
              appendAdminLogStream(data.new_log);
         }
    };
    
    sseSource.onerror = (err) => {
         console.warn("[SSE ERROR] Telemetry stream dropped. EventSource will auto-reconnect.");
    };
}

// Fetch global system logs from backend for admin radar table
async function fetchAdminLogs() {
    try {
        const response = await fetch("/api/v1/admin/system/logs", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.ok) {
            const logs = await response.json();
            adminLogStreamBody.innerHTML = "";
            if (logs.length === 0) {
                adminLogStreamBody.innerHTML = `<tr><td colspan="5" class="table-empty">No background system audit logs found.</td></tr>`;
                return;
            }
            logs.forEach(log => {
                const tr = document.createElement("tr");
                let levelTag = "status-success";
                if (log.level === "ERROR") {
                     levelTag = "status-red";
                } else if (log.level === "WARN") {
                     levelTag = "status-rescued";
                }
                tr.innerHTML = `
                    <td><code>${log.timestamp}</code></td>
                    <td><code>global_swarm</code></td>
                    <td><span class="status-tag status-sent">${log.module}</span></td>
                    <td>${log.event}</td>
                    <td><span class="status-tag ${levelTag}">${log.level}</span></td>
                `;
                adminLogStreamBody.appendChild(tr);
            });
            isFirstAdminLog = false;
        }
    } catch (err) {
         console.error("Failed to load admin system logs:", err);
    }
}

// Append new operations to admin log ledger table in real time
function appendAdminLogStream(log) {
    if (isFirstAdminLog) {
         adminLogStreamBody.innerHTML = "";
         isFirstAdminLog = false;
    }
    
    const tr = document.createElement("tr");
    
    let actionTag = "status-sent";
    if (log.action === "rescued") {
         actionTag = "status-rescued";
    }
    
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    tr.innerHTML = `
        <td>${timeStr}</td>
        <td><code>${log.user_id}</code></td>
        <td><span class="status-tag ${log.ai_replied ? 'status-success' : 'status-sent'}">${log.ai_replied ? 'AI_SERVICE' : 'CELERY_WORKER'}</span></td>
        <td>Dispatched warmup transaction to swarm</td>
        <td><span class="status-tag ${actionTag}">${log.action.toUpperCase()}</span></td>
    `;
    
    adminLogStreamBody.insertBefore(tr, adminLogStreamBody.firstChild);
    
    if (adminLogStreamBody.children.length > 20) {
         adminLogStreamBody.removeChild(adminLogStreamBody.lastChild);
    }
}

// Update form fields depending on Provider selected
function updateProviderFields(provider) {
    if (provider === "google") {
        providerWarning.classList.remove("hidden");
        providerWarning.querySelector("strong").textContent = "Google Workspace Security Notice:";
        providerWarning.querySelector("p").textContent = "Do NOT enter your primary account password. You MUST generate a 16-character App Password in your Google Account Settings to authorize connection.";
        onboardSmtpHost.value = "smtp.gmail.com";
        onboardSmtpPort.value = "465";
        onboardImapHost.value = "imap.gmail.com";
        onboardImapPort.value = "993";
    } else if (provider === "microsoft") {
        providerWarning.classList.remove("hidden");
        providerWarning.querySelector("strong").textContent = "Microsoft 365 Security Notice:";
        providerWarning.querySelector("p").textContent = "Ensure MFA is enabled and generate an App Password inside your Microsoft Security settings page to authorize SMTP/IMAP connections.";
        onboardSmtpHost.value = "smtp.office365.com";
        onboardSmtpPort.value = "587";
        onboardImapHost.value = "outlook.office365.com";
        onboardImapPort.value = "993";
    } else {
        providerWarning.classList.add("hidden");
        onboardSmtpHost.value = "";
        onboardSmtpPort.value = "587";
        onboardImapHost.value = "";
        onboardImapPort.value = "993";
    }
}

// Reset Onboarding Forms
function resetOnboardForm() {
    onboardForm.reset();
    providerCards.forEach(c => c.classList.remove("active"));
    providerCards[0].classList.add("active");
    activeProvider = "google";
    updateProviderFields("google");
}

// Retrieve telemetry stats and mailbox fleet records
async function fetchDashboardData() {
    try {
        const analyticsRes = await fetch("/api/v1/analytics/overview", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (analyticsRes.ok) {
            const data = await analyticsRes.json();
            statSent.textContent = data.metrics.total_sent_24h;
            statRescued.textContent = data.metrics.spam_rescues_24h;
            statAi.textContent = data.metrics.ai_replies_activated_24h;
            statHealth.textContent = `${data.metrics.inbox_placement_rate}%`;
            statHealthFill.style.width = `${data.metrics.inbox_placement_rate}%`;
        }
        
        const mailboxesRes = await fetch("/api/v1/mailboxes", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (mailboxesRes.ok) {
            const mailboxes = await mailboxesRes.json();
            renderMailboxesTable(mailboxes);
        }
    } catch (err) {
        console.error("Dashboard synchronization error:", err);
    }
}

// Render Mailbox Fleet
function renderMailboxesTable(mailboxes) {
    if (mailboxes.length === 0) {
        mailboxListBody.innerHTML = `
            <tr>
                <td colspan="6" class="table-empty">
                    <i class="fa-solid fa-inbox"></i>
                    <p>No mailboxes onboarded yet. Connect your first inbox to join the swarm!</p>
                </td>
            </tr>
        `;
        return;
    }
    
    mailboxListBody.innerHTML = "";
    mailboxes.forEach(m => {
        const tr = document.createElement("tr");
        
        tr.addEventListener("click", (e) => {
             if (e.target.closest(".switch") || e.target.closest("input") || e.target.closest(".btn-delete")) return;
             openAnalyticsModal(m);
        });
        
        tr.innerHTML = `
            <td><strong>${m.email}</strong></td>
            <td><span class="badge badge-indigo">${m.provider}</span></td>
            <td>${m.smtp_host}:${m.smtp_port}</td>
            <td>${m.imap_host}:${m.imap_port}</td>
            <td>
                <span class="status-tag ${m.is_active ? 'status-success' : 'status-rescued'}">
                    ${m.is_active ? 'Active' : 'Paused'}
                </span>
            </td>
            <td class="text-right">
                <div class="mailbox-actions-cell">
                    <label class="switch">
                        <input type="checkbox" ${m.is_active ? 'checked' : ''} data-id="${m.id}">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-delete" data-id="${m.id}" title="Remove Mailbox">
                        <i class="fa-regular fa-trash-can"></i>
                    </button>
                </div>
            </td>
        `;
        
        const toggleCheckbox = tr.querySelector("input[type='checkbox']");
        toggleCheckbox.addEventListener("change", async () => {
             tr.style.filter = "blur(1px)";
             tr.style.opacity = "0.7";
             
             try {
                  const toggleRes = await fetch(`/api/v1/mailboxes/${m.id}/toggle`, {
                       method: "PATCH",
                       headers: { "Authorization": `Bearer ${token}` }
                  });
                  if (!toggleRes.ok) {
                       throw new Error("Toggle status update failed.");
                  }
                  fetchDashboardData();
             } catch (err) {
                  alert(err.message);
                  toggleCheckbox.checked = !toggleCheckbox.checked;
             } finally {
                  tr.style.filter = "none";
                  tr.style.opacity = "1";
             }
        });
        
        const deleteBtn = tr.querySelector(".btn-delete");
        deleteBtn.addEventListener("click", async (e) => {
             e.stopPropagation();
             if (!confirm(`Are you sure you want to remove mailbox ${m.email} from the P2P swarm?`)) {
                  return;
             }
             tr.style.filter = "blur(1px)";
             tr.style.opacity = "0.7";
             
             try {
                  const deleteRes = await fetch(`/api/v1/mailboxes/${m.id}`, {
                       method: "DELETE",
                       headers: { "Authorization": `Bearer ${token}` }
                  });
                  if (!deleteRes.ok) {
                       throw new Error("Delete mailbox failed.");
                  }
                  fetchDashboardData();
             } catch (err) {
                  alert(err.message);
                  tr.style.filter = "none";
                  tr.style.opacity = "1";
             }
        });
        
        mailboxListBody.appendChild(tr);
    });
}

// Open deep analytics panel
async function openAnalyticsModal(mailbox) {
    analyticsModal.classList.add("active");
    
    document.getElementById("node-details-email").textContent = mailbox.email;
    document.getElementById("node-details-id").textContent = `Node ID: ${mailbox.id}`;
    
    const rampVal = mailbox.is_active ? 18 : 0;
    const progressPercent = mailbox.is_active ? 45.0 : 0;
    
    document.getElementById("node-ramp-val").textContent = `${rampVal} / 40 daily sends`;
    document.getElementById("node-ramp-fill").style.width = `${progressPercent}%`;
    
    const logsBody = document.getElementById("node-logs-body");
    logsBody.innerHTML = `
        <tr>
            <td colspan="5" class="table-empty">
                <i class="fa-solid fa-circle-notch fa-spin"></i>
                <p>Loading activity ledger...</p>
            </td>
        </tr>
    `;
    
    try {
        const response = await fetch(`/api/v1/mailboxes/${mailbox.id}/logs`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.ok) {
            const logs = await response.json();
            if (logs.length === 0) {
                logsBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="table-empty">No activity logs recorded. Warmup loops schedule nightly.</td>
                    </tr>
                `;
                return;
            }
            logsBody.innerHTML = "";
            logs.forEach(log => {
                const tr = document.createElement("tr");
                
                // Format timestamp
                let dateStr = "Recent";
                if (log.created_at) {
                    try {
                        const dt = new Date(log.created_at);
                        dateStr = dt.toISOString().slice(0,10) + " " + dt.toTimeString().slice(0,5);
                    } catch(e) {}
                }
                
                const actionTag = log.action === "sent" ? "OUTBOUND SEND" : "SPAM RESCUE";
                const actionClass = log.action === "sent" ? "status-sent" : "status-rescued";
                
                tr.innerHTML = `
                    <td>${dateStr}</td>
                    <td><span class="status-tag ${actionClass}">${actionTag}</span></td>
                    <td>${log.recipient_email || 'inbox@domain.com'}</td>
                    <td><i class="fa-solid ${log.ai_replied ? 'fa-check text-google' : 'fa-xmark text-muted'}"></i> ${log.ai_replied ? 'Yes' : 'No'}</td>
                    <td><span class="status-tag status-success">${log.action === "sent" ? "DELIVERED" : "RESCUED"}</span></td>
                `;
                logsBody.appendChild(tr);
            });
        } else {
             logsBody.innerHTML = `<tr><td colspan="5" class="table-empty">Failed to load database logs.</td></tr>`;
        }
    } catch(err) {
         logsBody.innerHTML = `<tr><td colspan="5" class="table-empty">Failed to query ledger: ${err.message}</td></tr>`;
    }
}

// Client helper validators
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function showAuthError(msg) {
    authError.className = "alert-box error";
    authError.querySelector(".alert-msg").textContent = msg;
    authError.classList.remove("hidden");
}

function showAuthSuccess(msg) {
    authError.className = "alert-box warning";
    authError.querySelector(".alert-msg").textContent = msg;
    authError.classList.remove("hidden");
}
