from flask import Flask, request, jsonify
import asyncio
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

load_dotenv()

app = Flask(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL')


if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not MCP_SERVER_URL:
    raise ValueError("MCP_SERVER_URL environment variable is required")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

class MCPManager:
    def __init__(self, server_url):
        self.server_url = server_url
        self.transport = StreamableHttpTransport(server_url)
        self.client = Client(transport=self.transport)
        self.available_tools = []
    
    async def get_available_tools(self):
        """Fetch available tools from MCP server"""
        try:
            async with self.client:
                tools = await self.client.list_tools()
                self.available_tools = []
                
                for tool in tools:
                   
                    tool_schema = getattr(tool, 'inputSchema', None)
                    
                    if tool_schema and hasattr(tool_schema, 'get'):
                        
                        properties = tool_schema.get('properties', {})
                        required = tool_schema.get('required', [])
                    else:
                       
                        properties = {}
                        required = []
                    
                   
                    if 'instructions' in required:
                        required = [r for r in required if r != 'instructions']
                    
                    # chatcompletioon required format
                    tool_definition = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required
                            }
                        }
                    }
                    
                    self.available_tools.append(tool_definition)
                
                return self.available_tools
        except Exception as e:
            print(f"Error fetching tools: {e}")
            return []
    
    async def execute_tool(self, tool_name, parameters):
        """Execute a specific tool with given parameters"""
        try:
            async with self.client:
              
            #  use **unpacking ones as to append new parameters and convert into in dict
                mcp_parameters = {
                    "instructions": f"Execute the {tool_name} tool with the following parameters",
                    **parameters  
                }
                
                result = await self.client.call_tool(tool_name, mcp_parameters)
               
                if result and len(result) > 0:
                    if hasattr(result[0], 'text'):
                        try:
                            return json.loads(result[0].text)
                        except json.JSONDecodeError:
                            return {"result": result[0].text}
                    else:
                        return {"result": str(result[0])}
                return {"result": "No result returned"}
        except Exception as e:
            print(f"Error executing tool {tool_name}: {e}")
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

# Initialize MCP Manager - can further optimized even when using more than one MCP server.
mcp_manager = MCPManager(MCP_SERVER_URL)

def run_async(coro):
    """Helper function to run async code in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Get user message from request
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Step 1: Get available tools from MCP server
        available_tools = run_async(mcp_manager.get_available_tools())
        
        # Step 2: Prepare chat completion with function calling
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can use various tools to help users. When a user asks for something that matches available tools, use the appropriate function. Always provide clear, friendly responses with proper formatting. If you create or access any links, format them as clickable markdown links."},
            {"role": "user", "content": user_message}
        ]
        
        # Step 3: Call OpenAI Chat Completion with functions
        if available_tools:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                tools=available_tools,
                tool_choice="auto"
            )
        else:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages
            )
        
        assistant_message = response.choices[0].message
        
        # Step 4: Check if tool was called
        if assistant_message.tool_calls:
            tool_call = assistant_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"Executing tool: {function_name}")
            print(f"Arguments: {function_args}")
            
            # Step 5: Execute the MCP tool
            tool_result = run_async(mcp_manager.execute_tool(function_name, function_args))
            
            # Step 6: Send tool result back to OpenAI for final response with enhanced formatting
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": tool_call.function.arguments
                    }
                }]
            })
            # to remeber context used before 
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result) #serialization is needed to obj->str
            })
            
            # displaying finall result in good format , need to instruct gpt.(just guiding gpt)
            messages.append({
                "role": "system",
                "content": "Format your response in a user-friendly way. If there are any URLs in the tool result, format them as clickable markdown links. Provide a clear, concise summary of what was accomplished. Don't show raw JSON or technical details unless specifically requested."
            })
            
            # Get final response from OpenAI (displayingg)
            final_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages
            )
            
            # Return only the beautified response
            return jsonify({
                "response": final_response.choices[0].message.content
            })
        
        else:
            # No function was called, return regular text response
            return jsonify({
                "response": assistant_message.content
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tools', methods=['GET'])
def get_tools():
    """Endpoint to get available tools"""
    try:
        tools = run_async(mcp_manager.get_available_tools())
        return jsonify({
            "tools": tools,
            "count": len(tools)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)