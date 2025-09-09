## Front Template
```html
<!-- ======================= SHARED UTILS ======================= -->

{{^SharedUtils}}
<!-- IF THE "SharedUtils" FIELD IS EMPTY, ANKI WILL INSERT THIS SCRIPT -->
<script id="shared-utils">
    // --- NEW: A central place for all formatting rules ---
    const formattingRules = {
        frenchPunctuation: (text) => text.replace(/«\s*/g, '«\u00A0').replace(/\s*([!?:;»])/g, '\u00A0$1'),
        emDashes: (text) => text.replace(/\s*—\s*/g, '\u00A0—\u00A0'),
        interpunctQuotes: (text) => text.replace(/·(.*?)·/g, `<span class="interpunct-quote">$1</span>`),
        elisionNoWrap: (text) => text.replace(/(\w'\s*)(<span class="interpunct-quote">.*?<\/span>)/g, `<span class="no-wrap">$1$2</span>`)
    };

    // The old function, now rebuilt using the rules above
    function applyStandardFormatting(text) {
        if (!text) return '';
        let processedText = text;
        processedText = formattingRules.frenchPunctuation(processedText);
        processedText = formattingRules.emDashes(processedText);
        processedText = formattingRules.interpunctQuotes(processedText);
        processedText = formattingRules.elisionNoWrap(processedText);
        return processedText;
    }
    // Centralized fish animation (de-minified for clarity)
    function spawnShoal(containerId) {
        const container = document.getElementById(containerId);
        if (!container || container.offsetWidth <= 0) return;
        const shoalContainer = document.createElement('div');
        shoalContainer.className = 'shoal-container';
        container.appendChild(shoalContainer);
        function checkOverlap(r1, r2) { const m=5; return r1.x<r2.x+r2.width+m && r1.x<r2.width+m>r2.x && r1.y<r2.y+r2.height+m && r1.y+r1.height+m>r2.y; }
        function createSchool() {
            const numFish=Math.floor(6*Math.random())+4, placedFish=[], baseSize=parseFloat(getComputedStyle(document.querySelector('.card')).fontSize);
            for (let i=0; i<numFish; i++) {
                let attempts=0;
                while (attempts<30) {
                    const scale=1.5*Math.random()+1.2, size=scale*baseSize*.8, rect={x:Math.random()*(shoalContainer.offsetWidth-size),y:Math.random()*(shoalContainer.offsetHeight-size),width:size,height:size};
                    if (!placedFish.some(p => checkOverlap(p, rect))) {
                        placedFish.push(rect);
                        const fish=document.createElement('span');
                        fish.className='shoal-fish'; fish.textContent='?'; fish.style.left=rect.x+'px'; fish.style.top=rect.y+'px'; fish.style.fontSize=scale+'em';
                        const dur=(3*Math.random()+5)+'s', del=(1.5*Math.random())+'s';
                        fish.style.animation=`swimAndFade ${dur} ease-in-out ${del} forwards`;
                        fish.addEventListener('animationend', ()=>fish.remove());
                        shoalContainer.appendChild(fish);
                        break;
                    }
                    attempts++;
                }
            }
        }
        function loop() { createSchool(); setTimeout(loop, 5e3*Math.random()+4e3); }
        loop();
    }
</script>
{{/SharedUtils}}

<!-- ======================= FRONT TEMPLATE ======================= -->

<div id="data_question" style="display:none;">{{Question}}</div>
<div id="data_answer" style="display:none;">{{Answer}}</div>
<div id="data_cloze_answer" style="display:none;">{{ClozeAnswer}}</div>

<div id="prompt-container" class="animated-border-container">
    <div id="prompt-box">
        <div id="prompt-sentence"></div>
        <hr id="prompt-divider" class="prompt-divider">
        <div id="context-line-prompt"></div>
    </div>
</div>

<!-- ======================= CORRECTED SVG DISPLAY BLOCK ======================= -->
{{#SVGImage}}
<div class="svg-image-container">
    {{SVGImage}}
</div>
<div id="hint-tooltip" class="hint-tooltip"></div> <!-- TOOLTIP ELEMENT -->
{{/SVGImage}}
<!-- ===================================================================== -->

<script>
    window.userTypedWords = [];
    window.hintUsed = false; // <<< ADD THIS LINE TO INITIALIZE THE FLAG

    setTimeout(function() {
        const questionData = document.getElementById('data_question').textContent.trim();
        const answerData = document.getElementById('data_answer').textContent.trim();
        const mainPromptField = questionData;
        let clozePromptField = answerData;
        const promptSentenceDiv = document.getElementById('prompt-sentence');
        const contextLineDiv = document.getElementById('context-line-prompt');
        
        const clozeMatch = answerData.match(/\*(.*?)\*/);
        const clozeContent = clozeMatch ? clozeMatch[1] : '';
        const words = clozeContent.trim().split(/\s+/).filter(w => w.length > 0);

        clozePromptField = clozePromptField.replace(/\*(.*?)\*\s*([.,])/g, '*$1*$2');

        function formatForMeasurement(text) {
            return text.replace(
                /\*(.*?)\*/g,
                () => words.map(word => `<span class="measured-span" style="font-family: 'AppFont Heavy', serif; font-style: italic;">${word}</span>`).join(' ')
            );
        }

        contextLineDiv.innerHTML = formatForMeasurement(clozePromptField);

        requestAnimationFrame(() => {
            const renderedSpans = contextLineDiv.querySelectorAll('.measured-span');
            const widths = Array.from(renderedSpans).map(span => span.getBoundingClientRect().width);
            const clozeIsFollowedByPunctuation = /\*(.*?)\*\s*[.,?!:;]/.test(answerData);

            const inputsHTML = words.map((word, index) => {
                const finalWidth = Math.ceil(widths[index]);
                const maxLength = word.length;
                let containerClasses = "cloze-input-container";
                if (index === words.length - 1 && clozeIsFollowedByPunctuation) {
                    containerClasses += " no-right-pad";
                }
                return `<div class="${containerClasses}" style="width: ${finalWidth}px;"><span class="cloze-text-display">${word}</span><input type="text" class="cloze-input-real" data-index="${index}" maxlength="${maxLength}" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"></div>`;
            }).join('<span class="cloze-space"> </span>');

            let finalHTML = clozePromptField.replace(/\*(.*?)\*/g, `<span id="cloze-input-wrapper">${inputsHTML}</span>`);
            
            let formattedHTML = finalHTML;
            formattedHTML = formattingRules.emDashes(formattedHTML);
            formattedHTML = formattingRules.interpunctQuotes(formattedHTML);
            formattedHTML = formattingRules.elisionNoWrap(formattedHTML);
            contextLineDiv.innerHTML = formattedHTML;

            const wrapper = document.getElementById('cloze-input-wrapper');
            if (wrapper) {
                const realInputs = Array.from(wrapper.querySelectorAll('.cloze-input-real'));
                function updateGlobalAnswer() { window.userTypedWords = realInputs.map(input => input.value); }
                
                wrapper.addEventListener('input', (e) => {
                    if (e.target.classList.contains('cloze-input-real')) {
                        const input = e.target;
                        const displaySpan = input.previousElementSibling;
                        displaySpan.textContent = input.value;
                        displaySpan.classList.toggle('is-typing', !!input.value);
                        updateGlobalAnswer();
                    }
                });

                wrapper.addEventListener('keydown', (e) => {
                    if (e.target.classList.contains('cloze-input-real')) {
                        const input = e.target;
                        const index = parseInt(input.dataset.index, 10);
                        if (e.key === ' ' && index < realInputs.length - 1) { e.preventDefault(); realInputs[index + 1].focus(); }
                        if (e.key === 'Backspace' && input.selectionStart === 0 && index > 0) { e.preventDefault(); realInputs[index - 1].focus(); }
                        if (e.key === 'Enter') { e.preventDefault(); pycmd('ans'); }
                    }
                });

                realInputs.forEach((input, index) => {
                    input.previousElementSibling.textContent = '';
                    if (index === 0) { input.focus(); }
                });
            }
        });

        promptSentenceDiv.innerHTML = applyStandardFormatting(mainPromptField);

        // --- FINAL: Static Position Tooltip Logic ---
        const svgContainer = document.querySelector('.svg-image-container');
        const tooltip = document.getElementById('hint-tooltip');

        if (svgContainer && tooltip) {
            const clozeAnswer = document.getElementById('data_cloze_answer').textContent.trim();
            tooltip.textContent = clozeAnswer;
            let tooltipTimeout;

            const showTooltip = () => {
                window.hintUsed = true; // <<< ADD THIS LINE TO SET THE FLAG
                // Calculate position relative to the SVG container every time it's shown
                const rect = svgContainer.getBoundingClientRect();
                // Position is horizontally centered, and vertically at the bottom of the container
                tooltip.style.left = `${rect.left + window.scrollX + (rect.width / 2)}px`;
                tooltip.style.top = `${rect.bottom + window.scrollY}px`;
                
                tooltip.classList.add('visible');
            };
            
            const hideTooltip = () => {
                tooltip.classList.remove('visible');
            };

            // Show on hover
            svgContainer.addEventListener('mouseenter', showTooltip);
            svgContainer.addEventListener('mouseleave', hideTooltip);
            
            // Show on Right Alt keydown
            window.addEventListener('keydown', (e) => {
                if (e.key === 'AltGraph' || (e.key === 'Alt' && e.location === KeyboardEvent.DOM_KEY_LOCATION_RIGHT)) {
                    e.preventDefault();
                    showTooltip(); // The show function already knows how to position it
                    
                    clearTimeout(tooltipTimeout);
                    tooltipTimeout = setTimeout(hideTooltip, 1500); // Hide after a delay for the hotkey
                }
            });
        }
        // --- END OF FINAL LOGIC ---

    }, 10);
