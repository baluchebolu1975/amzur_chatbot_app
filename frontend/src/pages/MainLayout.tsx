import { ReactNode, useState } from "react";
import ChatPage from "./ChatPage";
import TicketsPage from "./TicketsPage";
import "./MainLayout.css";

type TabName = "chatbot" | "tickets";

export default function MainLayout() {
  const [activeTab, setActiveTab] = useState<TabName>("chatbot");

  const tabs: { name: TabName; label: string; icon: string }[] = [
    { name: "chatbot", label: "Chatbot", icon: "💬" },
    { name: "tickets", label: "Tickets", icon: "🎫" },
  ];

  return (
    <div className="main-layout">
      <div className="tab-navigation">
        {tabs.map((tab) => (
          <button
            key={tab.name}
            className={`tab-button ${activeTab === tab.name ? "active" : ""}`}
            onClick={() => setActiveTab(tab.name)}
            title={tab.label}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === "chatbot" && <ChatPage />}
        {activeTab === "tickets" && <TicketsPage />}
      </div>
    </div>
  );
}
