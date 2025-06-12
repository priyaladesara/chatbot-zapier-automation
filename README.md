# Chatbot-to-Zapier Automation Bridge

A Flask-based middleware server that seamlessly integrates any chatbot with Zapier's automation platform through OpenAI's Chat Completion API and Model Context Protocol (MCP). Simply send natural language requests to execute Zapier automations without writing any code!

## 🚀 Features

- **Universal Chatbot Integration**: Works with any chatbot that can make HTTP requests to `/chat` endpoint
- **Zero-Code Automation**: Execute Zapier workflows through natural language - no function writing required
- **Intelligent Tool Discovery**: Automatically discovers and registers all available Zapier actions via MCP
- **OpenAI Function Calling**: Leverages GPT-3.5-turbo to intelligently map user requests to appropriate Zapier actions
- **Seamless Workflow**: User input → OpenAI analysis → Zapier execution → Formatted response
- **Auto-formatting**: Returns clean, user-friendly responses with clickable links and structured data

## 📋 Prerequisites

- Python 3.8+
- OpenAI API key
- Zapier account with MCP server access
- Any chatbot platform (Discord, Slack, Telegram, custom web chat, etc.)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/flask-mcp-integration.git
   cd flask-mcp-integration
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your configuration:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   MCP_SERVER_URL=https://your-zapier-mcp-server-url
   PORT=5000
   FLASK_DEBUG=False
   ```

## 🚀 Usage

### Starting the Server

```bash
python app.py
```

The server will start on `http://localhost:5000` (or your configured port).

### API Endpoints

#### POST /chat
Send a message and get an AI response with potential tool execution.

**Request:**
```json
{
  "message": "Your message here"
}
```

**Response:**
```json
{
  "response": "AI response with tool results"
}
```

#### GET /tools
Get list of available tools from the MCP server.

**Response:**
```json
{
  "tools": [...],
  "count": 3
}
```

### Example Usage

#### From Any Chatbot Platform

```bash
# Your chatbot sends this request to the Flask server
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Send an email to john@example.com saying the project is complete"}'

# Response: Email sent successfully via Zapier automation
```

#### Natural Language Automation Examples

```json
// Create a new Trello card
{"message": "Create a Trello card in my 'Projects' board titled 'Website Redesign' with description 'Update homepage layout'"}

// Send Slack notification
{"message": "Send a message to #general channel saying 'Deployment completed successfully'"}

// Add row to Google Sheets
{"message": "Add a new row to my 'Sales' spreadsheet with customer name 'John Doe', amount '$500', date 'today'"}

// Create calendar event
{"message": "Schedule a meeting for tomorrow at 2 PM titled 'Project Review' and invite team@company.com"}
```

## 🏗️ Architecture & Workflow

![Screenshot 2025-06-12 122339](https://github.com/user-attachments/assets/5886dc83-f314-415e-813d-71a83b328ed1)


### Step-by-Step Process

1. **User Input**: Any chatbot sends natural language request to `/chat` endpoint
2. **Tool Discovery**: Flask server fetches available Zapier actions from MCP server
3. **AI Analysis**: OpenAI analyzes the request and selects appropriate Zapier action
4. **Function Calling**: OpenAI generates structured parameters for the selected action
5. **Zapier Execution**: MCP client executes the automation workflow
6. **Response Formatting**: Results are formatted into user-friendly response
7. **Chatbot Display**: Clean, actionable response sent back to the chatbot user

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Yes | - |
| `MCP_SERVER_URL` | URL of your MCP server | Yes | - |
| `PORT` | Port for Flask server | No | 5000 |
| `FLASK_DEBUG` | Enable debug mode | No | False |

### MCP Server Compatibility

This integration works with any MCP server that supports:
- Tool listing via `list_tools()`
- Tool execution via `call_tool(name, parameters)`
- HTTP transport protocol


## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.



## 📊 Performance

- Supports concurrent requests
- Efficient async MCP communication
- Minimal memory footprint
- Fast tool discovery and execution

---

**Built with ❤️ using Flask, OpenAI, and FastMCP**