</script>

<script>
    setTimeout(() => spawnShoal('prompt-box'), 50);
</script>
```
## Back Template
```html
<!-- ======================= SHARED UTILS ======================= -->

{{^SharedUtils}}
<!-- IF THE "SharedUtils" FIELD IS EMPTY, ANKI WILL INSERT THIS SCRIPT -->
<script id="shared-utils">
    // --- NEW: A central place for all formatting rules ---
    const formattingRules = {
        frenchPunctuation: (text) => text.replace(/«\s*/g, '«\u00A0').replace(/\s*([!?:;»])/g, '\u00A0$1'),
        emDashes: (text) => text.replace(/\s*—\s*/g, '\u00A0—\u00A0'),
        interpunctQuotes: (text) => text.replace(/·(.*?)·/g, `<span class="interpunct-quote">$1</span>`),
        elisionNoWrap: (text) => text.replace(/(\w'\s*)(<span class="interpunct-quote">.*?<\/span>)/g, `<span class="no-wrap">$1$2</span>`)
    };

    // The old function, now rebuilt using the rules above
    function applyStandardFormatting(text) {
        if (!text) return '';
        let processedText = text;
        processedText = formattingRules.frenchPunctuation(processedText);
        processedText = formattingRules.emDashes(processedText);
        processedText = formattingRules.interpunctQuotes(processedText);
        processedText = formattingRules.elisionNoWrap(processedText);
        return processedText;
    }
    // Centralized fish animation (de-minified for clarity)
    function spawnShoal(containerId) {
        const container = document.getElementById(containerId);
        if (!container || container.offsetWidth <= 0) return;
        const shoalContainer = document.createElement('div');
        shoalContainer.className = 'shoal-container';
        container.appendChild(shoalContainer);
        function checkOverlap(r1, r2) { const m=5; return r1.x<r2.x+r2.width+m && r1.x<r2.width+m>r2.x && r1.y<r2.y+r2.height+m && r1.y+r1.height+m>r2.y; }
        function createSchool() {
            const numFish=Math.floor(6*Math.random())+4, placedFish=[], baseSize=parseFloat(getComputedStyle(document.querySelector('.card')).fontSize);
            for (let i=0; i<numFish; i++) {
                let attempts=0;
                while (attempts<30) {
                    const scale=1.5*Math.random()+1.2, size=scale*baseSize*.8, rect={x:Math.random()*(shoalContainer.offsetWidth-size),y:Math.random()*(shoalContainer.offsetHeight-size),width:size,height:size};
                    if (!placedFish.some(p => checkOverlap(p, rect))) {
                        placedFish.push(rect);
                        const fish=document.createElement('span');
                        fish.className='shoal-fish'; fish.textContent='?'; fish.style.left=rect.x+'px'; fish.style.top=rect.y+'px'; fish.style.fontSize=scale+'em';
                        const dur=(3*Math.random()+5)+'s', del=(1.5*Math.random())+'s';
                        fish.style.animation=`swimAndFade ${dur} ease-in-out ${del} forwards`;
                        fish.addEventListener('animationend', ()=>fish.remove());
                        shoalContainer.appendChild(fish);
                        break;
                    }
                    attempts++;
                }
            }
        }
        function loop() { createSchool(); setTimeout(loop, 5e3*Math.random()+4e3); }
        loop();
    }
</script>
{{/SharedUtils}}

<!-- ======================= BACK TEMPLATE ======================= -->

<div id="answer-wrapper"></div>

<!-- ======================= NEW SVG DISPLAY BLOCK ======================= -->
{{#SVGImage}}
<div class="svg-image-container">
    {{SVGImage}}
</div>
{{/SVGImage}}
<!-- ===================================================================== -->

<script>
    setTimeout(function() {
        // --- 1. SETUP & RENDER ---
        const answerWrapper = document.getElementById("answer-wrapper");
        const fields = { answer: `{{Answer}}`, clozeAnswerForDisplay: `{{ClozeAnswer}}` };
        
        function formatForDisplay(text) {
            let processedText = text.replace(/\*(.*?)\*/g, (match, innerText) => {
                const words = innerText.trim().split(/\s+/).filter(Boolean);
                // Now we apply all three classes for the full effect
                return words.map(w => `<span class="gradient-text typed-answer-correct animated-text">${w}</span>`).join(' ');
            });
            return applyStandardFormatting(processedText);
        }

        const revealedHTML = formatForDisplay(fields.answer);
        const mainAnswerBlock = `
            <div id="answer-container" class="animated-border-container">
                <div id="answer-box">
                    <div class="reverse">${fields.clozeAnswerForDisplay}</div>
                    <hr id="answer-divider" class="divider">
                    <div class="quaestionum-block">
                        <div class="quaestionum-a">${revealedHTML}</div>
                    </div>
                </div>
            </div>`;
        answerWrapper.innerHTML = mainAnswerBlock;

        const animatedWords = answerWrapper.querySelectorAll('.animated-text');
        const containerAnimationDuration = 250; 
        animatedWords.forEach((word, index) => {
            const totalDelay = containerAnimationDuration + (index * 80);
            word.style.animationDelay = `${totalDelay}ms`; 
        });

        // --- 2. DATA GATHERING & CORRECTNESS CHECK ---
        const headlineDiv = document.querySelector('.reverse');
        const borderDiv = document.getElementById('answer-container');
        const typedWords = window.userTypedWords || [];
        
        const clozeMatch = fields.answer.match(/\*(.*?)\*/);
        const clozeContent = clozeMatch ? clozeMatch[1] : '';
        const correctWords = clozeContent.trim().split(/\s+/).filter(Boolean);

        const userHasTyped = typedWords.length > 0 && typedWords.some(w => w.length > 0);
        
        const isCorrect = userHasTyped && (typedWords.join(' ').toLowerCase() === correctWords.join(' ').toLowerCase());

        // --- 3. VISUAL FEEDBACK (FINAL LOGIC) ---
        if (isCorrect) {
            // The answer is correct. Now, check if a hint was used.
            if (window.hintUsed) {
                // Case: ASSISTED CORRECT. Show blue border.
                borderDiv.classList.add('border-assisted');
            } else {
                // Case: UNASSISTED CORRECT. Show green border.
                borderDiv.classList.add('border-correct');
            }
            // In all correct cases, show the green text.
            headlineDiv.innerHTML = `<span class="typed-answer-correct gradient-text">${correctWords.join(' ')}</span>`;

        } else {
            // The answer is incorrect (or wasn't typed). Always show red border.
            borderDiv.classList.add('border-incorrect');
            
            if (userHasTyped) {
                // User typed something wrong, show detailed feedback.
                const feedbackHTML = correctWords.map((correctWord, index) => {
                    const typedWord = typedWords[index] || "";
                    if (typedWord.toLowerCase() === correctWord.toLowerCase()) {
                        return `<span class="typed-answer-correct gradient-text">${correctWord}</span>`;
                    }
                    let wordHTML = '';
                    let inCorrectSpan = false;
                    for (let i = 0; i < correctWord.length; i++) {
                        const isCharCorrect = (i < typedWord.length && typedWord[i].toLowerCase() === correctWord[i].toLowerCase());
                        if (isCharCorrect) {
                            if (!inCorrectSpan) { wordHTML += '<span class="typed-answer-correct gradient-text">'; inCorrectSpan = true; }
                            wordHTML += correctWord[i];
                        } else {
                            if (inCorrectSpan) { wordHTML += '</span>'; inCorrectSpan = false; }
                            wordHTML += correctWord[i];
                        }
                    }
                    if (inCorrectSpan) wordHTML += '</span>';
                    return wordHTML;
                }).join(' ');
                headlineDiv.innerHTML = feedbackHTML;
            } else {
                // User didn't type anything, just show the correct answer.
                headlineDiv.textContent = correctWords.join(' ');
            }
        }
    }, 10);
</script>

<script>
    setTimeout(() => spawnShoal('answer-box'), 50);
</script>
```
## Styling
```css
/* === CSS RESET FOR ANKI === */
/* This forces the Editor and Reviewer to behave the same way */
html, body, div, span, applet, object, iframe,
h1, h2, h3, h4, h5, h6, p, blockquote, pre,
a, abbr, acronym, address, big, cite, code,
del, dfn, em, img, ins, kbd, q, s, samp,
small, strike, strong, sub, sup, tt, var,
b, u, i, center,
dl, dt, dd, ol, ul, li,
fieldset, form, label, legend,
table, caption, tbody, tfoot, thead, tr, th, td,
article, aside, canvas, details, embed,
figure, figcaption, footer, header, hgroup,
menu, nav, output, ruby, section, summary,
time, mark, audio, video {
    margin: 0;
    padding: 0;
    border: 0;
    font-size: 100%;
    font: inherit;
    vertical-align: baseline;
    box-sizing: border-box; /* This is a very important rule for layout */
}
article, aside, details, figcaption, figure,
footer, header, hgroup, menu, nav, section {
    display: block;
}
body {
    line-height: 1;
}
/* === END OF RESET === */

/* [ENTIRE STYLING SECTION - CONDENSED & COLOR-CORRECTED VERSION] */

:root {
    --font-size-base: 22px;
    --font-main: 'AppFont', serif;
    --font-heavy: 'AppFont Heavy', serif;
    
/* Light Mode */
--bg-light: #f8f6ee;          /* (Unchanged) */
--card-bg-light: #fffdfa;     /* (Unchanged) */
--text-main-light: #5C524A;   /* Darker, richer 'ink' color for high readability */
--text-subtle-light: #A1988E; /* Softer, slightly lighter to recede beautifully */

/* Dark Mode */
--bg-dark: #2B2825;           /* (Unchanged) */
--card-bg-dark: #3D3936;      /* (Unchanged) */
--text-main-dark: #E0DACE;    /* A touch brighter for more pop as the primary text */
--text-subtle-dark: #B3A99E;  /* (Unchanged) Excellent choice, provides perfect subtle contrast */

    /* Using Silver Dividers */
--divider-color-1: #4F4A45;  /* A deep, warm, almost-black coffee bean */
--divider-color-2: #E1DDD7;  /* A light, warm parchment, like aged paper */
--divider-color-3: #918B85;  /* A mid-tone, desaturated warm gray */

    /* QUAESTIONUM-SPECIFIC GRADIENT COLORS */
--green-base: #257D50;      /* A strong, confident forest green */
--green-highlight: #B4E07B; /* A vibrant, sun-drenched lime highlight */

    /* Using Magenta for Concepts */
    --purple-base: #7D5295;
    --purple-highlight: #DA70D6;

    --dark-base: #413A34;
    --dark-highlight: #A1988E;
    
    /* --- NEW: THE "GOLDEN TICKET" SYSTEM --- */
    --gold-shadow:   #855600;  /* The deepest shadow in the creases */
    --gold-mid:      #D4A017;  /* The main, rich body color of the gold */
    --gold-highlight:#F7C43B;  /* The bright, primary reflection */
    --gold-glint:    #FFF8E1;  /* The sharp, almost-white specular glint */

--steel-base: #D6D1CA;       /* A solid, warm stone color */
--steel-highlight: #E1DDD7;  /* Same as the lightest divider for consistency */

    --blue-base: #1E3A8A; /* A deep, serious blue */
    --blue-highlight: #3B82F6; /* A bright, clear blue */
    
    /* Using Jarring Amber for Incorrect */
    --red-base: #FF3300;
    --red-highlight: #FFB300;

/* Corresponds to --text-subtle-light: #A1988E */
--text-subtle-light-hsl: 33, 8%, 59%; 

/* Corresponds to --text-subtle-dark: #B3A99E */
--text-subtle-dark-hsl: 39, 9%, 68%;
}

@font-face { font-family: 'AppFont'; src: url('GT-Pantheon-Text-Medium.ttf'); }
@font-face { font-family: 'AppFont'; font-style: italic; src: url('GT-Pantheon-Text-Medium-Italic.ttf'); }
@font-face { font-family: 'AppFont Heavy'; src: url('GT-Pantheon-Text-Black.ttf'); }
@font-face { font-family: 'AppFont Heavy'; font-style: italic; src: url('GT-Pantheon-Text-Black-Italic.ttf'); }

html { scrollbar-gutter: stable; overflow-y: auto; }
body { -webkit-overflow-scrolling: touch; }

.card {
    font-family: var(--font-main);
    font-size: var(--font-size-base);
    line-height: 1.5;
    background-color: var(--bg-light);
    color: var(--text-main-light);
    overflow: hidden;
    text-align: left;
    transition: background-color 0.4s ease, color 0.4s ease;
}

.nightMode.card {
    background-color: var(--bg-dark);
    color: var(--text-main-dark);
}

#prompt-sentence,
#context-line-prompt,
.reverse,
.quaestionum-a {
    white-space: pre-wrap;
    overflow-wrap: break-word;
    word-break: normal;
    -webkit-hyphens: none;
    -moz-hyphens: none;
    -ms-hyphens: none;
    hyphens: none;
}

/* A simple utility class to prevent line breaks */
.no-wrap {
    white-space: nowrap;
}

@keyframes symbol-color-flow { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes bounce-and-wiggle { 0%, 40%, 100% { transform: translateY(0) rotate(0deg); } 4% { transform: translateY(-10px) rotate(0deg); } 8% { transform: translateY(0) rotate(0deg); } 12% { transform: translateY(-5px) rotate(0deg); } 16% { transform: translateY(0) rotate(0deg); } 50%, 65%, 100% { transform: rotate(0deg); } 53% { transform: rotate(3deg); } 56% { transform: rotate(-2deg); } 59% { transform: rotate(1deg); } 62% { transform: rotate(0deg); } }
@keyframes fadeInDown { from { opacity: 0; transform: translateY(-100px); } to { opacity: 1; translateY(0); } }
@keyframes slideUpAndFadeIn { from { opacity: 0; transform: translateY(100px); } to { opacity: 1; transform: translateY(0); } }

.card1 .animated-border-container { animation: fadeInDown 0.7s ease-out forwards, symbol-color-flow 3s ease-in-out 0.7s infinite; }
#answer-wrapper .animated-border-container { animation: slideUpAndFadeIn 1.2s cubic-bezier(0.2, 0.8, 0.2, 1) forwards, symbol-color-flow 2s ease-in-out 1.2s infinite; }

.animated-border-container {
    max-width: 1080px;
        margin: 1em auto;
    padding: 5px;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02), 0 10px 20px rgba(0, 0, 0, 0.04);
    background-size: 200% 200%;
    background-image: linear-gradient(
        100deg,
        var(--divider-color-1), 
        var(--divider-color-3) 25%,
        var(--divider-color-2) 50%,
        var(--divider-color-3) 75%,
        var(--divider-color-1)
    );
}

/* --- SVG BORDER: THE LIVING PALETTE (DEFINITIVE VERSION) --- */
.svg-image-container {
    /* Base styling */
    max-width: 250px;
    margin: 2em auto 1em auto;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02), 0 10px 20px rgba(0, 0, 0, 0.04);
    padding: 5px; /* Re-establish padding for the border effect */
    opacity: 0;

    /* --- The Animation --- */
    /* We use the original, simple symbol-color-flow which works perfectly */
    animation: smoothFadeInUp 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) forwards,
               symbol-color-flow 7s linear infinite;
    display: flex; /* Keep flexbox for robust centering */
    justify-content: center;
    align-items: center;

    /* --- The Gradient and Size --- */
    /* This is the key: a large size to stretch the gradient, ensuring all colors appear */
    background-size: 900% 900%; 
    background-image: linear-gradient(
        110deg,
        #E4A32E,   /* Gold */
        #F8C3CD,   /* Pink */
        #6B8C4F,   /* Green */
        #165C8E,   /* Blue */
        #E73F5E,   /* Red */
        #165C8E,   /* Blue */
        #6B8C4F,   /* Green */
        #F8C3CD,   /* Pink */
        #E4A32E    /* Gold */
    );
}

#prompt-box, #answer-box {
    padding: 1em 2em; 
    background-color: var(--card-bg-light);
    border-radius: 8px;
    position: relative;
    overflow: hidden;
    z-index: 1;
    text-shadow: 0 2px 4px rgba(0,0,0,0.03);
}

.nightMode #prompt-box, .nightMode #answer-box { background-color: var(--card-bg-dark); }

/* --- CORRECTED BORDER STATES FOR IMMEDIATE ANIMATION --- */

/* This new rule targets ALL THREE states to override the animation timing. */
#answer-container.border-correct,
#answer-container.border-incorrect,
#answer-container.border-assisted {
    /* Re-declare the full animation property here.
       We keep the entrance animation, but change the gradient flow to have a 0s delay. */
    animation: slideUpAndFadeIn 1.2s cubic-bezier(0.2, 0.8, 0.2, 1) forwards,
               symbol-color-flow 2s ease-in-out 0s infinite; /* Delay is now 0s */
}

