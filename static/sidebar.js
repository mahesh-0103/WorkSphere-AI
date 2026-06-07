// WorkSphere AI Shared Session & Navigation Helper Script (sidebar.js)
(function() {
    // 1. Token Extraction and Race-Free URL Cleaning
    const urlParams = new URLSearchParams(window.location.search);
    let token = urlParams.get('token');
    let provider = urlParams.get('provider');
    let needsClean = false;
    
    if (token) {
        localStorage.setItem('worksphere_token', token);
        urlParams.delete('token');
        needsClean = true;
    } else {
        token = localStorage.getItem('worksphere_token');
    }

    if (provider) {
        localStorage.setItem('ws_provider', provider);
        urlParams.delete('provider');
        needsClean = true;
    }

    if (needsClean) {
        const newQuery = urlParams.toString();
        const newPath = window.location.pathname + (newQuery ? '?' + newQuery : '');
        window.history.replaceState({}, document.title, newPath);
    }

    // Redirect to login if token is missing
    if (!token && window.location.pathname !== '/') {
        window.location.href = '/';
        return;
    }

    window.worksphere_token = token;

    // 2. Inject Styles for Toast
    const toastStyle = document.createElement('style');
    toastStyle.textContent = `
        #worksphere-toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 11000;
            padding: 12px 18px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid #cfc4c5;
            background-color: #ffffff;
            color: #1a1c1c;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            transform: translateY(20px);
            opacity: 0;
            pointer-events: none;
        }
        #worksphere-toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        #worksphere-toast.error {
            border-color: #ba1a1a;
            background-color: #ffdad6;
            color: #ba1a1a;
        }
        .ws-profile-shimmer {
            display: inline-block;
            width: 80px;
            height: 14px;
            background: linear-gradient(90deg, #e2e2e2, #f3f3f3, #e2e2e2);
            background-size: 200% 100%;
            animation: ws-profile-pulse 1.5s ease-in-out infinite;
            border-radius: 3px;
            vertical-align: middle;
        }
        @keyframes ws-profile-pulse {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
    `;
    document.head.appendChild(toastStyle);

    // 3. Global Toast Function
    window.showToast = function(message, type = 'info') {
        let toast = document.getElementById('worksphere-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'worksphere-toast';
            document.body.appendChild(toast);
        }

        toast.textContent = message;
        if (type === 'error') {
            toast.classList.add('error');
        } else {
            toast.classList.remove('error');
        }

        toast.classList.add('show');

        if (window.wsToastTimeout) clearTimeout(window.wsToastTimeout);
        window.wsToastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    };

    // 4. Wire Sidebar Links & Highlights on DOM Load
    function setupInteractions() {
        const path = window.location.pathname;

        // Dynamically change 'Connect Account' to 'Logout' if token is present
        const connectBtn = document.getElementById('add-instance-btn') || document.getElementById('connect-account-btn');
        if (connectBtn) {
            if (token) {
                connectBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">logout</span><span class="hidden md:inline ml-2">Logout</span>';
                connectBtn.onclick = async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                        await fetch('/auth/logout', { method: 'POST' });
                    } catch (err) { /* ignore */ }
                    localStorage.removeItem('worksphere_token');
                    localStorage.removeItem('ws_token');
                    localStorage.removeItem('ws_briefing');
                    localStorage.removeItem('ws_provider');
                    window.location.href = '/';
                };
            }
        }

        // Render Custom Agents from LocalStorage first (before links wiring)
        const agentContainer = document.querySelector('#agent-nodes-container') || 
                               Array.from(document.querySelectorAll('nav div.px-sm.space-y-xs')).find(el => el.querySelector('.status-indicator') || el.textContent.includes('Agent'));
        
        if (agentContainer) {
            const customAgents = JSON.parse(localStorage.getItem('worksphere_custom_agents') || '[]');
            customAgents.forEach(agent => {
                const agentDiv = document.createElement('div');
                
                // check if the container is the right panel active agents or the sidebar
                const isRightPanel = agentContainer.id === 'agent-nodes-container' && path === '/dashboard';
                if (isRightPanel) {
                    agentDiv.className = 'flex items-center justify-between p-sm bg-white instrument-border rounded-lg';
                    agentDiv.innerHTML = `
                        <div class="flex items-center space-x-sm">
                            <span class="material-symbols-outlined text-secondary/70">${agent.icon}</span>
                            <span class="text-sm font-medium text-on-surface">${agent.name}</span>
                        </div>
                        <div class="flex items-center space-x-xs bg-neutral-100 px-sm py-[2px] rounded-full status-pill-container">
                            <div class="w-1.5 h-1.5 bg-neutral-400 rounded-full status-indicator"></div>
                            <span class="text-[10px] font-semibold text-neutral-500 status-detail">${agent.status}</span>
                        </div>
                    `;
                } else {
                    agentDiv.className = 'p-sm flex items-center justify-center md:justify-start space-x-0 md:space-x-sm rounded-lg hover:bg-surface-container transition-all cursor-pointer group';
                    agentDiv.innerHTML = `
                        <div class="relative">
                            <span class="material-symbols-outlined text-on-surface-variant/70">${agent.icon}</span>
                            <div class="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full status-indicator"></div>
                        </div>
                        <div class="flex-1 min-w-0 hidden md:block">
                            <p class="font-body-sm text-body-sm font-medium truncate">${agent.name}</p>
                            <p class="font-code-sm text-[10px] opacity-60 status-detail">${agent.status}</p>
                        </div>
                    `;
                }
                agentContainer.appendChild(agentDiv);
            });
        }

        // Find navigation links in the sidebar
        const navLinks = document.querySelectorAll('#sidebar-nav-links a, nav a');
        navLinks.forEach(link => {
            let targetUrl = link.getAttribute('href');
            const text = link.textContent.trim().toLowerCase();

            if (!targetUrl || targetUrl === '#' || targetUrl.startsWith('javascript:')) {
                if (text.includes('dashboard') || text.includes('command')) {
                    targetUrl = '/dashboard';
                } else if (text.includes('intelligence') || text.includes('executive')) {
                    targetUrl = '/executive_intelligence';
                } else if (text.includes('operations') || text.includes('agent')) {
                    targetUrl = '/agent_operations';
                } else if (text.includes('graph') || text.includes('memory') || text.includes('explorer')) {
                    targetUrl = '/memory_explorer';
                } else if (text.includes('control') || text.includes('settings')) {
                    targetUrl = '/control_plane';
                }
            }

            if (targetUrl && targetUrl !== '/') {
                link.setAttribute('href', targetUrl);
                link.style.cursor = 'pointer';
                link.onclick = (e) => {
                    e.preventDefault();
                    window.location.href = targetUrl;
                };

                // Apply link container layout styles: display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 12px;
                link.style.display = 'flex';
                link.style.alignItems = 'center';
                link.style.gap = '8px';
                link.style.width = '100%';
                link.style.padding = '8px 12px';

                const isCurrent = (path === targetUrl);
                // Highlight active nav item
                if (isCurrent) {
                    link.className = 'bg-surface-container-highest text-primary rounded-lg font-body-sm font-medium';
                } else {
                    link.className = 'text-on-surface-variant hover:bg-surface-container transition-colors rounded-lg font-body-sm';
                }

                // Reduce icon size from 20px to 16px
                const icon = link.querySelector('.material-symbols-outlined');
                if (icon) {
                    icon.style.fontSize = '16px';
                    icon.style.width = '16px';
                    icon.style.flexShrink = '0';
                    icon.classList.remove('text-[20px]');
                }

                // Set text span styles
                const textSpan = link.querySelector('span:not(.material-symbols-outlined)');
                if (textSpan) {
                    textSpan.style.overflow = 'visible';
                    textSpan.style.whiteSpace = 'nowrap';
                    textSpan.style.flex = '1';
                    textSpan.style.minWidth = '0';
                }
            }
        });

        // Update the session badge in the header
        const sessionBadge = document.querySelector('[data-session-name]') || 
                             document.querySelector('.session-name') ||
                             document.getElementById('session-display-name');

        // Show cached name immediately to prevent flash
        const cachedName = localStorage.getItem('ws_display_name');
        if (sessionBadge && cachedName) {
            sessionBadge.textContent = cachedName;
        } else if (sessionBadge) {
            sessionBadge.textContent = 'WorkSphere User';
        }

        async function updateHeaderBadge() {
            const token = localStorage.getItem('worksphere_token') || localStorage.getItem('ws_token');
            if (!token) return;
            
            try {
                const provider = localStorage.getItem('ws_provider') || 'microsoft';
                const resp = await fetch(`/api/profile?token=${encodeURIComponent(token)}&provider=${encodeURIComponent(provider)}`, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (resp.ok) {
                    const data = await resp.json();
                    const name = data.display_name || data.name || 'Executive';
                    // Blocklist check
                    const blocklist = ['google user', 'google', 'microsoft user', 'worksphere user', 'active session', 'user', 'null', 'undefined', 'executive'];
                    const sanitized = blocklist.includes(name.toLowerCase().trim()) ? null : name;
                    
                    if (sanitized) {
                        localStorage.setItem('ws_display_name', sanitized);
                    }
                    if (sessionBadge && sanitized) {
                        sessionBadge.textContent = sanitized;
                    }
                }
            } catch (e) {
                console.warn('[WorkSphere] Could not update header badge:', e);
            }
        }

        updateHeaderBadge();

        // Check if redirecting from another page to start a new session
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('new_session') === 'true' && path === '/dashboard') {
            setTimeout(() => {
                const chatContainer = document.getElementById('chat-messages-container');
                if (chatContainer) {
                    const statusContainer = document.getElementById('status-container');
                    chatContainer.innerHTML = '';
                    
                    const emptyState = document.createElement('div');
                    emptyState.id = 'empty-state';
                    emptyState.className = 'max-w-3xl mx-auto flex flex-col items-center justify-center py-24 text-center';
                    emptyState.innerHTML = `
                        <span class="material-symbols-outlined text-[64px] text-on-surface-variant/20 mb-md" style="font-variation-settings: 'FILL' 1;">auto_awesome</span>
                        <p class="font-body-md text-body-md text-on-surface-variant/60 max-w-md mb-lg">Ask me to prepare for a meeting, summarise your emails, or review your tasks.</p>
                        <div class="flex flex-wrap justify-center gap-sm mt-md">
                            <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">Prepare me for tomorrow's meetings</button>
                            <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">Summarise my unread emails</button>
                            <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">What tasks are overdue?</button>
                        </div>
                    `;
                    
                    const statusText = document.getElementById('status-text');
                    if (statusText) statusText.textContent = '';
                    
                    emptyState.querySelectorAll('.suggestion-chip').forEach(chip => {
                        chip.addEventListener('click', () => {
                            const queryInput = document.getElementById('query-input');
                            if (queryInput) {
                                queryInput.value = chip.textContent.trim();
                                queryInput.focus();
                            }
                        });
                    });
                    
                    chatContainer.appendChild(emptyState);
                    if (statusContainer) chatContainer.appendChild(statusContainer);
                    window.showToast("New chat session started");
                }
            }, 100);
        }

        // Global Modal setup
        const addInstanceBtn = document.getElementById('add-instance-btn') || document.getElementById('connect-account-btn');
        if (addInstanceBtn && !token) {
            // Create global modal container if it doesn't exist
            let globalModal = document.getElementById('global-add-instance-modal');
            if (!globalModal) {
                globalModal = document.createElement('div');
                globalModal.id = 'global-add-instance-modal';
                globalModal.className = 'fixed inset-0 z-[10000] hidden items-center justify-center bg-black/50 backdrop-blur-sm transition-opacity duration-300';
                globalModal.innerHTML = `
                  <div class="bg-white border border-outline-variant rounded-xl max-w-md w-full p-lg shadow-2xl relative mx-gutter" style="font-family: 'Inter', sans-serif;">
                    <button id="global-close-modal-btn" class="absolute top-sm right-sm text-secondary hover:text-primary transition-colors">
                      <span class="material-symbols-outlined">close</span>
                    </button>
                    
                    <h3 class="font-headline-lg text-primary mb-md font-semibold text-lg">Connect Account or Start Sync</h3>
                    
                    <!-- Tab headers -->
                    <div class="flex border-b border-outline-variant/30 mb-md">
                      <button type="button" id="tab-session-btn" class="flex-1 pb-2 border-b-2 border-primary font-semibold text-xs uppercase tracking-wider text-primary">Reset Briefing</button>
                      <button type="button" id="tab-agent-btn" class="flex-1 pb-2 border-b-2 border-transparent font-medium text-xs uppercase tracking-wider text-secondary hover:text-primary">Activate Analyst</button>
                    </div>
                    
                    <!-- Tab Content: Session -->
                    <div id="tab-content-session" class="space-y-md py-sm">
                      <p class="text-sm text-secondary">Restart the intelligence briefing workflow. This clears the current conversation.</p>
                      <button type="button" id="confirm-new-session" class="w-full py-sm bg-primary text-white rounded font-medium text-body-sm hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-xs">
                        <span class="material-symbols-outlined text-[18px]">chat</span>
                        <span>Reset Briefing</span>
                      </button>
                    </div>
                    
                    <!-- Tab Content: Agent -->
                    <form id="global-add-agent-form" class="space-y-md hidden py-sm">
                      <div class="space-y-xs">
                        <label for="agent-name-input" class="font-label-md uppercase text-secondary text-[10px] tracking-wider block">Analyst Name</label>
                        <input type="text" id="agent-name-input" required placeholder="e.g. Finance Analyst" class="w-full bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-0 font-body-sm px-md py-sm rounded">
                      </div>
                      <div class="space-y-xs">
                        <label for="agent-icon-select" class="font-label-md uppercase text-secondary text-[10px] tracking-wider block">Capability / Role</label>
                        <select id="agent-icon-select" class="w-full bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-0 font-body-sm px-md py-sm rounded">
                          <option value="monitoring">monitoring (Performance Audit)</option>
                          <option value="database">database (Information Store)</option>
                          <option value="shield">shield (Risk/Compliance)</option>
                          <option value="smart_toy">smart_toy (Specialized Reasoning)</option>
                        </select>
                      </div>
                      <div class="space-y-xs">
                        <label for="agent-status-input" class="font-label-md uppercase text-secondary text-[10px] tracking-wider block">Initial Status</label>
                        <input type="text" id="agent-status-input" required placeholder="e.g. IDLE, SYNCING" value="IDLE" class="w-full bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-0 font-body-sm px-md py-sm rounded">
                      </div>
                      <div class="pt-sm flex justify-end gap-sm">
                        <button type="button" id="global-cancel-modal-btn" class="px-md py-sm border border-outline-variant text-secondary rounded hover:bg-surface-container transition-all text-body-sm font-medium">Cancel</button>
                        <button type="submit" class="px-md py-sm bg-primary text-white rounded hover:opacity-90 active:scale-[0.98] transition-all text-body-sm font-medium flex items-center gap-xs">
                          <span class="material-symbols-outlined text-[18px]">bolt</span>
                          <span>Activate Analyst</span>
                        </button>
                      </div>
                    </form>
                  </div>
                `;
                document.body.appendChild(globalModal);
            }

            const globalModalEl = document.getElementById('global-add-instance-modal');
            const closeBtn = document.getElementById('global-close-modal-btn');
            const cancelBtn = document.getElementById('global-cancel-modal-btn');
            const tabSessionBtn = document.getElementById('tab-session-btn');
            const tabAgentBtn = document.getElementById('tab-agent-btn');
            const contentSession = document.getElementById('tab-content-session');
            const formAgent = document.getElementById('global-add-agent-form');
            const confirmSessionBtn = document.getElementById('confirm-new-session');

            function openGlobalModal() {
                globalModalEl.classList.remove('hidden');
                globalModalEl.classList.add('flex');
            }

            function closeGlobalModal() {
                globalModalEl.classList.add('hidden');
                globalModalEl.classList.remove('flex');
                formAgent.reset();
            }

            addInstanceBtn.addEventListener('click', openGlobalModal);
            if (closeBtn) closeBtn.addEventListener('click', closeGlobalModal);
            if (cancelBtn) cancelBtn.addEventListener('click', closeGlobalModal);

            tabSessionBtn.addEventListener('click', () => {
                tabSessionBtn.className = 'flex-1 pb-2 border-b-2 border-primary font-semibold text-xs uppercase tracking-wider text-primary';
                tabAgentBtn.className = 'flex-1 pb-2 border-b-2 border-transparent font-medium text-xs uppercase tracking-wider text-secondary hover:text-primary';
                contentSession.classList.remove('hidden');
                formAgent.classList.add('hidden');
            });

            tabAgentBtn.addEventListener('click', () => {
                tabAgentBtn.className = 'flex-1 pb-2 border-b-2 border-primary font-semibold text-xs uppercase tracking-wider text-primary';
                tabSessionBtn.className = 'flex-1 pb-2 border-b-2 border-transparent font-medium text-xs uppercase tracking-wider text-secondary hover:text-primary';
                contentSession.classList.add('hidden');
                formAgent.classList.remove('hidden');
            });

            confirmSessionBtn.addEventListener('click', () => {
                closeGlobalModal();
                if (path === '/dashboard') {
                    const chatContainer = document.getElementById('chat-messages-container');
                    if (chatContainer) {
                        const statusContainer = document.getElementById('status-container');
                        chatContainer.innerHTML = '';
                        
                        const emptyState = document.createElement('div');
                        emptyState.id = 'empty-state';
                        emptyState.className = 'max-w-3xl mx-auto flex flex-col items-center justify-center py-24 text-center';
                        emptyState.innerHTML = `
                            <span class="material-symbols-outlined text-[64px] text-on-surface-variant/20 mb-md" style="font-variation-settings: 'FILL' 1;">auto_awesome</span>
                            <p class="font-body-md text-body-md text-on-surface-variant/60 max-w-md mb-lg">Ask me to prepare for a meeting, summarise your emails, or review your tasks.</p>
                            <div class="flex flex-wrap justify-center gap-sm mt-md">
                                <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">Prepare me for tomorrow's meetings</button>
                                <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">Summarise my unread emails</button>
                                <button class="suggestion-chip border border-outline-variant hover:border-primary/45 hover:bg-surface-container rounded-full px-4 py-1.5 text-[13px] bg-transparent transition-all cursor-pointer">What tasks are overdue?</button>
                            </div>
                        `;
                        
                        const statusText = document.getElementById('status-text');
                        if (statusText) statusText.textContent = '';
                        
                        emptyState.querySelectorAll('.suggestion-chip').forEach(chip => {
                            chip.addEventListener('click', () => {
                                const queryInput = document.getElementById('query-input');
                                if (queryInput) {
                                    queryInput.value = chip.textContent.trim();
                                    queryInput.focus();
                                }
                            });
                        });
                        
                        chatContainer.appendChild(emptyState);
                        if (statusContainer) chatContainer.appendChild(statusContainer);
                        window.showToast("New chat session started");
                    }
                } else {
                    window.location.href = '/dashboard?new_session=true';
                }
            });

            formAgent.addEventListener('submit', (e) => {
                e.preventDefault();
                const name = document.getElementById('agent-name-input').value.trim();
                const icon = document.getElementById('agent-icon-select').value;
                const status = document.getElementById('agent-status-input').value.trim();

                const customAgents = JSON.parse(localStorage.getItem('worksphere_custom_agents') || '[]');
                customAgents.push({ name, icon, status });
                localStorage.setItem('worksphere_custom_agents', JSON.stringify(customAgents));

                // Append immediately if container exists
                if (agentContainer) {
                    const agentDiv = document.createElement('div');
                    const isRightPanel = agentContainer.id === 'agent-nodes-container' && path === '/dashboard';
                    if (isRightPanel) {
                        agentDiv.className = 'flex items-center justify-between p-sm bg-white instrument-border rounded-lg';
                        agentDiv.innerHTML = `
                            <div class="flex items-center space-x-sm">
                                <span class="material-symbols-outlined text-secondary/70">${icon}</span>
                                <span class="text-sm font-medium text-on-surface">${name}</span>
                            </div>
                            <div class="flex items-center space-x-xs bg-neutral-100 px-sm py-[2px] rounded-full status-pill-container">
                                <div class="w-1.5 h-1.5 bg-neutral-400 rounded-full status-indicator"></div>
                                <span class="text-[10px] font-semibold text-neutral-500 status-detail">${status}</span>
                            </div>
                        `;
                    } else {
                        agentDiv.className = 'p-sm flex items-center justify-center md:justify-start space-x-0 md:space-x-sm rounded-lg hover:bg-surface-container transition-all cursor-pointer group';
                        agentDiv.innerHTML = `
                            <div class="relative">
                                <span class="material-symbols-outlined text-on-surface-variant/70">${icon}</span>
                                <div class="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full status-indicator"></div>
                            </div>
                            <div class="flex-1 min-w-0 hidden md:block">
                                <p class="font-body-sm text-body-sm font-medium truncate">${name}</p>
                                <p class="font-code-sm text-[10px] opacity-60 status-detail">${status}</p>
                            </div>
                        `;
                    }
                    agentContainer.appendChild(agentDiv);
                }

                window.showToast(`Agent "${name}" Created Successfully`);
                closeGlobalModal();
            });

            // Handle ESC key to close modal
            window.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && !globalModalEl.classList.contains('hidden')) {
                    closeGlobalModal();
                }
            });
        }

        // Wire No-Op Buttons to "Coming Soon" Toasts
        document.querySelectorAll('button, a').forEach(el => {
            const text = el.textContent.trim().toUpperCase();
            
            const isControl = text.includes('SAVE') || 
                             text.includes('TEST') || 
                             text.includes('RESET') ||
                             text.includes('AUDIT') ||
                             text.includes('LOGOUT') ||
                             text.includes('ADD INSTANCE') ||
                             el.closest('nav') || 
                             el.closest('header') ||
                             el.id === 'ms-signin' ||
                             el.id === 'send-btn' ||
                             el.id === 'add-instance-btn' ||
                             el.closest('#global-add-instance-modal');
            
            if (isControl) return;

            const noOps = [
                'AUDIT SECURITY LOG', 'RESET TO DEFAULTS', 'TEST CONNECTIONS'
            ];

            const href = el.getAttribute('href');
            const isNoOpText = noOps.some(term => text.includes(term));
            const isDummyLink = el.tagName === 'A' && (href === '#' || href === '');

            if (isNoOpText || isDummyLink) {
                el.addEventListener('click', (e) => {
                    if (isDummyLink) e.preventDefault();
                    window.showToast("Feature Coming Soon // WorkSphere AI under construction");
                });
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupInteractions);
    } else {
        setupInteractions();
    }
})();
