"use client";

import { useState, useRef, useEffect } from "react";

// Matches the port configured in your app.py
const API_BASE = "http://localhost:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function ConsultantChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [requirements, setRequirements] = useState<any | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom of the chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startSession = async () => {
    setIsLoading(true);
    setRequirements(null);
    try {
      const res = await fetch(`${API_BASE}/consultant/session/new`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.session_id && data.greeting) {
        setSessionId(data.session_id);
        setMessages([{ role: "assistant", content: data.greeting }]);
      }
    } catch (error) {
      console.error("Failed to start session:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/consultant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage,
        }),
      });
      const data = await res.json();
      
      if (data.reply) {
        setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
      } else if (data.error) {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const generateSummary = async () => {
    if (!sessionId) return;
    setIsExtracting(true);
    try {
      const res = await fetch(`${API_BASE}/consultant/session/${sessionId}/summary`);
      const data = await res.json();
      if (data.requirements) {
        setRequirements(data.requirements);
      } else if (data.error) {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error("Failed to generate summary:", error);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans text-gray-900">
      {/* Left Column: Chat Interface */}
      <div className={`flex flex-col h-full transition-all duration-300 ${requirements ? 'w-1/2 border-r border-gray-200' : 'w-full max-w-4xl mx-auto'}`}>
        
        {/* Header */}
        <header className="bg-white border-b border-gray-200 p-4 flex justify-between items-center shadow-sm z-10">
          <div>
            <h1 className="text-xl font-bold text-blue-700">Nonprofit Web Consultant</h1>
            <p className="text-sm text-gray-500">
              {sessionId ? `Session ID: ${sessionId.substring(0, 8)}...` : "Not connected"}
            </p>
          </div>
          <div className="space-x-3">
            {sessionId && (
              <button
                onClick={generateSummary}
                disabled={isExtracting || isLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {isExtracting ? "Extracting..." : "Generate Brief"}
              </button>
            )}
            <button
              onClick={startSession}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 disabled:opacity-50"
            >
              {sessionId ? "Restart Session" : "Start Session"}
            </button>
          </div>
        </header>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {!sessionId ? (
            <div className="h-full flex items-center justify-center text-gray-400">
              <p>Click "Start Session" to begin mapping out your website.</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-5 py-3 whitespace-pre-wrap shadow-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-br-none"
                      : "bg-white border border-gray-200 text-gray-800 rounded-bl-none"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}
          {isLoading && sessionId && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 text-gray-500 rounded-2xl rounded-bl-none px-5 py-3 shadow-sm">
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form onSubmit={sendMessage} className="p-4 bg-white border-t border-gray-200">
          <div className="flex space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!sessionId || isLoading}
              placeholder={sessionId ? "Type your message..." : "Start a session first..."}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!sessionId || isLoading || !input.trim()}
              className="px-6 py-3 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              Send
            </button>
          </div>
        </form>
      </div>

      {/* Right Column: Extracted Requirements Brief */}
      {requirements && (
        <div className="w-1/2 h-full flex flex-col bg-white overflow-hidden shadow-xl">
          <header className="bg-gray-800 text-white p-4 border-b border-gray-700 flex justify-between items-center">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              Website Requirements Brief
            </h2>
            <button onClick={() => setRequirements(null)} className="text-gray-400 hover:text-white">
              ✕
            </button>
          </header>
          
          <div className="flex-1 overflow-y-auto p-6 text-sm">
            <div className="prose prose-sm max-w-none prose-blue">
              <p className="text-gray-500 mb-4">
                Structured data extracted from the conversation schema.
              </p>
              
              <div className="bg-gray-50 p-4 rounded-md border border-gray-200 font-mono text-xs overflow-x-auto">
                <pre>{JSON.stringify(requirements, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}