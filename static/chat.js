(function (){
    const toggle = document.getElementById("chatToggle");
    const box = document.getElementById("chatBox");
    const closeBtn = document.getElementById("chatClose");
    const msgs = document.getElementById("chatMessages");
    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSend");

    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    if (!csrfToken) {
        console.error("⚠️ CSRF token not found! Add <meta name='csrf-token' content='{{ csrf_token() }}'> to your HTML");
    }

    function addMessage(text, who) {
        const div = document.createElement("div");
        div.className = "msg " + (who === "user" ? "user" : "bot");

        if (who === "bot") {
            div.innerHTML = text;  // Allow HTML for links
        } 
        else {
            div.textContent = text;  // User text as plain text (security)
        }
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    function showTyping() {
        const typingDiv = document.createElement("div");
        typingDiv.className = "msg bot typing";
        typingDiv.id = "typingIndicator";
        typingDiv.innerHTML = '<span>●</span><span>●</span><span>●</span>';
        msgs.appendChild(typingDiv);
        msgs.scrollTop = msgs.scrollHeight;
        return typingDiv;
    }

    function removeTyping() {
        const typing = document.getElementById("typingIndicator");
        if (typing) typing.remove();
    }

    async function send() {
        const text = (input.value || "").trim();
        if (!text) return;
        
        input.value = "";
        addMessage(text, "user");
        
        const typingIndicator = showTyping();

        try {
            const result = await fetch("/api/chat", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken  // Include CSRF token
                },
                body: JSON.stringify({ message: text })
            });
            
            removeTyping();
            
            if (!result.ok) {
                if (result.status === 429) {
                    addMessage("Please wait a moment before sending another message. 😊", "bot");
                } else {
                    throw new Error(`HTTP ${result.status}`);
                }
                return;
            }
            
            const data = await result.json();
            addMessage(data.reply || "Sorry, something went wrong. Please try again!", "bot");
            
        } catch(e) {
            removeTyping();
            console.error("Chat error:", e);
            addMessage(
                "I'm having trouble connecting right now. 😔<br>" +
                "Please try again in a moment or give us a call!", 
                "bot"
            );
        }
    }

    // Event listeners
    toggle.addEventListener("click", () => {
        box.classList.toggle("hidden");
        if (!box.classList.contains("hidden") && msgs.childElementCount === 0) {
            addMessage(
                "Hi! 👋 I'm here to help answer your questions about our dental office.<br><br>" +
                "Ask me about our hours, services, insurance, or how to schedule an appointment!", 
                "bot"
            );
        }
    });

    closeBtn.addEventListener("click", () => box.classList.add("hidden"));
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => { 
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(); 
        }
    });

    // Disable send button when input is empty
    input.addEventListener("input", () => {
        sendBtn.disabled = !input.value.trim();
    });
})();