/* Now, we just set the specific background for each state */
#answer-container.border-correct {
    background-image: linear-gradient(125deg, var(--green-base), var(--green-highlight), var(--green-base));
}

#answer-container.border-incorrect {
    background-image: linear-gradient(125deg, var(--red-base), var(--red-highlight), var(--red-base));
}

#answer-container.border-assisted {
    background-image: linear-gradient(125deg, var(--blue-base), var(--blue-highlight), var(--blue-base));
}

#prompt-sentence, #context-line-prompt { font-size: 1.4em; line-height: 1.4; }
#prompt-sentence { font-style: italic; color: var(--text-subtle-light); }
.nightMode #prompt-sentence { color: var(--text-subtle-dark); }

.prompt-divider,
.divider {
    all: unset;
    display: block;
    height: 1px;
    margin: 1.2em auto;
    width: 80%;
    border-radius: 1px;
    background: linear-gradient(to right, 
        transparent 0%, 
        hsla(var(--text-subtle-light-hsl), 0.3) 20%, 
        hsla(var(--text-subtle-light-hsl), 0.6) 50%, 
        hsla(var(--text-subtle-light-hsl), 0.3) 80%, 
        transparent 100%
    );
}

.nightMode .prompt-divider,
.nightMode .divider {
    background: linear-gradient(to right, 
        transparent 0%, 
        hsla(var(--text-subtle-dark-hsl), 0.3) 20%, 
        hsla(var(--text-subtle-dark-hsl), 0.6) 50%, 
        hsla(var(--text-subtle-dark-hsl), 0.3) 80%, 
        transparent 100%
    );
}

