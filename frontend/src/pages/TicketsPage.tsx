import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "./TicketsPage.css";

interface Ticket {
  id: string;
  user_email: string;
  issue: string;
  category: "billing" | "technical" | "account" | "general";
  priority: "low" | "medium" | "high" | "urgent";
  status: "Open" | "In Progress" | "Resolved" | "Closed";
  created_at: string;
  triage_label?: string;
}

interface TicketFormData {
  user_email: string;
  issue: string;
  category: "billing" | "technical" | "account" | "general";
  priority: "low" | "medium" | "high" | "urgent";
}

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export default function TicketsPage() {
  const queryClient = useQueryClient();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [editingTicketId, setEditingTicketId] = useState<string | null>(null);
  const [editingStatus, setEditingStatus] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [formData, setFormData] = useState<TicketFormData>({
    user_email: "",
    issue: "",
    category: "general",
    priority: "medium",
  });

  const ticketsQuery = useQuery({
    queryKey: ["tickets"],
    queryFn: async (): Promise<Ticket[]> => {
      const response = await fetch(`${API_BASE_URL}/tickets`, {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to fetch tickets");
      }

      return response.json();
    },
    staleTime: 30_000,
  });

  useEffect(() => {
    if (ticketsQuery.data) {
      setTickets(ticketsQuery.data);
    }
  }, [ticketsQuery.data]);

  useEffect(() => {
    if (ticketsQuery.error instanceof Error) {
      setErrorMessage(ticketsQuery.error.message);
      const timeoutId = globalThis.setTimeout(
        () => setErrorMessage(null),
        5000,
      );
      return () => globalThis.clearTimeout(timeoutId);
    }
  }, [ticketsQuery.error]);

  // Create ticket mutation
  const createTicketMutation = useMutation({
    mutationFn: async (data: TicketFormData) => {
      const response = await fetch(`${API_BASE_URL}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...data,
          source: "chatbot",
        }),
        credentials: "include",
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to create ticket");
      }

      return response.json();
    },
    onSuccess: (data) => {
      setSuccessMessage(`Ticket created successfully! ID: ${data.ticket_id}`);
      setFormData({
        user_email: "",
        issue: "",
        category: "general",
        priority: "medium",
      });

      queryClient.invalidateQueries({ queryKey: ["tickets"] });

      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (error: Error) => {
      setErrorMessage(error.message);
      setTimeout(() => setErrorMessage(null), 5000);
    },
  });

  // Update ticket status mutation
  const updateStatusMutation = useMutation({
    mutationFn: async (variables: {
      ticketId: string;
      userEmail: string;
      newStatus: string;
    }) => {
      const response = await fetch(
        `${API_BASE_URL}/tickets/${variables.ticketId}/status`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticket_id: variables.ticketId,
            user_email: variables.userEmail,
            status: variables.newStatus,
          }),
          credentials: "include",
        },
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to update status");
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      setSuccessMessage("Status updated successfully!");
      setTickets((prev) =>
        prev.map((ticket) =>
          ticket.id === variables.ticketId
            ? { ...ticket, status: variables.newStatus as any }
            : ticket,
        ),
      );
      setEditingTicketId(null);
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (error: Error) => {
      setErrorMessage(error.message);
      setTimeout(() => setErrorMessage(null), 5000);
    },
  });

  const handleFormChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreateTicket = async (
    e: React.SyntheticEvent<HTMLFormElement>,
  ) => {
    e.preventDefault();

    if (!formData.user_email || !formData.issue) {
      setErrorMessage("Email and issue are required");
      setTimeout(() => setErrorMessage(null), 5000);
      return;
    }

    if (formData.issue.length < 10) {
      setErrorMessage("Issue description must be at least 10 characters");
      setTimeout(() => setErrorMessage(null), 5000);
      return;
    }

    createTicketMutation.mutate(formData);
  };

  const handleStatusSave = (ticketId: string, userEmail: string) => {
    if (!editingStatus) {
      setEditingTicketId(null);
      return;
    }

    updateStatusMutation.mutate({
      ticketId,
      userEmail,
      newStatus: editingStatus,
    });
  };

  const handleStatusCancel = () => {
    setEditingTicketId(null);
    setEditingStatus("");
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "#dc2626";
      case "high":
        return "#ea580c";
      case "medium":
        return "#f59e0b";
      case "low":
        return "#10b981";
      default:
        return "#6b7280";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "Open":
        return "#3b82f6";
      case "In Progress":
        return "#f59e0b";
      case "Resolved":
        return "#10b981";
      case "Closed":
        return "#6b7280";
      default:
        return "#6b7280";
    }
  };

  const renderTicketsContent = () => {
    if (ticketsQuery.isLoading) {
      return (
        <div className="empty-state">
          <p>Loading tickets...</p>
        </div>
      );
    }

    if (tickets.length === 0) {
      return (
        <div className="empty-state">
          <p>No tickets yet. Create your first ticket above.</p>
        </div>
      );
    }

    return (
      <div className="table-wrapper">
        <table className="tickets-table">
          <thead>
            <tr>
              <th style={{ width: "12%" }}>Ticket ID</th>
              <th style={{ width: "14%" }}>Status</th>
              <th style={{ width: "12%" }}>Category</th>
              <th style={{ width: "12%" }}>Priority</th>
              <th style={{ width: "20%" }}>Issue</th>
              <th style={{ width: "18%" }}>Created</th>
              <th style={{ width: "12%" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => (
              <tr key={ticket.id} className="ticket-row">
                <td style={{ width: "12%" }} title={ticket.id}>
                  <code className="ticket-id">
                    {ticket.id.substring(0, 8)}...
                  </code>
                </td>
                <td style={{ width: "14%" }}>
                  {editingTicketId === ticket.id ? (
                    <div className="status-edit-inline">
                      <select
                        value={editingStatus}
                        onChange={(e) => setEditingStatus(e.target.value)}
                        className="status-select"
                        autoFocus
                      >
                        <option value="">Select Status</option>
                        <option value="Open">Open</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Resolved</option>
                        <option value="Closed">Closed</option>
                      </select>
                      <button
                        className="btn btn-sm btn-save"
                        onClick={() =>
                          handleStatusSave(ticket.id, ticket.user_email)
                        }
                        disabled={updateStatusMutation.isPending}
                      >
                        Save
                      </button>
                      <button
                        className="btn btn-sm btn-cancel"
                        onClick={handleStatusCancel}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor: getStatusColor(ticket.status),
                      }}
                    >
                      {ticket.status}
                    </span>
                  )}
                </td>
                <td style={{ width: "12%" }}>
                  <span className="category-badge">{ticket.category}</span>
                </td>
                <td style={{ width: "12%" }}>
                  <span
                    className="priority-badge"
                    style={{
                      color: getPriorityColor(ticket.priority),
                      fontWeight: "600",
                    }}
                  >
                    {ticket.priority.toUpperCase()}
                  </span>
                </td>
                <td style={{ width: "20%" }} title={ticket.issue}>
                  <span className="issue-text">
                    {ticket.issue.substring(0, 40)}...
                  </span>
                </td>
                <td style={{ width: "18%" }}>
                  {new Date(ticket.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>
                <td style={{ width: "12%" }}>
                  {editingTicketId !== ticket.id && (
                    <button
                      className="btn btn-sm btn-edit"
                      onClick={() => {
                        setEditingTicketId(ticket.id);
                        setEditingStatus(ticket.status);
                      }}
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="tickets-container">
      <div className="tickets-header">
        <h1>Support Tickets</h1>
        <p>Create and manage your support tickets</p>
      </div>

      {successMessage && (
        <div className="alert alert-success" role="alert">
          {successMessage}
        </div>
      )}
      {errorMessage && (
        <div className="alert alert-error" role="alert">
          {errorMessage}
        </div>
      )}

      {/* Create Ticket Form */}
      <div className="create-ticket-section">
        <h2>Create New Ticket</h2>
        <form onSubmit={handleCreateTicket} className="ticket-form">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="user_email">Email Address *</label>
              <input
                type="email"
                id="user_email"
                name="user_email"
                value={formData.user_email}
                onChange={handleFormChange}
                placeholder="your@email.com"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="issue">Issue Description *</label>
              <textarea
                id="issue"
                name="issue"
                value={formData.issue}
                onChange={handleFormChange}
                placeholder="Describe your issue in detail (minimum 10 characters)"
                rows={4}
                required
                minLength={10}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="category">Category</label>
              <select
                id="category"
                name="category"
                value={formData.category}
                onChange={handleFormChange}
              >
                <option value="general">General</option>
                <option value="billing">Billing</option>
                <option value="technical">Technical</option>
                <option value="account">Account</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="priority">Priority</label>
              <select
                id="priority"
                name="priority"
                value={formData.priority}
                onChange={handleFormChange}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createTicketMutation.isPending}
            >
              {createTicketMutation.isPending ? "Creating..." : "Create Ticket"}
            </button>
          </div>
        </form>
      </div>

      {/* My Tickets Table */}
      <div className="my-tickets-section">
        <h2>My Tickets</h2>
        {renderTicketsContent()}
      </div>
    </div>
  );
}
