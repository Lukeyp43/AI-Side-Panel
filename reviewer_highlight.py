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
                background: rgba(22, 22, 24, 0.92);
                -webkit-backdrop-filter: blur(40px) saturate(1.8);
                backdrop-filter: blur(40px) saturate(1.8);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 14px;
                box-shadow:
                    inset 0 0.5px 0 0 rgba(255, 255, 255, 0.12),
                    0 0 0 0.5px rgba(255, 255, 255, 0.08),
                    0 4px 24px rgba(0, 0, 0, 0.35),
                    0 0 40px rgba(255, 255, 255, 0.02);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                overflow: hidden;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 3px 10px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                ">
                    <button id="open-panel-btn" style="
                        background: none; border: none;
                        color: rgba(255,255,255,0.72);
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
                        color: rgba(255,255,255,0.65);
                        cursor: pointer; font-size: 12px; font-weight: 500;
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
        closeBtn.addEventListener('mouseenter', () => { closeBtn.style.color = 'rgba(255,255,255,0.95)'; });
        closeBtn.addEventListener('mouseleave', () => { closeBtn.style.color = 'rgba(255,255,255,0.65)'; });

        var openBtn = bubble.querySelector('#open-panel-btn');
        openBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pycmd('openevidence');
            hideBubble();
        });
        openBtn.addEventListener('mouseup', (e) => { e.stopPropagation(); });
        openBtn.addEventListener('mouseenter', () => { openBtn.style.color = 'rgba(255,255,255,0.98)'; });
        openBtn.addEventListener('mouseleave', () => { openBtn.style.color = 'rgba(255,255,255,0.72)'; });
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

    // Position the bubble relative to the selection
    function positionBubble(rect) {
        const bubbleHeight = bubble.offsetHeight;
        const bubbleWidth = bubble.offsetWidth;
        const margin = 10;

        if ((currentState === 'default' || currentState === 'loading') && selectionStartRect) {
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

    // Expose globally so Python can dismiss the bubble on errors
    window.ankiDismissExplain = hideBubble;

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
                if (cfg.explainEnabled !== false) {
                    // Show Explain tab
                    showBubble(rect, text);
                }
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
        config = mw.addonManager.getConfig(ADDON_NAME) or {}

        # Prepend config and append main script
        config_js = f"""
        <script>
        if (!window.quickActionsConfig) {{
            window.quickActionsConfig = {{}};
        }}
        window.quickActionsConfig.explainEnabled = {str(config.get('explain_enabled', True)).lower()};
        </script>
        """

        # Get CSS variables from ThemeManager
        css_vars = ThemeManager.get_css_variables()
        
        return html + css_vars + config_js + f"<script>{HIGHLIGHT_BUBBLE_JS}</script>"
    
    return html


def setup_highlight_hooks():
    """Register the highlight bubble injection hook"""
    gui_hooks.card_will_show.append(inject_highlight_bubble)