.reverse { font-family: 'AppFont Heavy', serif; font-size: 2.5em; text-align: center; color: var(--text-subtle-light); padding-top: 0em; }
.nightMode .reverse { color: var(--text-subtle-dark); }

.input-wrapper {
    display: inline-block;
    vertical-align: baseline;
    margin: 0 0px;
}

.cloze-input-container {
    display: inline-block;
    position: relative;
    vertical-align: baseline;
    border-bottom: 2px dashed var(--text-subtle-light);
    transition: border-bottom-color 0.3s ease-in-out;
    line-height: 1;
        padding-bottom: 7px;
}
.cloze-input-container.no-right-pad .cloze-text-display,
.cloze-input-container.no-right-pad .cloze-input-real {
    padding-right: 0;
}
.cloze-input-container:focus-within {
    border-bottom: 2px solid var(--divider-color-2);
}
.nightMode .cloze-input-container {
    border-bottom-color: var(--text-subtle-dark);
}
.nightMode .cloze-input-container:focus-within {
    border-bottom: 2px solid var(--divider-color-2);
}

.cloze-text-display {
    font-family: 'AppFont Heavy', serif;
    font-style: italic;
    font-size: inherit;
    line-height: inherit;
    color: var(--text-main-light);
    padding: 0 4px;
    margin: 0 -4px;
    white-space: pre;
    visibility: hidden;
}
.nightMode .cloze-text-display {
    color: var(--text-main-dark);
}
.cloze-text-display.is-typing {
    visibility: visible;
}

