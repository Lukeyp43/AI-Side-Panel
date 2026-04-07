"""
Reviewer highlight feature - Cursor-style floating action bar
Shows a floating action bar when text is highlighted on flashcards
"""

from aqt import mw, gui_hooks
from .utils import ADDON_NAME
from .theme_manager import ThemeManager


# JavaScript code to inject into the reviewer
HIGHLIGHT_BUBBLE_JS = """
(function() {
    // Only inject once
    if (window.ankiHighlightBubbleInjected) {
        return;
    }
    window.ankiHighlightBubbleInjected = true;
    console.log('Anki: Injecting highlight bubble for OpenEvidence');

    let bubble = null;
    let currentState = 'default'; // 'default' or 'input'
    let selectedText = '';
    let cmdKeyHeld = false;
    let contextText = ''; // Store context text for the pill
    let selectionStartRect = null; // Start position of current selection
    let selectionRect = null; // Full selection bounding rect
    let isCompact = false; // Track compact vs full tab mode
    let streamDisplayed = 0; // How many chars of the response have been shown

    // Completely rewritten key matching - more aggressive approach
    function checkShortcut(e, configKeys) {
        if (!configKeys || configKeys.length === 0) return false;

        var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        var pressedKeys = {};

        // Build pressed keys map
        if (e.shiftKey) pressedKeys['Shift'] = true;
        if (e.altKey) pressedKeys['Alt'] = true;
        
        if (isMac) {
            if (e.ctrlKey) pressedKeys['Control'] = true;
            if (e.metaKey) pressedKeys['Meta'] = true;
        } else {
            if (e.ctrlKey || e.metaKey) pressedKeys['Control/Meta'] = true;
        }

        // Get the regular key - try multiple methods for reliability
        // On macOS, Control+T might give e.key as "Tab" (browser shortcut) but e.code as "KeyT"
        var regularKey = null;
        
        // First try e.key if it's a single character
        if (e.key && e.key.length === 1 && /^[A-Za-z0-9]$/.test(e.key)) {
            regularKey = e.key.toUpperCase();
        } 
        // Fallback to e.code for more reliable detection (especially for Control combinations)
        else if (e.code) {
            // Match patterns like "KeyT", "KeyA", "Digit1", etc.
            var codeMatch = e.code.match(/^(Key|Digit)([A-Z0-9])$/);
            if (codeMatch) {
                regularKey = codeMatch[2];
            }
        }

        if (regularKey) {
            pressedKeys[regularKey] = true;
        }

        // Check if all required keys are present
        for (var i = 0; i < configKeys.length; i++) {
            if (!pressedKeys[configKeys[i]]) {
                return false;
            }
        }

        // Verify exact count match
        return Object.keys(pressedKeys).length === configKeys.length;
    }

    // Handle shortcut actions
    function handleAskQuestion(e) {
        e.preventDefault();
        e.stopImmediatePropagation();  // More aggressive than stopPropagation
        
        const selection = window.getSelection();
        const text = selection.toString().trim();
        
        if (text && text.length > 0) {
            selectedText = text;
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            bubble.style.display = 'block';
            renderInputState();
            setTimeout(() => positionBubble(rect), 0);
        } else if (currentState === 'default' || bubble.style.display === 'none') {
            selectedText = '';
            const centerRect = {
                left: window.innerWidth / 2,
                right: window.innerWidth / 2,
                top: window.innerHeight / 3,
                bottom: window.innerHeight / 3,
                width: 0,
                height: 0
            };
            bubble.style.display = 'block';
            renderInputState();
            setTimeout(() => positionBubble(centerRect), 0);
        }
    }

    function handleAddToChatShortcut(e) {
        e.preventDefault();
        e.stopImmediatePropagation();  // More aggressive than stopPropagation
        
        const selection = window.getSelection();
        const text = selection.toString().trim();
        
        if (text && text.length > 0) {
            selectedText = text;
            handleAddToChat();  // Call the actual handler function
        }
    }

    // Track Cmd/Ctrl key state for quick actions trigger
    document.addEventListener('keydown', (e) => {
        var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        if (isMac ? (e.metaKey || e.key === 'Meta') : (e.ctrlKey || e.key === 'Control')) {
            cmdKeyHeld = true;
        }
    }, true);

    // Main keyboard shortcut handler - completely rewritten
    // Use capture phase with highest priority on window (not document)
    window.addEventListener('keydown', function(e) {
        // Get shortcuts from config
        var askQuestionKeys = (window.quickActionsConfig && window.quickActionsConfig.askQuestion && window.quickActionsConfig.askQuestion.keys) || ['Meta', 'R'];
        var addToChatKeys = (window.quickActionsConfig && window.quickActionsConfig.addToChat && window.quickActionsConfig.addToChat.keys) || ['Meta', 'F'];

        // Early check: if Control key is pressed and it's part of our shortcuts, prevent default immediately
        var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        var hasControl = isMac ? e.ctrlKey : (e.ctrlKey || e.metaKey);
        
        if (hasControl) {
            // Check if this Control combination matches any of our shortcuts
            var askHasControl = askQuestionKeys.indexOf('Control') !== -1;
            var chatHasControl = addToChatKeys.indexOf('Control') !== -1;
            
            if (askHasControl || chatHasControl) {
                // Prevent default early for Control combinations to stop browser shortcuts
                e.preventDefault();
            }
        }

        // Debug logging
        console.log('Quick Actions keydown:', {
            key: e.key,
            code: e.code,
            ctrlKey: e.ctrlKey,
            metaKey: e.metaKey,
            shiftKey: e.shiftKey,
            altKey: e.altKey,
            askQuestionKeys: askQuestionKeys,
            addToChatKeys: addToChatKeys,
            checkResult: {
                ask: checkShortcut(e, askQuestionKeys),
                chat: checkShortcut(e, addToChatKeys)
            }
        });

        // Check Ask Question shortcut
        if (checkShortcut(e, askQuestionKeys)) {
            console.log('Ask Question match!');
            handleAskQuestion(e);
            return false;  // Return false as additional prevention
        }

        // Check Add to Chat shortcut
        if (checkShortcut(e, addToChatKeys)) {
            console.log('Add to Chat match!');
            handleAddToChatShortcut(e);
            return false;  // Return false as additional prevention
        }
    }, true);  // Capture phase - intercept before anyone else

    document.addEventListener('keyup', (e) => {
        var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        if (e.key === 'Meta' || e.key === 'Command' || e.key === 'Control') {
            cmdKeyHeld = false;
        }
    });

    // Also track when window loses focus (releases all keys)
    window.addEventListener('blur', () => {
        cmdKeyHeld = false;
    });

    // Create the bubble element — minimal container, children handle their own styling
    function createBubble() {
        const div = document.createElement('div');
        div.id = 'anki-highlight-bubble';
        div.style.cssText = `
            position: absolute;
            background: transparent;
            border-radius: 0;
            border: none;
            padding: 0;
            z-index: 9999;
            display: none;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 12px;
            color: var(--oa-text);
            line-height: 1;
            min-height: auto;
            overflow: visible;
        `;
        document.body.appendChild(div);
        return div;
    }

    // Render default state — small tab sitting above the selection start
    function resetBubbleStyle() {
        bubble.style.background = 'transparent';
        bubble.style.border = 'none';
        bubble.style.borderRadius = '0';
        bubble.style.padding = '0';
        bubble.style.overflow = 'visible';
        bubble.style.boxShadow = 'none';
    }

    function renderDefaultState() {
        currentState = 'default';
        resetBubbleStyle();

        isCompact = selectionRect && selectionRect.width < 70;
        var compact = isCompact;

        bubble.innerHTML = `
            <button id="explain-btn" style="
                background: #5b9bd5;
                border: none;
                color: #ffffff;
                padding: ${compact ? '2px 4px' : '2px 7px 2px 5px'};
                cursor: pointer;
                border-radius: 5px 5px 0 0;
                font-size: 9px;
                font-weight: 600;
                transition: background 0.15s ease;
                white-space: nowrap;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: inline-flex;
                align-items: center;
                gap: 3px;
                line-height: 1;
                margin: 0;
                opacity: 0.9;
            ">
                <span style="
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 11px;
                    height: 11px;
                    border-radius: 50%;
                    background: rgba(0, 0, 0, 0.18);
                    font-size: 8px;
                    font-weight: 700;
                    flex-shrink: 0;
                ">?</span>
                ${compact ? '' : '<span>Explain</span>'}
            </button>
        `;

        var btn = bubble.querySelector('#explain-btn');
        btn.addEventListener('mouseenter', () => { btn.style.opacity = '1'; btn.style.background = '#4a8cc6'; });
        btn.addEventListener('mouseleave', () => { btn.style.opacity = '0.9'; btn.style.background = '#5b9bd5'; });
        btn.addEventListener('click', (e) => { e.stopPropagation(); handleExplain(); });
        btn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
        btn.addEventListener('mousedown', (e) => { e.stopPropagation(); });
    }

    // Quick actions state — Add to Chat / Ask Question buttons (shown on Cmd+highlight)
    function renderQuickActionsState() {
        currentState = 'quickactions';
        bubble.style.boxShadow = 'none';
        bubble.style.background = 'var(--oa-background)';
        bubble.style.border = '1px solid var(--oa-border)';
        bubble.style.borderRadius = '6px';
        bubble.style.padding = '4px';
        bubble.style.overflow = 'hidden';

        var cfg = window.quickActionsConfig || {};
        var addDisplay = (cfg.addToChat && cfg.addToChat.display) || '\u2318F';
        var askDisplay = (cfg.askQuestion && cfg.askQuestion.display) || '\u2318R';

        var buttons = '';
        if (cfg.addToChatEnabled !== false) {
            buttons += `
                <button id="add-to-chat-btn" style="
                    background: transparent; border: none; box-shadow: none;
                    color: var(--oa-text);
                    padding: 2px 8px; cursor: pointer; font-size: 12px; font-weight: 500;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: inline-flex; align-items: center; gap: 6px;
                    transition: all 0.15s ease; border-radius: 3px; white-space: nowrap;
                    line-height: 1; margin: 0;
                ">
                    <span>Add to Chat</span>
                    <span style="font-size: 10px; color: var(--oa-text-secondary); font-weight: 400;">${addDisplay}</span>
                </button>`;
        }
        if (cfg.addToChatEnabled !== false && cfg.askQuestionEnabled !== false) {
            buttons += '<div style="width: 1px; height: 14px; background-color: var(--oa-border); margin: 0;"></div>';
        }
        if (cfg.askQuestionEnabled !== false) {
            buttons += `
                <button id="ask-question-btn" style="
                    background: transparent; border: none; box-shadow: none;
                    color: var(--oa-text);
                    padding: 2px 8px; cursor: pointer; font-size: 12px; font-weight: 500;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: inline-flex; align-items: center; gap: 6px;
                    transition: all 0.15s ease; border-radius: 3px; white-space: nowrap;
                    line-height: 1; margin: 0;
                ">
                    <span>Ask Question</span>
                    <span style="font-size: 10px; color: var(--oa-text-secondary); font-weight: 400;">${askDisplay}</span>
                </button>`;
        }

        bubble.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1px; line-height: 1; margin: 0; padding: 0;">
                ${buttons}
            </div>
        `;

        var atcBtn = bubble.querySelector('#add-to-chat-btn');
        if (atcBtn) {
            atcBtn.addEventListener('mouseenter', () => { atcBtn.style.background = 'var(--oa-hover)'; });
            atcBtn.addEventListener('mouseleave', () => { atcBtn.style.background = 'transparent'; });
            atcBtn.addEventListener('click', (e) => { e.stopPropagation(); handleAddToChat(); });
            atcBtn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
            atcBtn.addEventListener('mousedown', (e) => { e.stopPropagation(); });
        }
        var aqBtn = bubble.querySelector('#ask-question-btn');
        if (aqBtn) {
            aqBtn.addEventListener('mouseenter', () => { aqBtn.style.background = 'var(--oa-hover)'; });
            aqBtn.addEventListener('mouseleave', () => { aqBtn.style.background = 'transparent'; });
            aqBtn.addEventListener('click', (e) => { e.stopPropagation(); renderInputState(); });
            aqBtn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
            aqBtn.addEventListener('mousedown', (e) => { e.stopPropagation(); });
        }
    }

    // Show quick actions bubble (Cmd+highlight)
    function showQuickActionsBubble(rect, text) {
        selectedText = text;
        selectionRect = rect;
        renderQuickActionsState();
        bubble.style.display = 'block';
        setTimeout(() => positionBubble(rect), 0);
    }

    // Loading state — tab morphs in place: icon becomes spinner, text becomes "Thinking"
    function renderLoadingState() {
        currentState = 'loading';
        resetBubbleStyle();

        // Inject keyframes if not already
        if (!document.getElementById('anki-explain-styles')) {
            var style = document.createElement('style');
            style.id = 'anki-explain-styles';
            style.textContent = '@keyframes ankiSpin { to { transform: rotate(360deg); } }';
            document.head.appendChild(style);
        }

        bubble.innerHTML = `
            <button id="explain-btn" style="
                background: #5b9bd5;
                border: none;
                color: #ffffff;
                padding: ${isCompact ? '2px 4px' : '2px 7px 2px 5px'};
                cursor: default;
                border-radius: 5px 5px 0 0;
                font-size: 9px;
                font-weight: 600;
                white-space: nowrap;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: inline-flex;
                align-items: center;
                gap: 3px;
                line-height: 1;
                margin: 0;
                opacity: 0.9;
            ">
                <span style="
                    display: inline-block;
                    width: 9px; height: 9px;
                    border: 1.5px solid rgba(255,255,255,0.3);
                    border-top-color: #fff;
                    border-radius: 50%;
                    animation: ankiSpin 0.7s linear infinite;
                    flex-shrink: 0;
                "></span>
                ${isCompact ? '' : '<span>Thinking</span>'}
            </button>
        `;

        // Stay in tab position (above highlight start)
        if (selectionStartRect) {
            positionBubble(selectionRect);
        }
    }

    // Tooltip state — Apple glass card below highlight
    function renderTooltipState(responseText, streaming) {
        currentState = 'tooltip';
        resetBubbleStyle();

        // Inject tooltip styles
        if (!document.getElementById('anki-blink-style')) {
            var blinkStyle = document.createElement('style');
            blinkStyle.id = 'anki-blink-style';
            blinkStyle.textContent = '@keyframes ankiBlink { 0%,100% { opacity:1; } 50% { opacity:0; } } #tooltip-text strong, #tooltip-text b { font-weight: 600; color: rgba(255,255,255,0.95); } #tooltip-text em, #tooltip-text i { font-style: italic; } #tooltip-scroll { scrollbar-width: thin; } #tooltip-scroll::-webkit-scrollbar { width: 7px; background: transparent; } #tooltip-scroll::-webkit-scrollbar-track { background: transparent; } #tooltip-scroll::-webkit-scrollbar-thumb { background: transparent; border-radius: 4px; transition: background 0.3s; } #tooltip-scroll:hover::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); } #tooltip-scroll:hover::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }';
            document.head.appendChild(blinkStyle);
        }

        bubble.innerHTML = `
            <div style="
                width: 320px;
                background: rgba(0, 0, 0, 0.35);
                -webkit-backdrop-filter: blur(40px) saturate(1.8);
                backdrop-filter: blur(40px) saturate(1.8);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                box-shadow:
                    inset 0 0.5px 0 0 rgba(255, 255, 255, 0.1),
                    0 0 0 0.5px rgba(255, 255, 255, 0.06),
                    0 2px 16px rgba(0, 0, 0, 0.25),
                    0 0 40px rgba(255, 255, 255, 0.02);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                overflow: hidden;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 3px 10px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
                ">
                    <button id="open-panel-btn" style="
                        background: none; border: none;
                        color: rgba(255,255,255,0.4);
                        cursor: pointer; font-size: 10px; font-weight: 500;
                        font-family: inherit; padding: 0;
                        display: inline-flex; align-items: center; gap: 4px;
                        transition: color 0.15s;
                        line-height: 1;
                    ">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M15 3h6v6"/><path d="M10 14L21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        </svg>
                        <span>Continue in chat</span>
                    </button>
                    <button id="tooltip-close" style="
                        background: none; border: none;
                        color: rgba(255,255,255,0.3);
                        cursor: pointer; font-size: 10px;
                        padding: 0 2px; line-height: 1;
                        transition: color 0.15s;
                    ">\u2715</button>
                </div>
                <div id="tooltip-scroll" style="
                    max-height: 150px;
                    overflow-y: auto;
                    padding: 10px 14px 12px 14px;
                ">
                    <div id="tooltip-text" style="
                        font-size: 12px;
                        font-weight: 400;
                        color: rgba(255,255,255,0.88);
                        line-height: 1.65;
                        text-align: left;
                    "></div>
                </div>
            </div>
        `;

        // Set content as HTML (preserves bold/italic formatting)
        var textDiv = bubble.querySelector('#tooltip-text');
        var cursor = streaming ? '<span class="stream-cursor" style="display:inline;animation:ankiBlink 0.8s step-end infinite;color:rgba(255,255,255,0.4);margin-left:1px;">\\u258E</span>' : '';
        textDiv.innerHTML = responseText + cursor;
        streamDisplayed = responseText.length;

        // Reposition below highlight, left-aligned with selection start
        if (selectionRect) {
            positionBubble(selectionRect);
        }

        var closeBtn = bubble.querySelector('#tooltip-close');
        closeBtn.addEventListener('click', (e) => { e.stopPropagation(); pycmd('openevidence:clear_chat'); hideBubble(); });
        closeBtn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
        closeBtn.addEventListener('mouseenter', () => { closeBtn.style.color = 'rgba(255,255,255,0.65)'; });
        closeBtn.addEventListener('mouseleave', () => { closeBtn.style.color = 'rgba(255,255,255,0.3)'; });

        var openBtn = bubble.querySelector('#open-panel-btn');
        openBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pycmd('openevidence');
            hideBubble();
        });
        openBtn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
        openBtn.addEventListener('mouseenter', () => { openBtn.style.color = 'rgba(255,255,255,0.65)'; });
        openBtn.addEventListener('mouseleave', () => { openBtn.style.color = 'rgba(255,255,255,0.4)'; });
    }

    // Handle explain button click
    function handleExplain() {
        // Store the selection rect before it might get lost
        var sel = window.getSelection();
        if (sel.rangeCount > 0) {
            selectionRect = sel.getRangeAt(0).getBoundingClientRect();
        }
        streamDisplayed = 0;
        renderLoadingState();
        pycmd('openevidence:inline_explain:' + encodeURIComponent(selectedText));
    }

    // Streaming callback — streams text as it arrives
    window.ankiStreamExplainText = function(text, isDone) {
        if (text === 'ERROR_TIMEOUT' || text === 'OUT_OF_SCOPE') {
            var msg = text === 'OUT_OF_SCOPE'
                ? 'This doesn\\'t appear to be a medical topic. Try highlighting a medical term.'
                : 'Couldn\\'t load explanation.';
            renderTooltipState(msg, false);
            return;
        }

        if (currentState !== 'tooltip') {
            // First chunk — create tooltip with initial text
            renderTooltipState(text, !isDone);
        } else {
            var textDiv = bubble.querySelector('#tooltip-text');
            if (textDiv && (text.length !== streamDisplayed || isDone)) {
                var scrollContainer = bubble.querySelector('#tooltip-scroll');
                var wasAtBottom = scrollContainer &&
                    (scrollContainer.scrollTop + scrollContainer.clientHeight >= scrollContainer.scrollHeight - 5);

                var cursor = isDone ? '' : '<span class="stream-cursor" style="display:inline;animation:ankiBlink 0.8s step-end infinite;color:rgba(255,255,255,0.4);margin-left:1px;">\\u258E</span>';
                textDiv.innerHTML = text + cursor;
                streamDisplayed = text.length;

                // Auto-scroll if user was at the bottom
                if (wasAtBottom && scrollContainer) {
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                }
            }
        }

    };

    // Legacy callback
    window.ankiShowExplainTooltip = function(text) {
        window.ankiStreamExplainText(text, true);
    };

    function renderInputState() {
        currentState = 'input';
        resetBubbleStyle();
        // Add shadow back for the input bubble so it stands out
        bubble.style.boxShadow = '0 4px 12px var(--oa-shadow)';
        
        bubble.innerHTML = `
            <div style="
                display: flex;
                flex-direction: column;
                padding: 0px;
                gap: 0px;
                min-width: 280px;
                max-width: 380px;
                position: relative;
                background: var(--oa-surface);
                border: 1px solid var(--oa-border);
                border-radius: 10px;
            ">
                <div style="display: flex; align-items: flex-start; gap: 4px; padding: 7px 6px 6px 8px;">
                    <textarea
                        id="question-input"
                        placeholder="Ask a question..."
                        rows="1"
                        style="
                            background: transparent;
                            border: none;
                            color: var(--oa-text);
                            padding: 0;
                            font-size: 13px;
                            font-weight: 500;
                            outline: none;
                            flex: 1;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            resize: none;
                            overflow-y: auto;
                            min-height: 10px;
                            max-height: 100px;
                            line-height: 1.3;
                            word-wrap: break-word;
                            margin: 0;
                        "
                    ></textarea>
                    <button id="close-btn" style="
                        appearance: none;
                        -webkit-appearance: none;
                        background: transparent;
                        border: none;
                        box-shadow: none;
                        outline: none;
                        color: var(--oa-text-secondary);
                        cursor: pointer;
                        font-size: 13px;
                        padding: 0;
                        width: 18px;
                        height: 18px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: all 0.15s ease;
                        line-height: 1;
                        flex-shrink: 0;
                        margin: 0;
                        margin-left: auto;
                        margin-right: -1px;
                        border-radius: 0;
                    ">✕</button>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; margin: 0; padding: 0 6px 6px 8px;">
                    <div id="context-pill" style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        background: var(--oa-hover);
                        border: 1px dashed var(--oa-border);
                        border-radius: 12px;
                        padding: 2px 8px;
                        height: 20px;
                        box-sizing: border-box;
                        font-size: 10px;
                        color: var(--oa-text-secondary);
                        cursor: pointer;
                        transition: all 0.15s ease;
                        max-width: 180px;
                        white-space: nowrap;
                        overflow: hidden;
                    ">
                        <span id="context-text" style="
                            overflow: hidden;
                            text-overflow: ellipsis;
                            line-height: 1.2;
                        ">Select text +</span>
                        <button id="context-clear" style="
                            display: none;
                            background: transparent;
                            border: none;
                            color: inherit;
                            cursor: pointer;
                            font-size: 10px;
                            padding: 0;
                            width: 10px;
                            height: 10px;
                            flex-shrink: 0;
                            line-height: 1;
                            opacity: 0.7;
                        ">✕</button>
                    </div>
                    <button id="submit-btn" style="
                        background: var(--oa-accent);
                        border: none;
                        color: #ffffff;
                        padding: 0;
                        cursor: pointer;
                        border-radius: 50%;
                        font-size: 13px;
                        font-weight: 600;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: all 0.15s ease;
                        width: 19px;
                        height: 19px;
                        flex-shrink: 0;
                        margin: 0;
                    "><svg width="10" height="11" viewBox="0 0 10 11" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 1.5V9.5M5 1.5L2 4.5M5 1.5L8 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                </div>
            </div>
        `;

        const input = bubble.querySelector('#question-input');
        const submitBtn = bubble.querySelector('#submit-btn');
        const closeBtn = bubble.querySelector('#close-btn');
        const contextPill = bubble.querySelector('#context-pill');
        const contextTextSpan = bubble.querySelector('#context-text');
        const contextClearBtn = bubble.querySelector('#context-clear');

        // Auto-resize textarea as user types
        function autoResize() {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 100) + 'px';
        }

        // Update context pill based on contextText
        function updateContextPill() {
            if (contextText) {
                // State B: Active (Selection)
                const truncated = contextText.length > 9 ? contextText.substring(0, 9) + '...' : contextText;
                contextTextSpan.textContent = '"' + truncated + '"';
                contextClearBtn.style.display = 'block';

                // Style changes with glow effect to show selection
                contextPill.style.borderStyle = 'solid';
                contextPill.style.borderColor = 'rgba(59, 130, 246, 0.6)'; // Keep accent semi-transparent (hard to do with vars unless we split RGB)
                contextPill.style.color = 'var(--oa-text)';
                contextPill.style.background = 'rgba(59, 130, 246, 0.1)';
                contextPill.style.boxShadow = '0 0 8px rgba(59, 130, 246, 0.4)';
            } else {
                // State A: Empty (Default)
                contextTextSpan.textContent = 'Select text +';
                contextClearBtn.style.display = 'none';

                // Reset styles
                contextPill.style.borderStyle = 'dashed';
                contextPill.style.borderColor = 'var(--oa-border)';
                contextPill.style.color = 'var(--oa-text-secondary)';
                contextPill.style.background = 'var(--oa-hover)';
                contextPill.style.boxShadow = 'none';
            }
        }

        // Clear context
        function clearContext() {
            contextText = '';
            updateContextPill();
        }

        // Focus the input
        setTimeout(() => input.focus(), 0);

        // Initialize context with selectedText if available
        if (selectedText && !contextText) {
            contextText = selectedText;
        }

        // Initialize context pill
        updateContextPill();

        // Auto-resize on input
        input.addEventListener('input', autoResize);

        // Submit on Enter key (without Shift)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmitQuestion();
            }
        });

        // Hover effect for submit button
        submitBtn.addEventListener('mouseenter', () => {
            submitBtn.style.backgroundColor = 'var(--oa-accent-hover)';
        });
        submitBtn.addEventListener('mouseleave', () => {
            submitBtn.style.backgroundColor = 'var(--oa-accent)';
        });

        // Hover effect for close button
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.color = 'var(--oa-text)';
        });
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.color = 'var(--oa-text-secondary)';
        });

        // Close button handler
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            hideBubble();
        });
        closeBtn.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
        closeBtn.addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });

        // Click handler for submit button
        submitBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleSubmitQuestion();
        });
        // Prevent mouseup/mousedown from bubbling to document level
        submitBtn.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
        submitBtn.addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });

        // Context pill click handler (State A: show hint)
        contextPill.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!contextText) {
                // Show hint
                const originalText = contextTextSpan.textContent;
                contextTextSpan.textContent = 'Highlight text on page';
                setTimeout(() => {
                    if (!contextText) {
                        contextTextSpan.textContent = originalText;
                    }
                }, 1500);
            }
        });

        // Context clear button handler
        contextClearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearContext();
        });
        contextClearBtn.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
        contextClearBtn.addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });

        // Listen for text selection while bubble is open
        const selectionHandler = () => {
            const selection = window.getSelection();
            const text = selection.toString().trim();
            if (text && text.length > 0 && currentState === 'input') {
                contextText = text;
                updateContextPill();
            }
        };
        document.addEventListener('mouseup', selectionHandler);

        // Clean up listener when bubble is hidden
        const originalHideBubble = hideBubble;
        window.hideBubbleWithCleanup = function() {
            document.removeEventListener('mouseup', selectionHandler);
            originalHideBubble();
        };
    }

    // Handle "Add to Chat" action
    function handleAddToChat() {
        console.log('Anki: Add to Chat clicked, text:', selectedText);
        // Send message to Python
        pycmd('openevidence:add_context:' + encodeURIComponent(selectedText));
        hideBubble();
    }

    // Handle question submission
    function handleSubmitQuestion() {
        const input = bubble.querySelector('#question-input');
        const query = input.value.trim();

        if (query) {
            // Use contextText if available, otherwise use selectedText
            const finalContext = contextText || selectedText;
            console.log('Anki: Question submitted:', query, 'Context:', finalContext);
            // Send message to Python with format: query|context
            pycmd('openevidence:ask_query:' + encodeURIComponent(query) + '|' + encodeURIComponent(finalContext));
            hideBubble();
            // Clear context after submission
            contextText = '';
        }
    }

    // Position the bubble relative to the selection
    function positionBubble(rect) {
        const bubbleHeight = bubble.offsetHeight;
        const bubbleWidth = bubble.offsetWidth;
        const margin = 10;

        if (currentState === 'quickactions') {
            // Quick actions: position below selection, right-aligned
            const padding = 8;
            let left = rect.right - bubbleWidth;
            if (left < margin) left = margin;
            if (left + bubbleWidth > window.innerWidth - margin) {
                left = window.innerWidth - bubbleWidth - margin;
            }
            let top = rect.bottom + padding;
            if (top + bubbleHeight > window.innerHeight) {
                top = rect.top - bubbleHeight - padding;
            }
            bubble.style.left = (left + window.scrollX) + 'px';
            bubble.style.top = (top + window.scrollY) + 'px';
        } else if ((currentState === 'default' || currentState === 'loading') && selectionStartRect) {
            // Tab mode: position at the START of the selection, directly above
            // Bottom of tab flush with top of selection (like a browser tab)
            let left = selectionStartRect.left;
            let top = selectionStartRect.top - bubbleHeight;

            // Keep within viewport
            if (left < margin) left = margin;
            if (left + bubbleWidth > window.innerWidth - margin) {
                left = window.innerWidth - bubbleWidth - margin;
            }
            // If no room above, place below the selection start
            if (top < 0) {
                top = selectionStartRect.bottom;
            }

            bubble.style.left = (left + window.scrollX) + 'px';
            bubble.style.top = (top + window.scrollY) + 'px';
        } else if (currentState === 'tooltip' && selectionStartRect) {
            // Tooltip: left edge aligned with selection start, below highlight
            let left = selectionStartRect.left;
            let top = rect.bottom + 15;

            if (left < margin) left = margin;
            if (left + bubbleWidth > window.innerWidth - margin) {
                left = window.innerWidth - bubbleWidth - margin;
            }
            if (top + bubbleHeight > window.innerHeight) {
                top = rect.top - bubbleHeight - 15;
            }

            bubble.style.left = (left + window.scrollX) + 'px';
            bubble.style.top = (top + window.scrollY) + 'px';
        } else {
            // Card mode (input, fallback): position below selection with gap
            const padding = 12;

            let left = rect.right - bubbleWidth;
            if (left < margin) left = margin;
            if (left + bubbleWidth > window.innerWidth - margin) {
                left = window.innerWidth - bubbleWidth - margin;
            }

            let top = rect.bottom + padding;
            if (top + bubbleHeight > window.innerHeight) {
                top = rect.top - bubbleHeight - padding;
            }

            bubble.style.left = (left + window.scrollX) + 'px';
            bubble.style.top = (top + window.scrollY) + 'px';
        }
    }

    // Show the bubble
    function showBubble(rect, text) {
        selectedText = text;
        selectionRect = rect;
        renderDefaultState();
        bubble.style.display = 'block';

        // Position after render so we have accurate dimensions
        setTimeout(() => positionBubble(rect), 0);
    }

    // Hide the bubble
    function hideBubble() {
        bubble.style.display = 'none';
        currentState = 'default';
        contextText = ''; // Clear context when bubble is hidden
        selectionStartRect = null;
        selectionRect = null;
        streamDisplayed = 0;
    }

    // Drag functionality
    let isDragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    function startDrag(e) {
        // Don't start drag on buttons, inputs, textareas, or their children
        var el = e.target;
        while (el && el !== bubble) {
            if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SVG' || el.tagName === 'path') {
                return;
            }
            el = el.parentElement;
        }

        isDragging = true;
        const rect = bubble.getBoundingClientRect();
        dragOffsetX = e.clientX - rect.left;
        dragOffsetY = e.clientY - rect.top;
        bubble.style.cursor = 'grabbing';
        e.preventDefault();
    }

    function drag(e) {
        if (!isDragging) return;

        const newLeft = e.clientX - dragOffsetX;
        const newTop = e.clientY - dragOffsetY;

        bubble.style.left = newLeft + 'px';
        bubble.style.top = newTop + 'px';
    }

    function stopDrag() {
        if (isDragging) {
            isDragging = false;
            bubble.style.cursor = 'default';
        }
    }

    // Add drag event listeners to the bubble
    document.addEventListener('mousedown', (e) => {
        if (bubble.contains(e.target) && bubble.style.display !== 'none') {
            startDrag(e);
        }
    });

    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', stopDrag);

    // Handle mouseup event
    document.addEventListener('mouseup', (e) => {
        // Small delay to allow selection to complete
        setTimeout(() => {
            const selection = window.getSelection();
            const text = selection.toString().trim();

            if (text && text.length > 3) {
                // Get selection range
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();

                // Get the START position of the selection for tab positioning
                const startRange = document.createRange();
                startRange.setStart(range.startContainer, range.startOffset);
                startRange.setEnd(range.startContainer, range.startOffset);
                selectionStartRect = startRange.getBoundingClientRect();

                var cfg = window.quickActionsConfig || {};
                if (cmdKeyHeld) {
                    // Cmd+highlight → show Add to Chat / Ask Question
                    showQuickActionsBubble(rect, text);
                } else if (cfg.explainEnabled !== false) {
                    // Normal highlight → show Explain tab
                    showBubble(rect, text);
                }
            } else {
                // No text selected - hide bubble if in default state and clicking outside
                if ((currentState === 'default' || currentState === 'quickactions') && !bubble.contains(e.target)) {
                    hideBubble();
                }
            }
        }, 10);
    });

    // Note: Bubble no longer auto-hides when clicking outside
    // Only the X button in the input state can close the bubble

    // Create the bubble on load
    bubble = createBubble();
    console.log('Anki: Highlight bubble ready');
})();
"""


