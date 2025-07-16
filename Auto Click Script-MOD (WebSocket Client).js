// ==UserScript==
// @name         Auto Click Script-MOD (WebSocket Client)
// @version      2.14
// @description  Applies price changes instantly on Apply.
// @author       You
// @match        https://csp.aliexpress.com/m_apps/aechoice-product-bidding/biddingRegistration*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    console.log("[AC-WS] Script starting...");

    // --- Global State ---
    let STATE = {
        checkTimer: null,
        processTimer: null,
        isRunning: false,
        ws: null,
        reconnectTimer: null,
        infoPollTimer: null,
        globalSettings: {},
        specificSettings: {}
    };

    // --- UI Functions ---
    function addStatusIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'ws-status-indicator';
        indicator.style.position = 'fixed';
        indicator.style.top = '10px';
        indicator.style.left = '10px';
        indicator.style.zIndex = '9999';
        indicator.style.padding = '5px 10px';
        indicator.style.borderRadius = '5px';
        indicator.style.color = 'white';
        indicator.style.fontSize = '12px';
        document.body.appendChild(indicator);
        updateStatus("WAITING FOR INFO", "gray");
    }

    function updateStatus(text, color) {
        const indicator = document.getElementById('ws-status-indicator');
        if (indicator) {
            indicator.textContent = `Panel: ${text}`;
            indicator.style.backgroundColor = color;
        }
        console.log(`[AC-WS] Status: ${text}`);
    }

    // --- RELIABLE KEYBOARD SIMULATION (Used for decrementing) ---
    function simulateKeyInput(element, text, callback) {
        let index = 0;
        function typeNextChar() {
            if (index >= text.length) {
                element.dispatchEvent(new Event('change', { bubbles: true })); // Ensure change event is dispatched
                if (callback) callback();
                return;
            }
            const char = text[index++];
            const eventProps = { bubbles: true, cancelable: true };
            const keyEventProps = { ...eventProps, key: char, code: `Key${char.toUpperCase()}` };
            element.dispatchEvent(new KeyboardEvent('keydown', keyEventProps));
            element.dispatchEvent(new KeyboardEvent('keypress', { ...keyEventProps, charCode: char.charCodeAt(0) }));
            element.value += char;
            element.dispatchEvent(new Event('input', eventProps));
            element.dispatchEvent(new KeyboardEvent('keyup', keyEventProps));
            setTimeout(typeNextChar, 50);
        }
        typeNextChar();
    }

    // --- Information Extraction ---
    function getProductInfo() {
        try {
            const imgElement = document.querySelector('img.ait-image-img.card_img');
            const productIdSpan = document.querySelector('span[aria-label^="商品ID："]');
            let imageUrl = imgElement ? imgElement.src : null;
            let productId = null;
            if (productIdSpan) {
                const match = productIdSpan.getAttribute('aria-label').match(/商品ID：(\d+)/);
                if (match) productId = match[1];
            }
            if (productId && imageUrl) return { productId, imageUrl };
            return null;
        } catch (e) {
            console.error("[AC-WS] Error in getProductInfo:", e);
            return null;
        }
    }
    
    // +++ NEW: simulateRealisticTyping function (focus-blur after direct value set) +++
    function simulateRealisticTyping(element, text, callback) {
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;

        // 1. Set the final value directly
        nativeInputValueSetter.call(element, text);

        // 2. Focus and then immediately blur the element
        element.focus();
        element.blur();

        // 3. Callback after a short delay to ensure events propagate
        setTimeout(() => {
            if (callback) callback();
        }, 100);
    }


    // +++ REFACTORED: setSkuPrices to use sequential, realistic typing +++
    function setSkuPrices(prices, callback) {
        console.log('Attempting to set SKU prices with realistic typing:', prices);
        if (!Array.isArray(prices) || prices.length === 0) {
            console.error('[AC-WS] Invalid or empty prices array received:', prices);
            updateStatus("INVALID PRICES", "red");
            if (callback) callback(false);
            return;
        }

        // Dynamically find all potential SKU price input fields
        const allInputElements = document.evaluate(
            '//table/tbody/tr/td[7]/div/span/span/input',
            document,
            null,
            XPathResult.ORDERED_NODE_ITERATOR_TYPE,
            null
        );

        const inputsToFill = [];
        let inputElement = allInputElements.iterateNext();
        while (inputElement) {
            // Check if the input element is visible and has a valid row in its XPath
            if (inputElement.offsetWidth > 0 || inputElement.offsetHeight > 0) {
                const xpath = getXPathForElement(inputElement);
                const match = xpath.match(/tr\[(\d+)\]/);
                if (match && match[1]) {
                    inputsToFill.push({ element: inputElement, xpath: xpath, row: parseInt(match[1]) });
                }
            }
            inputElement = allInputElements.iterateNext();
        }

        // Sort inputs by their row number to ensure correct order
        inputsToFill.sort((a, b) => a.row - b.row);

        if (inputsToFill.length === 0) {
            console.error('[AC-WS] Could not find any visible input elements to fill.');
            updateStatus("PRICE APPLY FAIL", "red");
            if (callback) callback(false);
            return;
        }
        
        console.log(`[AC-WS] Found ${inputsToFill.length} visible inputs to fill.`);

        // Process inputs one by one sequentially
        let currentIndex = 0;
        function processNextInput() {
            if (currentIndex >= inputsToFill.length || currentIndex >= prices.length) {
                console.log(`[AC-WS] Successfully applied ${Math.min(inputsToFill.length, prices.length)} prices.`);
                updateStatus("PRICES APPLIED", "green");
                if (callback) callback(true);
                return;
            }

            const item = inputsToFill[currentIndex];
            const price = prices[currentIndex];
            const formattedPrice = parseFloat(price).toFixed(2);

            if (!isNaN(formattedPrice)) {
                console.log(`[AC-WS] Typing price ${formattedPrice} into element found by: ${item.xpath}`);
                simulateRealisticTyping(item.element, formattedPrice, () => {
                    currentIndex++;
                    processNextInput(); // Process the next one
                });
            } else {
                console.warn(`[AC-WS] Skipping invalid price: ${price} for element: ${item.xpath}`);
                currentIndex++;
                processNextInput(); // Skip and process the next one
            }
        }

        processNextInput(); // Start the sequential process
    }

    // Helper function to get XPath of an element (simplified for this context)
    function getXPathForElement(element) {
        if (element.id !== '')
            return 'id("' + element.id + '")';
        if (element === document.body)
            return '/html/body';
        
        var ix = 0;
        var siblings = element.parentNode.childNodes;
        for (var i = 0; i < siblings.length; i++) {
            var sibling = siblings[i];
            if (sibling === element)
                return getXPathForElement(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                ix++;
        }
    }

    // --- Core Logic ---
    function stopAutoClick() {
        if (STATE.checkTimer) clearTimeout(STATE.checkTimer);
        if (STATE.processTimer) clearTimeout(STATE.processTimer);
        STATE.isRunning = false;
        STATE.checkTimer = null;
        STATE.processTimer = null;
        console.log("[AC-WS] All timers stopped.");
        updateStatus("IDLE", "blue");
    }

    // +++ REFACTORED: startAutoClick now handles multi-SKU price decrement +++
    function startAutoClick() {
        if (STATE.isRunning) {
            console.warn("[AC-WS] Already running. Ignoring start command.");
            return;
        }

        if (Object.keys(STATE.globalSettings).length === 0 || Object.keys(STATE.specificSettings).length === 0) {
            console.error("[AC-WS] Cannot start: Settings not received from panel.");
            updateStatus("NO SETTINGS", "red");
            return;
        }

        const submitButton = document.querySelector('button[name="submit"][type="button"].next-btn.next-medium.next-btn-primary');
        if (!submitButton) {
            console.error("[AC-WS] Submit button not found. Cannot start.");
            updateStatus("PAGE ELEM FAILED", "black");
            return;
        }

        stopAutoClick(); // Reset previous state
        STATE.isRunning = true;
        updateStatus("ARMED", "orange");
        console.log("[AC-WS] Start command processed. Waiting for target time.");

        const { targetHour, targetMinute, targetSecond, decrementValue, checkDelay, resultCheckDelay, resubmitDelay } = STATE.globalSettings;
        const { minValues, skuPrices, autoDecrement, randomDelay } = STATE.specificSettings;

        // Initialize current prices from the settings
        let currentPrices = [...skuPrices];

        const checkSubmitSuccess = () => document.querySelector('div[aria-modal="true"][aria-labelledby^="dialog-title-"]');

        const processSubmission = () => {
            if (!STATE.isRunning) return;

            submitButton.click();

            STATE.processTimer = setTimeout(() => {
                if (!STATE.isRunning) return;

                if (checkSubmitSuccess()) {
                    console.log("[AC-WS] Submission successful!");
                    updateStatus("SUCCESS", "green");
                    stopAutoClick();
                } else {
                    console.log("[AC-WS] Submission failed. Checking auto-decrement...");
                    if (autoDecrement) {
                        let stopDecrementing = false;
                        // Decrement all prices
                        currentPrices = currentPrices.map((price, i) => {
                            const newPrice = Math.round((price - decrementValue) * 100) / 100;
                            // Check against the corresponding minimum value
                            if (newPrice < minValues[i]) {
                                console.log(`[AC-WS] SKU ${i+1} reached minimum value (${minValues[i]}). Stopping further decrements.`);
                                stopDecrementing = true;
                            }
                            return newPrice;
                        });

                        if (stopDecrementing) {
                            updateStatus("MIN VAL REACHED", "red");
                            stopAutoClick();
                            return;
                        }

                        console.log(`[AC-WS] Resubmitting with new prices:`, currentPrices);
                        updateStatus("RESUBMITTING", "#FFC300");
                        
                        // Apply the new prices to the page and then try submitting again
                        setSkuPrices(currentPrices, (success) => {
                            if (success) {
                                STATE.processTimer = setTimeout(processSubmission, resubmitDelay);
                            } else {
                                console.error("[AC-WS] Failed to apply new prices during resubmission. Stopping.");
                                updateStatus("APPLY FAIL", "red");
                                stopAutoClick();
                            }
                        });

                    } else {
                        console.log("[AC-WS] Auto-decrement is disabled. Stopping.");
                        updateStatus("SUBMIT FAIL", "red");
                        stopAutoClick();
                    }
                }
            }, resultCheckDelay);
        };

        const checkTargetTime = () => {
            if (!STATE.isRunning) return;
            const now = new Date();
            const targetTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), targetHour, targetMinute, targetSecond);

            if (now >= targetTime) {
                console.log("[AC-WS] Target time reached. Starting submission process.");
                updateStatus("SUBMITTING", "purple");
                processSubmission();
            } else {
                STATE.checkTimer = setTimeout(checkTargetTime, checkDelay);
            }
        };
        
        console.log(`[AC-WS] Waiting for random delay of ${randomDelay || 0}ms before arming time check.`);
        setTimeout(() => {
            if (STATE.isRunning) {
                 console.log("[AC-WS] Random delay finished. Now checking for target time.");
                 updateStatus("WAITING FOR TIME", "#FFC300");
                 checkTargetTime();
            }
        }, randomDelay || 0);
    }

    // --- WebSocket Connection ---
    function connectWebSocket(productInfo) {
        if (STATE.ws && (STATE.ws.readyState === WebSocket.OPEN || STATE.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        
        STATE.ws = new WebSocket('ws://localhost:8765');
        updateStatus("CONNECTING", "gray");

        STATE.ws.onopen = () => {
            updateStatus("CONNECTED", "blue");
            STATE.ws.send(JSON.stringify({
                type: "register",
                productId: productInfo.productId,
                imageUrl: productInfo.imageUrl
            }));
            updateStatus("REGISTERED", "blue");
        };

        STATE.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log("[AC-WS] Received message from panel:", message);

                if (message.type === 'apply_settings') {
                    STATE.globalSettings = message.globalParams;
                    STATE.specificSettings = message.specificParams;
                    console.log("[AC-WS] Settings stored. Applying SKU prices to page immediately.");
                    setSkuPrices(STATE.specificSettings.skuPrices);

                } else if (message.type === 'start') {
                    console.log("[AC-WS] Received start command with full settings.");
                    // Store all settings from the start message
                    STATE.globalSettings = message.globalParams;
                    STATE.specificSettings = message.specificParams;
                    console.log("[AC-WS] Settings updated from start command.");
                    
                    // The `startAutoClick` function will now use these fresh settings
                    startAutoClick();

                } else if (message.type === 'stop') {
                    console.log("[AC-WS] Received stop command.");
                    stopAutoClick();
                }
            } catch (e) {
                console.error("[AC-WS] Error processing message:", e);
            }
        };

        STATE.ws.onclose = () => {
            updateStatus("DISCONNECTED", "red");
            console.log("[AC-WS] WebSocket closed. Attempting to reconnect in 5 seconds...");
            clearTimeout(STATE.reconnectTimer);
            STATE.reconnectTimer = setTimeout(() => connectWebSocket(productInfo), 5000);
        };

        STATE.ws.onerror = (err) => {
            console.error("[AC-WS] WebSocket error:", err);
        };
    }

    // --- Entry Point ---
    function main() {
        addStatusIndicator();
        
        let maxAttempts = 120;
        let attempts = 0;
        STATE.infoPollTimer = setInterval(() => {
            const productInfo = getProductInfo();
            if (productInfo) {
                clearInterval(STATE.infoPollTimer);
                console.log(`[AC-WS] Product info found: ID=${productInfo.productId}`);
                connectWebSocket(productInfo);
            } else {
                attempts++;
                if (attempts >= maxAttempts) {
                    clearInterval(STATE.infoPollTimer);
                    updateStatus("PAGE INFO FAILED", "black");
                    console.error("[AC-WS] Failed to get product info after multiple attempts.");
                }
            }
        }, 500);
    }

    window.addEventListener('load', main, false);

})();