.cloze-input-real {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    opacity: 1;
    color: transparent;
    caret-color: var(--text-main-light);
    font-family: 'AppFont Heavy', serif;
    font-style: italic;
    font-size: inherit;
    padding: 0 4px;
    margin: 0 -4px;
    outline: none;
    box-shadow: none;
    -webkit-appearance: none;
    border-radius: 0;
}
.nightMode .cloze-input-real {
    caret-color: var(--text-main-dark);
}

.cloze-space {
    white-space: pre;
}

/* --- IMPROVEMENT 3: NEW SHARED GRADIENT CLASS --- */
.gradient-text {
    font-family: var(--font-heavy);
    display: inline-block;
    background-size: 400% 400%;
    padding: 0em 1em; 
    margin: 0em -1em;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: symbol-color-flow 3s ease-in-out infinite;
}

/* --- REFACTORED GREEN TEXT STYLES --- */

/* This is now the single source for the "correct answer" green gradient.
   It inherits the flow animation from .gradient-text. */
.typed-answer-correct {
    background-image: linear-gradient(125deg, var(--green-base), var(--green-highlight), var(--green-base));
}

/* This class is now ONLY responsible for the reveal animation.
   It's designed to be used WITH .typed-answer-correct. */
.animated-text {
    font-style: italic;
    opacity: 0;
    
    /* We override the animation from .gradient-text to add the reveal effect. */
    animation: reveal-text 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) forwards,
               symbol-color-flow 3s ease-in-out 0.5s infinite;
}


