(function (){
    const toggle = document.getElementById("chatToggle");
    const box = document.getElementById("chatBox");
    const closeBtn = document.getElementById("chatClose");
    const msgs = document.getElementById("chatMessages");
    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSend");

    function addMessage(text, who) {
        const div = document.createElement("div");
        div.className = "msg " + (who === "user" ? "user" : "bot");

        if (who === "bot") {
            div.innerHTML = text;
        } 
        else {
            div.textContent = text;
        }
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    async function send() {
        const text = (input.value || "").trim();
        if (!text) return;
        input.value = "";
        addMessage(text, "user");

        try {
            const result = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });
            const data = await result.json();
            addMessage(data.reply || "Sorry, something went wrong.", "bot");
        } catch(e) {
            addMessage("Network error. Please try again or call the office.", "bot");
        }
    }
    toggle.addEventListener("click", () => {
        box.classList.toggle("hidden");
        if (!box.classList.contains("hidden") && msgs.childElementCount === 0) {
            addMessage("Hi! I can help with hours, location, services, insurance info, and appointment requests.", "bot");
        }
    });

    closeBtn.addEventListener("click", () => box.classList.add("hidden"));
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
})();