def inject_highlight_bubble(html, card, context):
    """Inject the highlight bubble JavaScript into reviewer cards

    Args:
        html: The HTML of the question or answer
        card: The current card object
        context: One of "reviewQuestion", "reviewAnswer", "clayoutQuestion",
                "clayoutAnswer", "previewQuestion", "previewAnswer"

    Returns:
        Modified HTML with injected JavaScript
    """
    # Only inject in review context (not in card layout or preview)
    if context in ("reviewQuestion", "reviewAnswer"):
        # Load shortcuts from config
        from aqt import mw
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        quick_actions = config.get("quick_actions", {
            "add_to_chat": {"keys": ["Meta", "F"]},
            "ask_question": {"keys": ["Meta", "R"]}
        })

        # Format shortcuts for JavaScript
        add_to_chat_keys = quick_actions["add_to_chat"]["keys"]
        ask_question_keys = quick_actions["ask_question"]["keys"]
        highlight_modifier = config.get("highlight_modifier", "none")

        # Create display text (e.g., "⌘F" or "Ctrl+Shift+F")
        def format_shortcut_display(keys):
            display_keys = []
            for key in keys:
                if key == "Meta":
                    display_keys.append("⌘")
                elif key == "Control":
                    display_keys.append("Ctrl")
                elif key == "Shift":
                    display_keys.append("Shift")
                elif key == "Alt":
                    display_keys.append("Alt")
                else:
                    display_keys.append(key)
            return "".join(display_keys) if "⌘" in display_keys else "+".join(display_keys)

        add_to_chat_display = format_shortcut_display(add_to_chat_keys)
        ask_question_display = format_shortcut_display(ask_question_keys)

        # Prepend config and append main script
        config_js = f"""
        <script>
        if (!window.quickActionsConfig) {{
            window.quickActionsConfig = {{}};
        }}
        window.quickActionsConfig.addToChat = {{
            keys: {add_to_chat_keys},
            display: "{add_to_chat_display}"
        }};
        window.quickActionsConfig.askQuestion = {{
            keys: {ask_question_keys},
            display: "{ask_question_display}"
        }};
        window.quickActionsConfig.explainEnabled = {str(config.get('explain_enabled', True)).lower()};
        window.quickActionsConfig.addToChatEnabled = {str(config.get('add_to_chat_enabled', True)).lower()};
        window.quickActionsConfig.askQuestionEnabled = {str(config.get('ask_question_enabled', True)).lower()};
        </script>
        """

        # Get CSS variables from ThemeManager
        css_vars = ThemeManager.get_css_variables()
        
        return html + css_vars + config_js + f"<script>{HIGHLIGHT_BUBBLE_JS}</script>"
    
    return html


def setup_highlight_hooks():
    """Register the highlight bubble injection hook"""
    gui_hooks.card_will_show.append(inject_highlight_bubble)