@keyframes swimAndFade { 0% { opacity: 0; transform: translate(0, 0) scale(1); } 20% { opacity: 0.09; } 80% { opacity: 0.04; } 100% { opacity: 0; transform: translate(30px, -20px) scale(0.8); } }
.shoal-container { position: absolute; width: 250px; height: 180px; top: 5px; right: 5px; pointer-events: none; z-index: 2; }
.shoal-fish { position: absolute; font-family: 'AppFont Heavy', serif; color: var(--text-subtle-light); opacity: 0; user-select: none; }
.nightMode .shoal-fish { color: var(--text-subtle-dark); }

.quaestionum-a { font-size: 1.4em; line-height: 1.4; }


.interpunct-quote {
    font-family: var(--font-heavy);
    font-style: italic;
    background-size: 400% 400%;
    padding: 1em; 
    margin: -1em;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    display: inline-block;
    opacity: 1;
    animation: symbol-color-flow 3s ease-in-out infinite;
    /* --- UPDATED: Using the new Golden Ticket gradient for a "shiny" effect --- */
    background-image: linear-gradient(135deg,
        var(--gold-shadow) 0%,
        var(--gold-mid) 25%,
        var(--gold-highlight) 45%,
        var(--gold-glint) 50%,
        var(--gold-highlight) 55%,
        var(--gold-mid) 75%,
        var(--gold-shadow) 100%
    );
}

