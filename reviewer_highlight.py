"""
Reviewer highlight feature - Cursor-style floating action bar
Shows a floating action bar when text is highlighted on flashcards
"""

from aqt import mw, gui_hooks


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

    // Track Command/Meta key state
    document.addEventListener('keydown', (e) => {
        if (e.metaKey || e.key === 'Meta' || e.key === 'Command') {
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
        if (e.key === 'Meta' || e.key === 'Command') {
            cmdKeyHeld = false;
        }
    });

    // Also track when window loses focus (releases all keys)
    window.addEventListener('blur', () => {
        cmdKeyHeld = false;
    });

    // Create the bubble element
    function createBubble() {
        const div = document.createElement('div');
        div.id = 'anki-highlight-bubble';
        div.style.cssText = `
            position: absolute;
            background: #1e1e1e;
            border-radius: 6px;
            border: 1px solid #4b5563;
            padding: 4px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2);
            z-index: 9999;
            display: none;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 12px;
            color: #ffffff;
            line-height: 1;
            min-height: auto;
            overflow: hidden;
        `;
        document.body.appendChild(div);
        return div;
    }

    // Render default state with two buttons and divider
    function renderDefaultState() {
        currentState = 'default';
        bubble.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1px; line-height: 1; margin: 0; padding: 0;">
                <button id="add-to-chat-btn" style="
                    background: transparent;
                    border: none;
                    color: #ffffff;
                    padding: 2px 8px;
                    cursor: pointer;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.15s ease;
                    white-space: nowrap;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    line-height: 1;
                    margin: 0;
                ">
                    <span>Add to Chat</span>
                    <span style="font-size: 10px; color: #9ca3af; font-weight: 400;">${window.quickActionsConfig?.addToChat?.display || '⌘F'}</span>
                </button>
                <div style="width: 1px; height: 14px; background-color: #4b5563; margin: 0;"></div>
                <button id="ask-question-btn" style="
                    background: transparent;
                    border: none;
                    color: #ffffff;
                    padding: 2px 8px;
                    cursor: pointer;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.15s ease;
                    white-space: nowrap;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    line-height: 1;
                    margin: 0;
                ">
                    <span>Ask Question</span>
                    <span style="font-size: 10px; color: #9ca3af; font-weight: 400;">${window.quickActionsConfig?.askQuestion?.display || '⌘R'}</span>
                </button>
            </div>
        `;

        // Add hover effects
        const addToChatBtn = bubble.querySelector('#add-to-chat-btn');
        const askQuestionBtn = bubble.querySelector('#ask-question-btn');

        addToChatBtn.addEventListener('mouseenter', () => {
            addToChatBtn.style.backgroundColor = '#374151';
        });
        addToChatBtn.addEventListener('mouseleave', () => {
            addToChatBtn.style.backgroundColor = 'transparent';
        });

        askQuestionBtn.addEventListener('mouseenter', () => {
            askQuestionBtn.style.backgroundColor = '#374151';
        });
        askQuestionBtn.addEventListener('mouseleave', () => {
            askQuestionBtn.style.backgroundColor = 'transparent';
        });

        // Add click handlers
        addToChatBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleAddToChat();
        });
        // Prevent mouseup/mousedown from bubbling to document level
        addToChatBtn.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
        addToChatBtn.addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });

        askQuestionBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            renderInputState();
        });
        // Prevent mouseup/mousedown from bubbling to document level
        askQuestionBtn.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
        askQuestionBtn.addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
    }

    function renderInputState() {
        currentState = 'input';
        bubble.innerHTML = `
            <div style="
                display: flex;
                flex-direction: column;
                padding: 0px;
                gap: 0px;
                min-width: 280px;
                max-width: 380px;
                position: relative;
            ">
                <div style="display: flex; align-items: flex-start; gap: 4px; padding: 7px 6px 6px 8px;">
                    <textarea
                        id="question-input"
                        placeholder="Ask a question..."
                        rows="1"
                        style="
                            background: transparent;
                            border: none;
                            color: #ffffff;
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
                        background: transparent;
                        border: none;
                        color: #9ca3af;
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
                    ">✕</button>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; margin: 0; padding: 0 6px 6px 8px;">
                    <div id="context-pill" style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px dashed rgba(255, 255, 255, 0.2);
                        border-radius: 12px;
                        padding: 2px 8px;
                        height: 20px;
                        box-sizing: border-box;
                        font-size: 10px;
                        color: #9ca3af;
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
                        background: #3b82f6;
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
                contextPill.style.borderColor = 'rgba(59, 130, 246, 0.6)';
                contextPill.style.color = '#e5e7eb';
                contextPill.style.background = 'rgba(59, 130, 246, 0.1)';
                contextPill.style.boxShadow = '0 0 8px rgba(59, 130, 246, 0.4)';
            } else {
                // State A: Empty (Default)
                contextTextSpan.textContent = 'Select text +';
                contextClearBtn.style.display = 'none';

                // Reset styles
                contextPill.style.borderStyle = 'dashed';
                contextPill.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                contextPill.style.color = '#9ca3af';
                contextPill.style.background = 'rgba(255, 255, 255, 0.05)';
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
            submitBtn.style.backgroundColor = '#2563eb';
        });
        submitBtn.addEventListener('mouseleave', () => {
            submitBtn.style.backgroundColor = '#3b82f6';
        });

        // Hover effect for close button
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.color = '#ffffff';
        });
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.color = '#9ca3af';
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

    // Position the bubble above or below the selection
    function positionBubble(rect) {
        const bubbleHeight = bubble.offsetHeight;
        const bubbleWidth = bubble.offsetWidth;
        const padding = 20; // Vertical padding between selection and bubble

        // Position horizontally based on the end (right edge) of the selection
        // Align bubble's right edge near the selection's right edge
        let left = rect.right - bubbleWidth;

        // Keep bubble within viewport horizontal bounds with some margin
        const margin = 10;
        if (left < margin) {
            left = margin;
        }
        if (left + bubbleWidth > window.innerWidth - margin) {
            left = window.innerWidth - bubbleWidth - margin;
        }

        // Default: Position below the selection
        let top = rect.bottom + padding;

        // Check: Would it go off the bottom of the screen?
        if (top + bubbleHeight > window.innerHeight) {
            // Flip: Position above the selection instead
            top = rect.top - bubbleHeight - padding;
        }

        bubble.style.left = left + window.scrollX + 'px';
        bubble.style.top = top + window.scrollY + 'px';
    }

    // Show the bubble
    function showBubble(rect, text) {
        selectedText = text;
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
    }

    // Drag functionality
    let isDragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    function startDrag(e) {
        // Don't start drag on buttons, inputs, or textareas
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
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

            // Only show bubble if Command/Meta key is held AND text is selected
            if (text && text.length > 0 && cmdKeyHeld) {
                // Get selection range
                const range = selection.getRangeAt(0);

                // For multi-line selections, get the END position specifically
                const endRange = document.createRange();
                endRange.setStart(range.endContainer, range.endOffset);
                endRange.setEnd(range.endContainer, range.endOffset);
                const endRect = endRange.getBoundingClientRect();

                // Use the full selection rect but with the end position for horizontal alignment
                const rect = range.getBoundingClientRect();
                const combinedRect = {
                    left: rect.left,
                    right: endRect.right || rect.right,
                    top: rect.top,
                    bottom: rect.bottom,
                    width: rect.width,
                    height: rect.height
                };

                showBubble(combinedRect, text);
            } else {
                // No text selected - hide bubble if in default state and clicking outside
                if (currentState === 'default' && !bubble.contains(e.target)) {
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
        config = mw.addonManager.getConfig(__name__) or {}
        quick_actions = config.get("quick_actions", {
            "add_to_chat": {"keys": ["Meta", "F"]},
            "ask_question": {"keys": ["Meta", "R"]}
        })

        # Format shortcuts for JavaScript
        add_to_chat_keys = quick_actions["add_to_chat"]["keys"]
        ask_question_keys = quick_actions["ask_question"]["keys"]

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

        # Inject config as JavaScript variables
        config_js = f"""
        <script>
        window.quickActionsConfig = {{
            addToChat: {{
                keys: {add_to_chat_keys},
                display: "{add_to_chat_display}"
            }},
            askQuestion: {{
                keys: {ask_question_keys},
                display: "{ask_question_display}"
            }}
        }};
        </script>
        """

        # Add the config and JavaScript to the card HTML
        html += config_js
        html += f"<script>{HIGHLIGHT_BUBBLE_JS}</script>"

    return html


def setup_highlight_hooks():
    """Register the highlight bubble injection hook"""
    gui_hooks.card_will_show.append(inject_highlight_bubble)