@media (max-width: 500px) {
    .reverse { font-size: 1.8em !important; }
    #prompt-box, #answer-box { transition: background-color 0.4s ease !important; padding: 1.2em 0.8em !important; }
    #prompt-sentence, #context-line-prompt, .quaestionum-a { font-size: 1.25em !important; }
}

@keyframes reveal-text {
    from { opacity: 0; transform: translateY(10px) scale(1.01); }
    to { opacity: 1; transform: translateY(0) scale(1.01); }
}

#prompt-sentence,
#context-line-prompt,
.quaestionum-a {
    text-align: left;
}

/* === SVG IMAGE STYLING === */

/* --- NEW, REFLOW-FREE ANIMATION --- */
@keyframes smoothFadeInUp {
    from {
        opacity: 0;
        /* Start the image 10px lower */
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        /* End at its natural position */
        transform: translateY(0);
    }
}

/* This rule is now simpler, as the border logic is handled above */
.svg-image-container {
    max-width: 250px;
    margin: 2em auto 1em auto;
    border-radius: 12px;
    background-color: transparent; /* The gradient is the background now */
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02), 0 10px 20px rgba(0, 0, 0, 0.04);
    opacity: 0;
    display: flex; /* This is the key */
    justify-content: center; /* Optional: ensures centering */
    align-items: center; /* Optional: ensures centering */
}

/* Animate the image in slightly after the main card content appears */
.card1 .svg-image-container {
    animation-delay: 0.5s; /* Delay on the Front card */
}
#answer-wrapper + .svg-image-container {
    animation-delay: 1.0s; /* Delay on the Back card */
}

/* This robust rule targets any direct child (img, svg, etc.) inside the container,
   preventing layout shifts by forcing block behavior from the start. */
.svg-image-container > * {
    display: block;
    width: 100%;
    height: auto;
    vertical-align: bottom;
    border-radius: 8px; /* Keeps the inner content's corners rounded */
}

/* === HINT TOOLTIP STYLING === */
.hint-tooltip {
    position: absolute; /* Positioned by JS */
    /* Horizontally center on the calculated 'left' position, and
       the 'top' of the tooltip will be 10px below the bottom of the SVG */
    transform: translate(-50%, 10px); 
    background-color: var(--divider-color-2);
    color: var(--divider-color-1);
    font-family: var(--font-main); /* Corrected from AppFont */
    font-style: italic;
    font-size: 1.2em;
    padding: 0.5em 1em;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    z-index: 100;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease, transform 0.2s ease;
    white-space: nowrap;
}
.hint-tooltip.visible {
    opacity: 1;
    /* Animate downwards by a few pixels for a nice "appearing" effect */
    transform: translate(-50%, 15px); 
}

/* DARK MODE TOOLTIP */
.nightMode .hint-tooltip {
    background-color: var(--divider-color-1); /* Use the light parchment for the background */
    color: var(--divider-color-2); /* Use the deep coffee for the text */
}
```